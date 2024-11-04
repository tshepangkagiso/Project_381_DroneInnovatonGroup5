from djitellopy import Tello
import threading
import time
import logging
import os
from .video_streamer import VideoStreamer
from typing import Optional

'''
This DroneManager class handles:

    Drone connection and initialization
    Safety monitoring (battery, connection)
    Emergency procedures
    Movement controls with safety checks
    Video streaming management
    Status monitoring and reporting
    Cleanup procedures

Each method includes error handling and logging. The class is designed to work with both manual control and the patrol system we'll be implementing.
'''

# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if not os.path.exists('logs'):
    os.makedirs('logs')
handler = logging.FileHandler('logs/drone_manager.log')
handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

# Separate logger for keep-alive messages
keepalive_logger = logging.getLogger('keepalive')
keepalive_logger.setLevel(logging.INFO)
keepalive_handler = logging.FileHandler('logs/keepalive.log')
keepalive_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
keepalive_logger.addHandler(keepalive_handler)

class DroneManager:
    def __init__(self, socketio):
        """Initialize DroneManager with SocketIO instance for real-time communication."""
        self.socketio = socketio
        self.drone: Optional[Tello] = None
        self.video_streamer = VideoStreamer(socketio)
        self.is_connected = False
        self.connection_lock = threading.Lock()
        self.keep_alive_thread = None
        self.battery_level = 0
        self.patrol_mode = False
        self.emergency_land_triggered = False
        
        # Flight parameters
        self.max_height = 30  # meters
        self.min_battery = 20  # percentage
        self.movement_speed = 50  # cm/s
        
        logger.info("DroneManager initialized")

    def connect_drone(self) -> bool:
        """Establish connection with the drone."""
        with self.connection_lock:
            try:
                if self.is_connected:
                    logger.info("Drone already connected")
                    return True

                logger.info("Connecting to drone...")
                self.drone = Tello()
                self.drone.connect()
                time.sleep(1)

                # Test connection and get battery
                self.battery_level = self.drone.get_battery()
                logger.info(f"Battery level: {self.battery_level}%")

                # Initialize video
                self.drone.streamon()
                time.sleep(2)  # Wait for stream to initialize

                # Set initial drone parameters
                self.drone.set_speed(self.movement_speed)
                
                self.is_connected = True
                self.start_keep_alive()
                logger.info("Drone connected successfully")
                return True

            except Exception as e:
                logger.error(f"Failed to connect to drone: {e}")
                self.cleanup()
                return False

    def start_keep_alive(self):
        """Start keep-alive thread with battery monitoring and safety checks."""
        def keep_alive_loop():
            failed_pings = 0
            max_failed_pings = 3
            last_battery_check = time.time()
            battery_check_interval = 30
            
            while self.is_connected:
                try:
                    current_time = time.time()
                    
                    # Battery monitoring
                    if current_time - last_battery_check >= battery_check_interval:
                        self.battery_level = self.drone.get_battery()
                        keepalive_logger.debug(f"Battery Level: {self.battery_level}%")
                        
                        # Emergency landing if battery too low
                        if self.battery_level <= self.min_battery:
                            keepalive_logger.warning("Low battery! Initiating emergency landing.")
                            self.emergency_land()
                        
                        # Emit battery status to clients
                        self.socketio.emit('battery_update', {
                            'battery': self.battery_level,
                            'timestamp': current_time,
                            'low_battery': self.battery_level <= self.min_battery
                        })
                        
                        last_battery_check = current_time
                        failed_pings = 0
                    
                    # Quick connection check
                    self.drone.get_height()
                    time.sleep(1)
                    
                except Exception as e:
                    failed_pings += 1
                    keepalive_logger.error(f"Keep-alive error: {e}")
                    if failed_pings >= max_failed_pings:
                        keepalive_logger.error("Lost connection to drone")
                        self.is_connected = False
                        self.emergency_land()
                        break
                    time.sleep(1)

        self.keep_alive_thread = threading.Thread(
            target=keep_alive_loop,
            daemon=True
        )
        self.keep_alive_thread.start()
        logger.info("Keep-alive monitoring started")

    def emergency_land(self):
        """Execute emergency landing procedure."""
        try:
            if not self.emergency_land_triggered and self.drone:
                logger.warning("Executing emergency landing procedure")
                self.emergency_land_triggered = True
                
                # Stop any ongoing patrol
                self.patrol_mode = False
                
                # Land the drone
                self.drone.land()
                
                # Notify clients
                self.socketio.emit('emergency_land', {
                    'message': 'Emergency landing executed',
                    'timestamp': time.time()
                })
                
        except Exception as e:
            logger.error(f"Emergency landing failed: {e}")
            # Try force landing as last resort
            try:
                self.drone.emergency()
            except:
                pass
        finally:
            self.emergency_land_triggered = False

    def cleanup(self):
        """Clean up drone resources and connections."""
        try:
            logger.info("Initiating cleanup procedure")
            self.is_connected = False
            
            if self.video_streamer:
                self.video_streamer.stop_streaming()
                logger.info("Video streaming stopped")
            
            if self.drone:
                try:
                    # Make sure the drone lands
                    if self.drone.is_flying:
                        logger.info("Landing drone during cleanup")
                        self.drone.land()
                except Exception as e:
                    logger.error(f"Error landing drone during cleanup: {e}")
                
                try:
                    self.drone.streamoff()
                    logger.info("Video stream turned off")
                except Exception as e:
                    logger.error(f"Error stopping video stream: {e}")
                
                try:
                    self.drone.end()
                    logger.info("Drone connection ended")
                except Exception as e:
                    logger.error(f"Error ending drone connection: {e}")
                    
            self.drone = None
            
            if self.keep_alive_thread:
                self.keep_alive_thread.join(timeout=2.0)
                logger.info("Keep-alive thread terminated")
            
            logger.info("Cleanup completed")
            
        except Exception as e:
            logger.error(f"Cleanup error: {e}")

    # Movement controls with safety checks
    def move(self, direction: str, distance: int) -> bool:
        """Execute movement command with safety checks."""
        if not self.is_connected or not self.drone:
            logger.error("Cannot move: Drone not connected")
            return False

        try:
            # Safety checks
            if self.battery_level <= self.min_battery:
                logger.warning("Cannot move: Battery too low")
                return False

            current_height = self.drone.get_height()
            
            # Execute movement
            movement_map = {
                'forward': self.drone.move_forward,
                'back': self.drone.move_back,
                'left': self.drone.move_left,
                'right': self.drone.move_right,
                'up': self.drone.move_up,
                'down': self.drone.move_down
            }

            if direction in movement_map:
                # Check height limits for vertical movements
                if direction == 'up' and current_height + distance > self.max_height:
                    logger.warning(f"Cannot move up: Would exceed max height of {self.max_height}m")
                    return False
                    
                if direction == 'down' and current_height - distance < 10:  # 10cm minimum height
                    logger.warning("Cannot move down: Would be too close to ground")
                    return False

                movement_map[direction](distance)
                logger.info(f"Moved {direction} by {distance}cm")
                return True
            else:
                logger.error(f"Invalid movement direction: {direction}")
                return False

        except Exception as e:
            logger.error(f"Movement error: {e}")
            return False

    def rotate(self, direction: str, degrees: int) -> bool:
        """Execute rotation command."""
        if not self.is_connected or not self.drone:
            logger.error("Cannot rotate: Drone not connected")
            return False

        try:
            if direction == 'cw':
                self.drone.rotate_clockwise(degrees)
            elif direction == 'ccw':
                self.drone.rotate_counter_clockwise(degrees)
            else:
                logger.error(f"Invalid rotation direction: {direction}")
                return False
                
            logger.info(f"Rotated {direction} by {degrees} degrees")
            return True

        except Exception as e:
            logger.error(f"Rotation error: {e}")
            return False

    def takeoff(self) -> bool:
        """Execute takeoff command with safety checks."""
        if not self.is_connected or not self.drone:
            logger.error("Cannot takeoff: Drone not connected")
            return False

        try:
            if self.battery_level <= self.min_battery:
                logger.warning("Cannot takeoff: Battery too low")
                return False

            self.drone.takeoff()
            logger.info("Takeoff successful")
            return True

        except Exception as e:
            logger.error(f"Takeoff error: {e}")
            return False

    def land(self) -> bool:
        """Execute landing command."""
        if not self.is_connected or not self.drone:
            logger.error("Cannot land: Drone not connected")
            return False

        try:
            self.drone.land()
            logger.info("Landing successful")
            return True

        except Exception as e:
            logger.error(f"Landing error: {e}")
            return False

    def get_status(self) -> dict:
        """Get current drone status."""
        if not self.is_connected or not self.drone:
            return {
                'connected': False,
                'battery': 0,
                'height': 0,
                'flying': False,
                'patrol_mode': False
            }

        try:
            return {
                'connected': self.is_connected,
                'battery': self.battery_level,
                'height': self.drone.get_height(),
                'flying': self.drone.is_flying,
                'patrol_mode': self.patrol_mode,
                'temperature': self.drone.get_temperature(),
                'flight_time': self.drone.get_flight_time()
            }
        except Exception as e:
            logger.error(f"Error getting status: {e}")
            return {'error': str(e)}