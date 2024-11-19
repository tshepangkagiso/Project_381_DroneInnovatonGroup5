import threading
import time
import logging
import os
from enum import Enum
from dataclasses import dataclass
from djitellopy import Tello
from typing import Optional, Dict, List, Tuple
import numpy as np
import asyncio
from .video_streamer import VideoStreamer

# Configure logging
logger = logging.getLogger(__name__)
keepalive_logger = logging.getLogger('keepalive')
performance_logger = logging.getLogger('performance')

class PatrolStatus(Enum):
    IDLE = "idle"
    TAKEOFF = "takeoff" 
    PATROLLING = "patrolling"
    LANDING = "landing"
    EMERGENCY = "emergency"
    ERROR = "error"
    MANUAL = "manual"

class PatrolConfig:
    # Measurements
    PATROL_SIZE = 2  # 2 meters = 200cm
    SIDE_LENGTH = 200  
    HEIGHT = 150      
    MANUAL_MOVEMENT = 30 
    ROTATION_MOVEMENT = 90
    
    # Speed settings (cm/s)
    DEFAULT_SPEED = 30
    MAX_SPEED = 100
    MIN_SPEED = 25
    
    # Safety settings
    MIN_BATTERY = 20
    STABILIZATION_TIME = 0.5
    MAX_CONSECUTIVE_ERRORS = 10
    EMERGENCY_LAND_HEIGHT = 20
    CONNECTION_TIMEOUT = 3
    MAX_RETRIES = 10

@dataclass
class PatrolMetrics:
    """Track metrics for each patrol sequence."""
    threats_detected: Dict[str, int] = None
    start_time: float = 0.0
    end_time: float = 0.0
    battery_used: int = 0
    path_type: str = ""
    
    def __post_init__(self):
        self.threats_detected = {"high": 0, "medium": 0, "low": 0}

class DroneManager:
    class PatrolController:
        """Integrated patrol control and validation."""
        def __init__(self, drone_manager):
            self.drone_manager = drone_manager
            self.config = PatrolConfig
            self.status = PatrolStatus.IDLE
            self.is_patrolling = False
            self._patrol_lock = threading.Lock()
            self.stop_requested = threading.Event()
            
            self.current_speed = self.config.DEFAULT_SPEED
            self.current_metrics = PatrolMetrics()
            self.error_count = 0
            self.active_movement = False
            self.current_position = "bottom_right"

        def _validate_conditions(self) -> bool:
            """Validate patrol conditions."""
            try:
                if not self.drone_manager.is_connected:
                    logger.error("Drone not connected")
                    return False
                    
                if self.drone_manager.battery_level < self.config.MIN_BATTERY:
                    logger.error(f"Battery too low: {self.drone_manager.battery_level}%")
                    return False
                    
                if self.status == PatrolStatus.ERROR:
                    logger.error("Drone in error state")
                    return False

                if self.active_movement:
                    logger.error("Movement already in progress")
                    return False

                if self.error_count >= self.config.MAX_CONSECUTIVE_ERRORS:
                    logger.error("Too many consecutive errors")
                    return False
                    
                return True
            except Exception as e:
                logger.error(f"Validation error: {e}")
                return False

        async def start_patrol_metrics(self, path_type: str) -> None:
            """Initialize metrics for patrol."""
            self.current_metrics = PatrolMetrics(path_type=path_type)
            self.current_metrics.start_time = time.time()
            self.current_metrics.battery_used = self.drone_manager.battery_level

        async def end_patrol_metrics(self) -> None:
            """Finalize metrics for patrol."""
            self.current_metrics.end_time = time.time()
            self.current_metrics.battery_used -= self.drone_manager.battery_level

        def get_patrol_metrics(self) -> Dict:
            """Get current patrol metrics."""
            return {
                "path_type": self.current_metrics.path_type,
                "duration": self.current_metrics.end_time - self.current_metrics.start_time,
                "battery_used": self.current_metrics.battery_used,
                "threats_detected": self.current_metrics.threats_detected
            }

        def get_status(self) -> Dict:
            """Get current patrol status."""
            return {
                "status": self.status.value,
                "is_patrolling": self.is_patrolling,
                "current_position": self.current_position,
                "battery_level": self.drone_manager.battery_level,
                "speed": self.current_speed,
                "error_count": self.error_count,
                "active_movement": self.active_movement
            }

        def cleanup(self) -> None:
            """Cleanup patrol resources."""
            self.stop_requested.set()
            self.status = PatrolStatus.IDLE
            self.is_patrolling = False
            self.active_movement = False

    def __init__(self, socketio):
        """Initialize drone manager with integrated patrol control."""
        try:
            # Core components
            self.socketio = socketio
            self.drone: Optional[Tello] = None
            self.video_streamer = VideoStreamer(socketio)
            
            # Integrated patrol controller
            self.patrol = self.PatrolController(self)
            
            # State management
            self.is_connected = False
            self.is_flying = False
            self.battery_level = 0
            self.last_command_time = 0
            self.command_cooldown = 0.1
            
            # Threading
            self.connection_lock = threading.Lock()
            self.command_lock = threading.Lock()
            self.keep_alive_thread = None
            self.keep_alive_event = threading.Event()
            
            # Performance monitoring
            self._init_metrics()
            
            logger.info("Drone Manager initialized")
            
        except Exception as e:
            logger.error(f"DroneManager initialization failed: {e}")
            raise

    def _init_metrics(self) -> None:
        """Initialize performance metrics."""
        self.metrics = {
            'commands_sent': 0,
            'commands_failed': 0,
            'avg_response_time': 0,
            'response_times': [],
            'max_response_time': 0,
            'connection_drops': 0,
            'battery_readings': []
        }

    def _validate_wifi_connection(self) -> bool:
        """Validate WiFi connection to drone."""
        try:
            # Check if we can reach drone's IP
            response = os.system("ping -n 1 192.168.10.1")
            if response == 0:
                logger.info("WiFi connection to drone verified")
                return True
            else:
                logger.error("Cannot reach drone IP (192.168.10.1)")
                return False
        except Exception as e:
            logger.error(f"WiFi validation error: {e}")
            return False

    def connect_drone(self) -> bool:
        """Establish optimized connection with drone."""
        try:
            with self.connection_lock:
                if self.is_connected:
                    return True

                if not self._validate_wifi_connection():
                    logger.error("WiFi connection validation failed")
                    return False

                logger.info("Connecting to drone...")
                
                # Initialize drone with optimized settings
                self.drone = Tello()
                self.drone.RESPONSE_TIMEOUT = PatrolConfig.CONNECTION_TIMEOUT
                self.drone.RETRY_COUNT = PatrolConfig.MAX_RETRIES
                
                # Test connection first
                try:
                    logger.info("Testing initial connection...")
                    self.drone.connect()
                    self.drone.set_speed(PatrolConfig.DEFAULT_SPEED)
                    time.sleep(0.5)
                    
                    # Verify connection with battery check
                    try:
                        self.battery_level = self.drone.get_battery()
                        logger.info(f"Initial connection successful. Battery: {self.battery_level}%")
                    except Exception:
                        logger.error("Failed to get battery level")
                        return False
                        
                    # Configure initial speed
                    '''retry_count = 0
                    while retry_count < 3:
                        try:
                            self.drone.set_speed(PatrolConfig.DEFAULT_SPEED)
                            break
                        except Exception:
                            retry_count += 1
                            if retry_count == 10:
                                logger.error("Failed to set initial speed")
                                return False
                            time.sleep(0.5)'''
                    
                    self.is_connected = True
                    self._start_keep_alive()
                    
                    logger.info("Drone connected successfully")
                    
                    # Initialize video stream
                    '''if not self.video_streamer.start_streaming(self.drone):
                        logger.warning("Failed to start video stream")'''
                        
                    return True
                    
                except Exception as e:
                    logger.error(f"Connection failed: {e}")
                    self.cleanup()
                    return False
                
        except Exception as e:
            logger.error(f"Connection error: {e}")
            self.cleanup()
            return False

    def _start_keep_alive(self) -> None:
        """Start optimized keep-alive monitoring."""
        try:
            def keep_alive_loop():
                failed_pings = 0
                max_failed_pings = 10
                ping_interval = 2.0
                battery_check_interval = 30.0
                last_battery_check = time.time()
                
                while not self.keep_alive_event.is_set():
                    try:
                        current_time = time.time()
                        
                        if current_time - last_battery_check >= battery_check_interval:
                            self.battery_level = self.drone.get_battery()
                            self.metrics['battery_readings'].append(self.battery_level)
                            
                            self.socketio.emit('battery_update', {
                                'battery': self.battery_level,
                                'timestamp': current_time
                            })
                            
                            keepalive_logger.debug(f"Battery Level: {self.battery_level}%")
                            last_battery_check = current_time
                            failed_pings = 0
                        else:
                            self.drone.get_height()
                        
                        failed_pings = 0
                        time.sleep(ping_interval)
                        
                    except Exception as e:
                        failed_pings += 1
                        logger.warning(f"Keep-alive ping failed: {failed_pings}/{max_failed_pings}")
                        
                        if failed_pings >= max_failed_pings:
                            logger.error("Lost connection to drone")
                            self.metrics['connection_drops'] += 1
                            
                            self.socketio.emit('connection_lost', {
                                'timestamp': time.time(),
                                'reason': 'Connection timeout'
                            })
                            
                            if not self._recover_connection():
                                break
                        
                        time.sleep(1)

            self.keep_alive_event.clear()
            self.keep_alive_thread = threading.Thread(
                target=keep_alive_loop,
                daemon=True
            )
            self.keep_alive_thread.start()
            
        except Exception as e:
            logger.error(f"Failed to start keep-alive: {e}")

    def _recover_connection(self) -> bool:
        """Attempt to recover lost connection."""
        try:
            logger.info("Attempting connection recovery...")
            self.cleanup()
            time.sleep(2)
            return self.connect_drone()
            
        except Exception as e:
            logger.error(f"Connection recovery failed: {e}")
            return False

    async def execute_movement(self, movement_func, *args) -> bool:
        """Execute movement with patrol validation."""
        if not self.patrol._validate_conditions():
            return False
            
        try:
            self.patrol.status = PatrolStatus.MANUAL
            self.patrol.active_movement = True
            
            result = await movement_func(*args)
            await asyncio.sleep(PatrolConfig.STABILIZATION_TIME)
            
            return result
        except Exception as e:
            logger.error(f"Movement error: {e}")
            self.patrol.error_count += 1
            return False
        finally:
            self.patrol.active_movement = False
            self.patrol.status = PatrolStatus.IDLE

    async def execute_pattern(self, pattern_func, pattern_name: str) -> bool:
        """Execute flight pattern with patrol management."""
        if not self.patrol._validate_conditions():
            return False
            
        try:
            await self.patrol.start_patrol_metrics(pattern_name)
            self.patrol.status = PatrolStatus.PATROLLING
            self.patrol.is_patrolling = True
            
            result = await pattern_func()
            
            return result
        except Exception as e:
            logger.error(f"Pattern error: {e}")
            await self.emergency_stop()
            return False
        finally:
            self.patrol.is_patrolling = False
            self.patrol.status = PatrolStatus.IDLE
            await self.patrol.end_patrol_metrics()

    # Basic Movement Commands
    def take_off(self) -> bool:
        """Execute takeoff with validation."""
        return self.execute_movement(self._takeoff_sequence)

    def _takeoff_sequence(self) -> bool:
        try:
            self.patrol.status = PatrolStatus.TAKEOFF
            self.drone.takeoff()
            self.is_flying = True
            logger.info("Takeoff successful")
            return True
        except Exception as e:
            logger.error(f"Takeoff error: {e}")
            return False

    def land(self) -> bool:
        """Execute landing with safety measures."""
        return self.execute_movement(self._landing_sequence)

    def _landing_sequence(self) -> bool:
        try:
            self.patrol.status = PatrolStatus.LANDING
            current_height = self.drone.get_height()
            
            if current_height > PatrolConfig.EMERGENCY_LAND_HEIGHT:
                self.drone.move_down(current_height - PatrolConfig.EMERGENCY_LAND_HEIGHT)
                time.sleep(0.5)

            self.drone.move_down(100) 
            self.drone.land()
            self.is_flying = False
            logger.info("Landing successful")
            return True
        except Exception as e:
            logger.error(f"Landing error: {e}")
            self.emergency_stop()
            return False

    async def emergency_stop(self) -> None:
        """Emergency stop procedure."""
        try:
            self.patrol.status = PatrolStatus.EMERGENCY
            await self.drone.emergency()
            self.is_flying = False
            logger.warning("Emergency stop executed")
        except Exception as e:
            logger.error(f"Emergency stop error: {e}")

    # Manual Movement Commands
    async def move_forward(self) -> bool:
        """Forward movement."""
        return await self.execute_movement(
            self.drone.move_forward,
            PatrolConfig.MANUAL_MOVEMENT
        )

    async def move_back(self) -> bool:
        """Backward movement."""
        return await self.execute_movement(
            self.drone.move_back,
            PatrolConfig.MANUAL_MOVEMENT
        )

    async def move_left(self) -> bool:
        """Left movement."""
        return await self.execute_movement(
            self.drone.move_left,
            PatrolConfig.MANUAL_MOVEMENT
        )

    async def move_right(self) -> bool:
        """Right movement."""
        return await self.execute_movement(
            self.drone.move_right,
            PatrolConfig.MANUAL_MOVEMENT
        )

    async def move_up(self) -> bool:
        """Upward movement."""
        return await self.execute_movement(
            self.drone.move_up,
            PatrolConfig.MANUAL_MOVEMENT
        )

    async def move_down(self) -> bool:
        """Downward movement."""
        return await self.execute_movement(
            self.drone.move_down,
            PatrolConfig.MANUAL_MOVEMENT
        )

    async def rotate_clockwise(self) -> bool:
        """Clockwise rotation."""
        return await self.execute_movement(
            self.drone.rotate_clockwise,
            PatrolConfig.ROTATION_MOVEMENT
        )

    async def rotate_counter_clockwise(self) -> bool:
        """Counter-clockwise rotation."""
        return await self.execute_movement(
            self.drone.rotate_counter_clockwise,
            PatrolConfig.ROTATION_MOVEMENT
        )

    # Pattern Flight Commands
    def perimeter(self) -> bool:
        """Execute perimeter patrol pattern."""
        return self.execute_pattern(
            self._perimeter_sequence,
            "perimeter"
        )

    def _perimeter_sequence(self) -> bool:
        """Internal perimeter sequence implementation."""
        try:
            tello = self.drone
            tello.set_speed(60)

            tello.takeoff()
            
            print("Drone took off")
            time.sleep(0.5)
        
            tello.move_up(150)  # Adjust for initial takeoff height
            print(f"Drone moved up to {150} cm")
            time.sleep(0.5)

            tello.move_forward(400)
            print(f"Drone moved forward to {400} cm")
            time.sleep(0.5)

            tello.rotate_clockwise(360)
            print("Drone completed 360-degree scan")
            time.sleep(0.5)

            tello.rotate_counter_clockwise(90)
            print("Drone completed 270-degree scan face tl")
            time.sleep(0.5)

            tello.move_forward(400)
            print(f"Drone moved forward to {400} cm")
            time.sleep(0.5)

            tello.rotate_clockwise(360)
            print("Drone completed 360-degree scan")
            time.sleep(0.5)

            tello.rotate_counter_clockwise(90)
            print("Drone completed 270-degree scan face bl")
            time.sleep(0.5)

            tello.move_forward(400)
            print(f"Drone moved forward to {400} cm")
            time.sleep(0.5)

            tello.rotate_clockwise(360)
            print("Drone completed 360-degree scan")
            time.sleep(0.5)

            tello.rotate_counter_clockwise(90)
            print("Drone completed 270-degree scan face br origin")
            time.sleep(0.5)

            tello.move_forward(400)
            print(f"Drone moved forward to {400} cm")
            time.sleep(0.5)

            tello.rotate_clockwise(360)
            print("Drone completed 360-degree scan")
            time.sleep(0.5)

            tello.rotate_counter_clockwise(90)
            print("Drone completed 270-degree scan face tr")
            time.sleep(0.5)

            # Move down slowly to ensure a controlled landing close to the takeoff position
            tello.move_down(150)
            print("Drone moved down to prepare for landing")
        
            # Land the drone
            tello.land()
            logger.info("Perimeter patrol completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Perimeter sequence error: {e}")
            return False

    def fly_to_TopRight(self) -> bool:
        """Execute TopRight flight pattern."""
        return self.execute_pattern(
            self._top_right_sequence,
            "top_right"
        )

    def _top_right_sequence(self) -> bool:
        """Internal TopRight sequence implementation."""
        try:
            tello = self.drone
            tello.set_speed(45)
            # Takeoff and reach the desired height
            tello.takeoff()
            print("Drone took off")
            time.sleep(1)
        
            tello.move_up(150)  # Adjust for initial takeoff height
            print(f"Drone moved up to {150} cm")
            time.sleep(1)

            tello.move_forward(200)
            print(f"Drone moved forward to {200} cm")
            time.sleep(1)

            tello.rotate_clockwise(360)
            print("Drone completed 360-degree scan")
            time.sleep(1)

            tello.move_back(200)
            print("Drone move to origin")
            time.sleep(1)

            # Move down slowly to ensure a controlled landing close to the takeoff position
            tello.move_down(100)
            print("Drone moved down to prepare for landing")
        
            # Land the drone
            tello.land()
            print("Drone landed")
            logger.info("TopRight flight completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"TopRight sequence error: {e}")
            return False

    def fly_to_TopLeft(self) -> bool:
        """Execute TopLeft flight pattern."""
        return self.execute_pattern(
            self._top_left_sequence,
            "top_left"
        )

    def _top_left_sequence(self) -> bool:
        """Internal TopLeft sequence implementation."""
        try:
            tello = self.drone
            tello.set_speed(45)
            tello.takeoff()
            print("Drone took off")
            time.sleep(1)

            tello.move_up(150)  # Adjust for initial takeoff height
            print(f"Drone moved up to {150} cm")
            time.sleep(1)

            tello.rotate_clockwise(270)
            time.sleep(0.5)

            tello.move_forward(200)
            time.sleep(0.5)

            tello.rotate_clockwise(270)
            time.sleep(0.5)

            tello.move_forward(200)
            time.sleep(0.5)

            tello.move_back(200)
            time.sleep(0.5)

            tello.rotate_clockwise(90)
            time.sleep(0.5)

            tello.move_forward(200)
            time.sleep(0.5)

            tello.rotate_counter_clockwise(90)
            time.sleep(0.5)

            # Move down slowly to ensure a controlled landing close to the takeoff position
            tello.move_down(100)
            print("Drone moved down to prepare for landing")
        
            # Land the drone
            tello.land()
            print("Drone landed")
            logger.info("TopLeft flight completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"TopLeft sequence error: {e}")
            return False

    def fly_to_BottomLeft(self) -> bool:
        """Execute BottomLeft flight pattern."""
        return self.execute_pattern(
            self._bottom_left_sequence,
            "bottom_left"
        )

    def _bottom_left_sequence(self) -> bool:
        """Internal BottomLeft sequence implementation."""
        try:
            tello = self.drone
            tello.set_speed(45)
            # Takeoff and reach the desired height
            tello.takeoff()
            print("Drone took off")
            time.sleep(0.5)

            tello.move_up(150)  # Adjust for initial takeoff height
            print(f"Drone moved up to {150} cm")
            time.sleep(0.5)

            tello.rotate_clockwise(270)
            time.sleep(0.5)

            tello.move_forward(200)
            time.sleep(0.5)

            tello.rotate_clockwise(180)
            time.sleep(0.5)

            tello.move_forward(200)
            time.sleep(0.5)

            tello.rotate_counter_clockwise(90)
            time.sleep(0.5)

            # Move down slowly to ensure a controlled landing close to the takeoff position
            tello.move_down(100)
            print("Drone moved down to prepare for landing")
        
            # Land the drone
            tello.land()
            print("Drone landed")
            logger.info("BottomLeft flight completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"BottomLeft sequence error: {e}")
            return False

    def get_status(self) -> Dict:
        """Get comprehensive drone status."""
        try:
            status = {
                'connected': self.is_connected,
                'flying': self.is_flying,
                'battery': self.battery_level,
                'streaming': self.video_streamer.is_streaming(),
                'metrics': {
                    'commands_sent': self.metrics['commands_sent'],
                    'commands_failed': self.metrics['commands_failed'],
                    'avg_response_time': self.metrics['avg_response_time'],
                    'connection_drops': self.metrics['connection_drops'],
                    'last_battery_readings': self.metrics['battery_readings'][-5:]
                },
                'patrol': self.patrol.get_status(),
                'patrol_metrics': self.patrol.get_patrol_metrics()
            }
            
            if self.video_streamer:
                status['video_metrics'] = self.video_streamer.get_status()
                
            return status
            
        except Exception as e:
            logger.error(f"Error getting status: {e}")
            return {
                'connected': False,
                'error': str(e)
            }

    def cleanup(self) -> None:
        """Enhanced cleanup procedure."""
        try:
            logger.info("Performing cleanup...")
            
            if self.keep_alive_thread:
                self.keep_alive_event.set()
                self.keep_alive_thread.join(timeout=2.0)
            
            if self.video_streamer:
                self.video_streamer.stop_streaming()
            
            if self.drone:
                try:
                    if self.is_flying:
                        asyncio.run(self.land())
                    if hasattr(self.drone, 'streamoff'):
                        self.drone.streamoff()
                    self.drone.end()
                except Exception as e:
                    logger.error(f"Error disconnecting drone: {e}")
            
            self.patrol.cleanup()
            
            self.is_connected = False
            self.is_flying = False
            self.drone = None
            
            logger.info("Cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
        finally:
            self.is_connected = False
            self.drone = None