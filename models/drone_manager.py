import threading
import time
import logging
from djitellopy import Tello
from .video_streamer import VideoStreamer
from typing import Optional, Dict, List, Tuple
import numpy as np

# Configure logging
logger = logging.getLogger(__name__)
keepalive_logger = logging.getLogger('keepalive')

class DroneManager:
    def __init__(self, socketio):
        """Initialize optimized drone manager."""
        try:
            # Core components
            self.socketio = socketio
            self.drone: Optional[Tello] = None
            self.video_streamer = VideoStreamer(socketio)
            self.patrol = None  # Will be set later to avoid circular import
            
            # State management
            self.is_connected = False
            self.is_flying = False
            self.battery_level = 0
            self.last_command_time = 0
            self.command_cooldown = 0.1  # 100ms minimum between commands
            
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

    def init_patrol(self):
        """Initialize patrol capability."""
        if not self.patrol:
            # Import PatrolDrone here to avoid circular import
            from .patrol_drone import PatrolDrone
            self.patrol = PatrolDrone(self)
    
    def get_position(self) -> tuple:
        """Get current position."""
        return (self.drone.get_x(), self.drone.get_y())
    
    def get_heading(self) -> float:
        """Get current heading."""
        return self.drone.get_yaw()

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
    
    def init_video_stream(self) -> bool:
        """Initialize video stream separately from connection."""
        try:
            if not self.is_connected:
                logger.error("Cannot initialize video: Drone not connected")
                return False

            logger.info("Initializing video stream...")
            if self.drone.streamon():
                time.sleep(1)  # Wait for stream initialization
                logger.info("Video stream initialized")
                return True
            return False

        except Exception as e:
            logger.error(f"Failed to initialize video stream: {e}")
            return False

    def connect_drone(self) -> bool:
        """Establish optimized connection with drone."""
        try:
            with self.connection_lock:
                if self.is_connected:
                    return True

                logger.info("Connecting to drone...")
                
                # Initialize drone
                self.drone = Tello()
                
                # Set UDP timeout lower for faster error detection
                self.drone.RESPONSE_TIMEOUT = 3
                
                # Connect with retry mechanism
                max_retries = 3
                retry_delay = 1.0
                
                for attempt in range(max_retries):
                    try:
                        self.drone.connect()
                        time.sleep(0.5)  # Short wait for stability
                        
                        # Test connection
                        self.battery_level = self.drone.get_battery()
                        logger.info(f"Battery level: {self.battery_level}%")
                        
                        self.is_connected = True
                        self._start_keep_alive()
                        
                        logger.info("Drone connected successfully")
                        return True
                        
                    except Exception as e:
                        logger.warning(f"Connection attempt {attempt + 1} failed: {e}")
                        if attempt < max_retries - 1:
                            time.sleep(retry_delay)
                            retry_delay *= 1.5  # Exponential backoff
                        continue

                logger.error("Failed to connect after maximum retries")
                self.cleanup()
                return False
                
        except Exception as e:
            logger.error(f"Failed to connect to drone: {e}")
            self.cleanup()
            return False

    def _start_keep_alive(self) -> None:
        """Start optimized keep-alive monitoring."""
        try:
            def keep_alive_loop():
                failed_pings = 0
                max_failed_pings = 3
                ping_interval = 2.0  # Seconds between pings
                battery_check_interval = 30.0  # Seconds between battery checks
                last_battery_check = time.time()
                
                while not self.keep_alive_event.is_set():
                    try:
                        current_time = time.time()
                        
                        # Battery check
                        if current_time - last_battery_check >= battery_check_interval:
                            self.battery_level = self.drone.get_battery()
                            self.metrics['battery_readings'].append(self.battery_level)
                            
                            # Emit battery update
                            self.socketio.emit('battery_update', {
                                'battery': self.battery_level,
                                'timestamp': current_time
                            })
                            
                            # Log battery status
                            keepalive_logger.debug(f"Battery Level: {self.battery_level}%")
                            last_battery_check = current_time
                            failed_pings = 0
                        
                        # Quick connection check
                        else:
                            self.drone.get_height()
                        
                        # Reset failed pings on success
                        failed_pings = 0
                        time.sleep(ping_interval)
                        
                    except Exception as e:
                        failed_pings += 1
                        logger.warning(f"Keep-alive ping failed: {failed_pings}/{max_failed_pings}")
                        
                        if failed_pings >= max_failed_pings:
                            logger.error("Lost connection to drone")
                            self.metrics['connection_drops'] += 1
                            
                            # Notify clients
                            self.socketio.emit('connection_lost', {
                                'timestamp': time.time(),
                                'reason': 'Connection timeout'
                            })
                            
                            # Try to recover connection
                            if not self._recover_connection():
                                break
                        
                        time.sleep(1)  # Short delay before retry

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
            
            # Try to reconnect
            self.cleanup()
            time.sleep(2)  # Wait before retry
            
            return self.connect_drone()
            
        except Exception as e:
            logger.error(f"Connection recovery failed: {e}")
            return False

    def send_command(self, command: str, *args) -> bool:
        """Send command with optimized error handling."""
        try:
            if not self.is_connected or not self.drone:
                logger.error("Cannot send command: Drone not connected")
                return False
                
            # Check command cooldown
            current_time = time.time()
            if current_time - self.last_command_time < self.command_cooldown:
                time.sleep(self.command_cooldown)
            
            with self.command_lock:
                start_time = time.time()
                
                try:
                    # Get command function
                    command_func = getattr(self.drone, command, None)
                    if not command_func or not callable(command_func):
                        logger.error(f"Invalid command: {command}")
                        return False
                    
                    # Execute command
                    result = command_func(*args)
                    
                    # Update metrics
                    self.metrics['commands_sent'] += 1
                    response_time = time.time() - start_time
                    self.metrics['response_times'].append(response_time)
                    self.metrics['avg_response_time'] = np.mean(self.metrics['response_times'])
                    self.metrics['max_response_time'] = max(self.metrics['max_response_time'], response_time)
                    
                    # Update last command time
                    self.last_command_time = time.time()
                    
                    logger.info(f"Command '{command}' executed successfully")
                    return True if result is None else result
                    
                except Exception as e:
                    self.metrics['commands_failed'] += 1
                    logger.error(f"Command '{command}' failed: {e}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error sending command: {e}")
            return False

    def take_off(self) -> bool:
        """Enhanced takeoff with safety checks."""
        try:
            if not self.is_connected:
                logger.error("Cannot take off: Drone not connected")
                return False
                
            if self.is_flying:
                logger.warning("Drone is already flying")
                return True
                
            # Safety checks
            if self.battery_level < 20:
                logger.error("Cannot take off: Battery too low")
                self.socketio.emit('message', {
                    'data': 'Cannot take off: Battery level too low',
                    'type': 'error'
                })
                return False
            
            # Execute takeoff
            if self.send_command('takeoff'):
                self.is_flying = True
                logger.info("Takeoff successful")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Takeoff failed: {e}")
            return False

    def land(self) -> bool:
        """Enhanced landing with safety measures."""
        try:
            if not self.is_connected:
                logger.error("Cannot land: Drone not connected")
                return False
                
            if not self.is_flying:
                logger.warning("Drone is already landed")
                return True
            
            # Execute landing
            if self.send_command('land'):
                self.is_flying = False
                logger.info("Landing successful")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Landing failed: {e}")
            self.emergency_stop()  # Emergency stop if landing fails
            return False

    def emergency_stop(self) -> None:
        """Enhanced emergency stop procedure."""
        try:
            logger.warning("Executing emergency stop!")
            
            if self.drone:
                try:
                    self.drone.emergency()
                except Exception as emergency_e:
                    logger.error(f"Emergency stop command failed: {emergency_e}")
                
                self.is_flying = False
                
                # Notify clients
                self.socketio.emit('emergency_stop', {
                    'timestamp': time.time(),
                    'status': 'completed'
                })
            
            # Force cleanup
            self.cleanup()
            
        except Exception as e:
            logger.error(f"Error during emergency stop: {e}")
            self.socketio.emit('emergency_stop', {
                'timestamp': time.time(),
                'status': 'failed',
                'error': str(e)
            })

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
                }
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
            
            # Stop keep-alive thread
            if self.keep_alive_thread:
                self.keep_alive_event.set()
                self.keep_alive_thread.join(timeout=2.0)
            
            # Stop video streaming
            if self.video_streamer:
                self.video_streamer.stop_streaming()
            
            # Disconnect drone
            if self.drone:
                try:
                    if self.is_flying:
                        self.land()
                    if hasattr(self.drone, 'streamoff'):
                        self.drone.streamoff()
                    self.drone.end()
                except Exception as e:
                    logger.error(f"Error disconnecting drone: {e}")
            
            # Reset state
            self.is_connected = False
            self.is_flying = False
            self.drone = None
            
            logger.info("Cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
        finally:
            self.is_connected = False
            self.drone = None

    def _get_movement_command(self, command: str) -> Optional[str]:
        """
        Map movement commands to drone API methods.
        
        Args:
            command: Command string
            
        Returns:
            Mapped command or None if invalid
        """
        movement_commands = {
            'up': 'move_up',
            'down': 'move_down',
            'left': 'move_left',
            'right': 'move_right',
            'forward': 'move_forward',
            'back': 'move_back',
            'clockwise': 'rotate_clockwise',
            'counter_clockwise': 'rotate_counter_clockwise'
        }
        return movement_commands.get(command)

    def move(self, direction: str, distance: int = 30) -> bool:
        """
        Execute drone movement with safety checks.
        
        Args:
            direction: Movement direction
            distance: Movement distance in cm
            
        Returns:
            bool: Success status
        """
        try:
            if not self.is_connected or not self.is_flying:
                logger.error(f"Cannot move {direction}: Drone not ready")
                return False
                
            # Get mapped command
            command = self._get_movement_command(direction)
            if not command:
                logger.error(f"Invalid movement command: {direction}")
                return False
                
            # Execute movement
            return self.send_command(command, distance)
            
        except Exception as e:
            logger.error(f"Movement error: {e}")
            return False
    
    def get_height(self) -> int:
        """Get current height in cm."""
        try:
            return self.drone.get_height()
        except Exception as e:
            logger.error(f"Height check error: {e}")
            return 0