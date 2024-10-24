import threading
from typing import Optional
import logging
import time

logger = logging.getLogger(__name__)

class ControlThread:
    def __init__(self):
        self.control_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self.running = False
        self.current_command = None
        # Default distances and speeds
        self.movement_distance = 30  # cm
        self.rotation_angle = 90    # degrees
        self.default_speed = 50     # percentage

    def handle_command(self, drone_manager, command, distance=None):
        """Execute the given command on the drone with improved control."""
        try:
            drone = drone_manager.get_drone()
            if not drone:
                raise Exception("Drone not available")

            # Set default speed for better control
            drone.set_speed(self.default_speed)
            
            if command == 'takeoff':
                drone.takeoff()
                time.sleep(2)  # Give time to stabilize
                drone.send_rc_control(0, 0, 0, 0)  # Stop all movement
                
            elif command == 'land':
                drone.land()
                
            elif command == 'move_forward':
                drone.send_rc_control(0, self.movement_distance, 0, 0)
                time.sleep(0.5)
                drone.send_rc_control(0, 0, 0, 0)
                
            elif command == 'move_back':
                drone.send_rc_control(0, -self.movement_distance, 0, 0)
                time.sleep(0.5)
                drone.send_rc_control(0, 0, 0, 0)
                
            elif command == 'move_left':
                drone.send_rc_control(-self.movement_distance, 0, 0, 0)
                time.sleep(0.5)
                drone.send_rc_control(0, 0, 0, 0)
                
            elif command == 'move_right':
                drone.send_rc_control(self.movement_distance, 0, 0, 0)
                time.sleep(0.5)
                drone.send_rc_control(0, 0, 0, 0)
                
            elif command == 'move_up':
                drone.send_rc_control(0, 0, self.movement_distance, 0)
                time.sleep(0.5)
                drone.send_rc_control(0, 0, 0, 0)
                
            elif command == 'move_down':
                drone.send_rc_control(0, 0, -self.movement_distance, 0)
                time.sleep(0.5)
                drone.send_rc_control(0, 0, 0, 0)
                
            elif command == 'rotate_clockwise':
                drone.send_rc_control(0, 0, 0, self.rotation_angle)
                time.sleep(0.5)
                drone.send_rc_control(0, 0, 0, 0)
                
            elif command == 'rotate_counter_clockwise':
                drone.send_rc_control(0, 0, 0, -self.rotation_angle)
                time.sleep(0.5)
                drone.send_rc_control(0, 0, 0, 0)
                
            elif command == 'emergency':
                drone.emergency()
            
            else:
                logger.error(f"Unknown command: {command}")
                
        except Exception as e:
            logger.error(f"Error executing command {command}: {str(e)}")
            # In case of error, try to stabilize the drone
            try:
                drone.send_rc_control(0, 0, 0, 0)
            except:
                pass

    def start(self, drone_manager, command, distance=None):
        """Start control thread for handling drone commands."""
        if self.is_running():
            logger.info("Control thread already running")
            return
        
        logger.info(f"Starting control thread for command: {command}")
        self.current_command = command
        self.running = True
        
        self.control_thread = threading.Thread(
            target=self._execute_command, 
            args=(drone_manager, command, distance),
            daemon=True
        )
        self.control_thread.start()

    def _execute_command(self, drone_manager, command, distance):
        """Internal method to execute command and handle cleanup."""
        try:
            self.handle_command(drone_manager, command, distance)
        finally:
            with self._lock:
                self.running = False
                self.current_command = None

    def is_running(self) -> bool:
        """Thread-safe check of control thread status."""
        with self._lock:
            return self.running

    def stop(self):
        """Stop any ongoing command and reset the drone."""
        with self._lock:
            self.running = False
        
        if self.control_thread and self.control_thread.is_alive():
            self.control_thread.join(timeout=1.0)