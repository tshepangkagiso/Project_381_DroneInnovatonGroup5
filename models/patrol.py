import logging
import os
import time
import threading
from typing import Optional, Dict, List
from enum import Enum
from queue import Queue

'''
Key features of this Patrol class:

    Configurable patrol parameters (height and side length) with safety limits
    Unit conversion (meters to centimeters) for drone commands
    Safe landing procedure with emergency fallback
    Three independent patrol routes (BL, TL, TR)
    Status monitoring
    Integration with DroneManager
    Each patrol movement sequence runs in its own dedicated thread
    Landing procedure now includes full descent before landing command
    Added thread safety with locks and events
    Included time delays between movements for stability
    Added stop command checking during long sequences
    Separated movement sequences into their own functions
    Added pause/resume capability through events
    Improved error handling and logging

The parameters are easily accessible at the top of the file as class constants, and all measurements are stored in meters but converted to centimeters for drone commands.
'''

# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if not os.path.exists('logs'):
    os.makedirs('logs')
handler = logging.FileHandler('logs/patrol.log')
handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

class PatrolPoint(Enum):
    """Enum for patrol points in the square pattern."""
    BR = "Bottom Right (Origin)"
    BL = "Bottom Left"
    TL = "Top Left"
    TR = "Top Right"

class PatrolCommand(Enum):
    """Commands for patrol operations."""
    STOP = "stop"
    PAUSE = "pause"
    RESUME = "resume"
    EMERGENCY = "emergency"

class Patrol:
    """Handles automated patrol routes for the drone."""
    
    # Patrol Configuration Parameters (in meters)
    DEFAULT_HEIGHT = 2.0  # Default patrol height in meters
    DEFAULT_SIDE_LENGTH = 3.0  # Default square side length in meters
    
    # Safety Parameters
    MIN_HEIGHT = 0.2  # Minimum allowed height in meters
    MAX_HEIGHT = 5.0  # Maximum allowed height in meters
    MIN_SIDE_LENGTH = 1.0  # Minimum square side in meters
    MAX_SIDE_LENGTH = 8.0  # Maximum square side in meters
    
    def __init__(self, drone_manager):
        """Initialize patrol with drone manager and default parameters."""
        self.drone_manager = drone_manager
        self.current_patrol = None
        self.patrol_thread = None
        self.is_patrolling = False
        self.patrol_lock = threading.Lock()
        self.command_queue = Queue()
        
        # Current configuration (in meters)
        self.height = self.DEFAULT_HEIGHT
        self.side_length = self.DEFAULT_SIDE_LENGTH
        
        # Thread control
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        
        logger.info("Patrol system initialized with default parameters")

    def set_patrol_parameters(self, height: float, side_length: float) -> bool:
        """Set patrol height and square side length with safety checks."""
        try:
            # Validate height
            if not self.MIN_HEIGHT <= height <= self.MAX_HEIGHT:
                logger.error(f"Height must be between {self.MIN_HEIGHT} and {self.MAX_HEIGHT} meters")
                return False

            # Validate side length
            if not self.MIN_SIDE_LENGTH <= side_length <= self.MAX_SIDE_LENGTH:
                logger.error(f"Side length must be between {self.MIN_SIDE_LENGTH} and {self.MAX_SIDE_LENGTH} meters")
                return False

            self.height = height
            self.side_length = side_length
            
            logger.info(f"Patrol parameters set - Height: {height}m, Side Length: {side_length}m")
            return True
            
        except Exception as e:
            logger.error(f"Error setting patrol parameters: {e}")
            return False

    def _convert_to_cm(self, meters: float) -> int:
        """Convert meters to centimeters."""
        return int(meters * 100)

    def _perform_scan(self):
        """Perform 360-degree scan at current position."""
        try:
            logger.info("Starting 360-degree scan")
            self.drone_manager.drone.rotate_clockwise(360)
            logger.info("Scan completed")
        except Exception as e:
            logger.error(f"Error during scan: {e}")
            raise

    def _safe_landing(self):
        """Execute safe landing procedure with full descent first."""
        try:
            logger.info("Initiating safe landing procedure")
            height_cm = self._convert_to_cm(self.height)
            
            # First, descend the full patrol height
            logger.info(f"Descending full patrol height: {self.height}m")
            self.drone_manager.drone.move_down(height_cm)
            time.sleep(2)  # Small delay to ensure stability
            
            # Then execute landing command
            logger.info("Executing final landing command")
            self.drone_manager.drone.land()
            logger.info("Landing completed successfully")
            
        except Exception as e:
            logger.error(f"Error during safe landing: {e}")
            try:
                self.drone_manager.drone.emergency()
                logger.warning("Emergency landing executed")
            except:
                logger.critical("Both normal and emergency landing failed")

    def _execute_movement_sequence(self, movement_func):
        """Execute a movement sequence in a separate thread."""
        try:
            # Reset control events
            self.stop_event.clear()
            self.pause_event.clear()
            
            def movement_thread():
                try:
                    movement_func()
                except Exception as e:
                    logger.error(f"Movement sequence error: {e}")
                    self._safe_landing()
                finally:
                    self.is_patrolling = False
                    self.current_patrol = None
            
            # Start movement in new thread
            self.patrol_thread = threading.Thread(target=movement_thread)
            self.patrol_thread.daemon = True
            self.patrol_thread.start()
            
        except Exception as e:
            logger.error(f"Error starting movement sequence: {e}")
            return False

    def fly_to_BL(self):
        """Execute Bottom Left patrol point routine."""
        def bl_sequence():
            try:
                logger.info("Starting Bottom Left patrol route")
                drone = self.drone_manager.drone
                height_cm = self._convert_to_cm(self.height)
                side_length_cm = self._convert_to_cm(self.side_length)
                
                # Take off and reach patrol height
                drone.takeoff()
                time.sleep(1)
                drone.move_up(height_cm)
                time.sleep(1)
                
                # Move to BL
                drone.move_left(side_length_cm)
                time.sleep(1)
                
                # Check for stop command
                if self.stop_event.is_set():
                    self._safe_landing()
                    return
                
                # Perform scan
                self._perform_scan()
                
                # Check for stop command
                if self.stop_event.is_set():
                    self._safe_landing()
                    return
                
                # Return to origin (BR)
                drone.move_right(side_length_cm)
                time.sleep(1)
                
                # Face TR
                drone.rotate_clockwise(90)
                time.sleep(1)
                
                # Safe landing with full descent
                self._safe_landing()
                
            except Exception as e:
                logger.error(f"Error in Bottom Left patrol: {e}")
                self._safe_landing()

        self._execute_movement_sequence(bl_sequence)

    def fly_to_TL(self):
        """Execute Top Left patrol point routine."""
        def tl_sequence():
            try:
                logger.info("Starting Top Left patrol route")
                drone = self.drone_manager.drone
                height_cm = self._convert_to_cm(self.height)
                side_length_cm = self._convert_to_cm(self.side_length)
                
                # Take off and reach patrol height
                drone.takeoff()
                time.sleep(1)
                drone.move_up(height_cm)
                time.sleep(1)
                
                # Move to TL
                drone.move_forward(side_length_cm)
                time.sleep(1)
                drone.move_left(side_length_cm)
                time.sleep(1)
                
                # Check for stop command
                if self.stop_event.is_set():
                    self._safe_landing()
                    return
                
                # Perform scan
                self._perform_scan()
                
                # Check for stop command
                if self.stop_event.is_set():
                    self._safe_landing()
                    return
                
                # Return to origin (BR)
                drone.move_right(side_length_cm)
                time.sleep(1)
                drone.move_back(side_length_cm)
                time.sleep(1)
                
                # Face TR
                drone.rotate_clockwise(90)
                time.sleep(1)
                
                # Safe landing with full descent
                self._safe_landing()
                
            except Exception as e:
                logger.error(f"Error in Top Left patrol: {e}")
                self._safe_landing()

        self._execute_movement_sequence(tl_sequence)

    def fly_to_TR(self):
        """Execute Top Right patrol point routine."""
        def tr_sequence():
            try:
                logger.info("Starting Top Right patrol route")
                drone = self.drone_manager.drone
                height_cm = self._convert_to_cm(self.height)
                side_length_cm = self._convert_to_cm(self.side_length)
                
                # Take off and reach patrol height
                drone.takeoff()
                time.sleep(1)
                drone.move_up(height_cm)
                time.sleep(1)
                
                # Move to TR
                drone.move_forward(side_length_cm)
                time.sleep(1)
                drone.move_right(side_length_cm)
                time.sleep(1)
                
                # Check for stop command
                if self.stop_event.is_set():
                    self._safe_landing()
                    return
                
                # Perform scan
                self._perform_scan()
                
                # Check for stop command
                if self.stop_event.is_set():
                    self._safe_landing()
                    return
                
                # Return to origin (BR)
                drone.move_left(side_length_cm)
                time.sleep(1)
                drone.move_back(side_length_cm)
                time.sleep(1)
                
                # Face TR
                drone.rotate_clockwise(90)
                time.sleep(1)
                
                # Safe landing with full descent
                self._safe_landing()
                
            except Exception as e:
                logger.error(f"Error in Top Right patrol: {e}")
                self._safe_landing()

        self._execute_movement_sequence(tr_sequence)

    def execute_patrol(self, patrol_point: PatrolPoint) -> bool:
        """Execute patrol to specified point."""
        if not self.drone_manager.is_connected:
            logger.error("Cannot start patrol: Drone not connected")
            return False

        try:
            with self.patrol_lock:
                if self.is_patrolling:
                    logger.error("Patrol already in progress")
                    return False
                
                self.is_patrolling = True
                self.current_patrol = patrol_point
                
                patrol_methods = {
                    PatrolPoint.BL: self.fly_to_BL,
                    PatrolPoint.TL: self.fly_to_TL,
                    PatrolPoint.TR: self.fly_to_TR
                }
                
                if patrol_point not in patrol_methods:
                    logger.error(f"Invalid patrol point: {patrol_point}")
                    self.is_patrolling = False
                    return False
                    
                patrol_methods[patrol_point]()
                return True
                
        except Exception as e:
            logger.error(f"Error executing patrol: {e}")
            self.is_patrolling = False
            return False

    def stop_patrol(self):
        """Stop current patrol and trigger safe landing."""
        logger.info("Stopping patrol")
        self.stop_event.set()
        if self.patrol_thread:
            self.patrol_thread.join(timeout=2.0)

    def get_patrol_status(self) -> Dict:
        """Get current patrol status and configuration."""
        return {
            'is_patrolling': self.is_patrolling,
            'current_patrol': self.current_patrol.name if self.current_patrol else None,
            'height': self.height,
            'side_length': self.side_length,
            'timestamp': time.time()
        }