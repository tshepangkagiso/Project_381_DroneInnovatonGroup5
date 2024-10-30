from djitellopy import Tello
import threading
import time
import logging
import asyncio
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

class DroneManager:
    def __init__(self):
        self.drone = None
        self.video_streamer = None
        self.is_connected = False
        self.battery_level = 0
        self.connection_lock = threading.Lock()
        self.keep_alive_thread = None
        
        # Movement constants
        self.SPEED = 50          # cm/s - Tello's speed
        self.ROTATION_SPEED = 45 # degrees/second
        self.MIN_DISTANCE = 20   # minimum distance to move (cm)
        self.MAX_HEIGHT = 3000   # maximum height in cm
        self.MIN_BATTERY = 20    # minimum battery percentage for operations

    def set_video_streamer(self, video_streamer):
        """Set the video streamer component."""
        self.video_streamer = video_streamer

    def connect_drone(self) -> bool:
        """Establish connection with the drone."""
        with self.connection_lock:
            try:
                if self.is_connected:
                    return True

                logger.info("Connecting to drone...")
                self.drone = Tello()
                self.drone.connect()
                time.sleep(1)  # Allow connection to stabilize

                # Test connection and get battery
                self.battery_level = self.drone.get_battery()
                logger.info(f"Battery level: {self.battery_level}%")

                # Set initial speed
                self.drone.set_speed(self.SPEED)

                # Initialize video
                self.drone.streamon()
                time.sleep(2)  # Wait for stream to initialize

                self.is_connected = True
                self.start_keep_alive()
                logger.info("Drone connected successfully")
                return True

            except Exception as e:
                logger.error(f"Failed to connect to drone: {e}")
                self.cleanup()
                return False

    async def move_to(self, x: float, y: float, z: float) -> bool:
        """Move drone to specified coordinates (in meters)."""
        try:
            if not self.is_connected:
                logger.error("Drone not connected")
                return False

            if self.battery_level < self.MIN_BATTERY:
                logger.error("Battery too low for movement")
                return False

            # Convert to cm for Tello
            x_cm = int(x * 100)
            y_cm = int(y * 100)
            z_cm = int(z * 100)

            if z_cm > self.MAX_HEIGHT:
                logger.error(f"Requested height {z_cm}cm exceeds maximum {self.MAX_HEIGHT}cm")
                return False

            # Get current position (in cm)
            current_height = self.drone.get_height()

            # Adjust height first for safety
            height_diff = z_cm - current_height
            if abs(height_diff) > self.MIN_DISTANCE:
                if height_diff > 0:
                    self.drone.move_up(abs(height_diff))
                else:
                    self.drone.move_down(abs(height_diff))
                await asyncio.sleep(abs(height_diff) / self.SPEED)

            # Move in x direction (forward/backward)
            if abs(x_cm) > self.MIN_DISTANCE:
                if x_cm > 0:
                    self.drone.move_forward(x_cm)
                else:
                    self.drone.move_back(abs(x_cm))
                await asyncio.sleep(abs(x_cm) / self.SPEED)

            # Move in y direction (left/right)
            if abs(y_cm) > self.MIN_DISTANCE:
                if y_cm > 0:
                    self.drone.move_right(y_cm)
                else:
                    self.drone.move_left(abs(y_cm))
                await asyncio.sleep(abs(y_cm) / self.SPEED)

            return True

        except Exception as e:
            logger.error(f"Movement error: {e}")
            return False

    async def rotate(self, degrees: int) -> bool:
        """Rotate drone by specified degrees."""
        try:
            if not self.is_connected:
                return False

            # Normalize degrees to -180 to 180
            degrees = ((degrees + 180) % 360) - 180

            if degrees > 0:
                self.drone.rotate_clockwise(degrees)
            else:
                self.drone.rotate_counter_clockwise(abs(degrees))

            # Wait for rotation to complete
            await asyncio.sleep(abs(degrees) / self.ROTATION_SPEED)
            return True

        except Exception as e:
            logger.error(f"Rotation error: {e}")
            return False

    async def scan_360(self) -> bool:
        """Perform 360-degree scan."""
        try:
            if not self.is_connected:
                return False

            # Do 8 rotations of 45 degrees each
            for _ in range(8):
                if not await self.rotate(45):
                    return False
                await asyncio.sleep(2)  # Pause for scanning
            return True

        except Exception as e:
            logger.error(f"Scan error: {e}")
            return False

    def start_keep_alive(self):
        """Start keep-alive thread with battery monitoring."""
        def keep_alive_loop():
            failed_pings = 0
            max_failed_pings = 3
            last_battery_check = time.time()
            battery_check_interval = 30  # Check battery every 30 seconds
            
            while self.is_connected:
                try:
                    current_time = time.time()
                    
                    # Battery check
                    if current_time - last_battery_check >= battery_check_interval:
                        self.battery_level = self.drone.get_battery()
                        logger.debug(f"Battery Level: {self.battery_level}%")
                        
                        # Emit battery status
                        if self.video_streamer and self.video_streamer.socketio:
                            self.video_streamer.socketio.emit('battery_update', {
                                'battery': self.battery_level,
                                'timestamp': current_time
                            })
                        
                        last_battery_check = current_time
                        failed_pings = 0
                    
                    # Connection check
                    self.drone.get_height()
                    time.sleep(1)
                    
                except Exception as e:
                    failed_pings += 1
                    if failed_pings >= max_failed_pings:
                        logger.error("Lost connection to drone")
                        self.is_connected = False
                        break
                    time.sleep(1)

        self.keep_alive_thread = threading.Thread(
            target=keep_alive_loop,
            daemon=True
        )
        self.keep_alive_thread.start()

    def emergency_land(self):
        """Emergency landing procedure."""
        try:
            if self.is_connected and self.drone:
                logger.warning("Initiating emergency landing")
                self.drone.emergency()
                self.is_connected = False
        except Exception as e:
            logger.error(f"Emergency landing error: {e}")

    def cleanup(self):
        """Clean up drone resources."""
        try:
            self.is_connected = False
            if self.video_streamer:
                self.video_streamer.stop_streaming()
            
            if self.drone:
                try:
                    self.drone.streamoff()
                except:
                    pass
                try:
                    self.drone.end()
                except:
                    pass
                    
            self.drone = None
            
            if self.keep_alive_thread:
                self.keep_alive_thread.join(timeout=2.0)
            
            logger.info("Drone cleanup completed")
            
        except Exception as e:
            logger.error(f"Cleanup error: {e}")