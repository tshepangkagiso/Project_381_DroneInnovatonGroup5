import asyncio
import logging
import time
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass
from enum import Enum
import sys
import signal
import math
from datetime import datetime
import threading

# Configure logging
logger = logging.getLogger(__name__)
patrol_logger = logging.getLogger('patrol')
patrol_logger.setLevel(logging.INFO)

# Add file handler for patrol logs
patrol_handler = logging.FileHandler('patrol.log')
patrol_handler.setFormatter(
    logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
)
patrol_logger.addHandler(patrol_handler)

# Patrol Configuration Constants
class PatrolConfig:
    """Centralized patrol configuration."""
    # Patrol area dimensions in meters
    PATROL_SIZE = 1  # Change this value to adjust patrol area (1m, 2m, 3m, 4m)
    
    # Convert patrol size to centimeters and derive other measurements
    PERIMETER_WIDTH = PATROL_SIZE * 100  # Convert meters to centimeters
    PERIMETER_HEIGHT = PATROL_SIZE * 100
    TAKEOFF_HEIGHT = PATROL_SIZE * 100
    
    # Safety and performance settings
    SPEED = 15  # cm/s
    BUFFER = 15  # cm buffer from edges
    ROTATION_SPEED = 45  # degrees per second
    MIN_BATTERY = 20  # minimum battery percentage
    POSITION_TOLERANCE = 20  # cm tolerance for position verification
    
    # Timing constants
    TAKEOFF_STABILIZATION_TIME = 2  # seconds
    HEIGHT_STABILIZATION_TIME = 3
    CORNER_STABILIZATION_TIME = 1
    ROTATION_STABILIZATION_TIME = 2  # seconds after rotation
    LANDING_STABILIZATION_TIME = 2
    EMERGENCY_TIMEOUT = 5  # maximum seconds to wait for emergency procedures
    
    @classmethod
    def get_corners(cls) -> Dict[str, Tuple[int, int]]:
        """Calculate corner coordinates based on patrol size."""
        return {
            'bottom_right': (0, 0),
            'top_right': (0, cls.PERIMETER_HEIGHT - cls.BUFFER),
            'top_left': (cls.PERIMETER_WIDTH - cls.BUFFER, cls.PERIMETER_HEIGHT - cls.BUFFER),
            'bottom_left': (cls.PERIMETER_WIDTH - cls.BUFFER, 0)
        }
    
    @classmethod
    def get_corner_sequences(cls) -> Dict[str, List[str]]:
        """Define patrol sequences."""
        return {
            'clockwise': ['top_right', 'top_left', 'bottom_left', 'bottom_right'],
            'counterclockwise': ['bottom_left', 'top_left', 'top_right', 'bottom_right']
        }

class PatrolStatus(Enum):
    """Patrol drone status states."""
    IDLE = "idle"
    TAKEOFF = "takeoff"
    PATROLLING = "patrolling"
    LANDING = "landing"
    EMERGENCY = "emergency"
    ERROR = "error"

@dataclass
class PatrolMetrics:
    """Track patrol performance metrics."""
    start_time: float = 0.0
    end_time: float = 0.0
    distance_traveled: float = 0.0
    corners_visited: int = 0
    scans_completed: int = 0
    patrol_number: int = 0
    battery_start: int = 0
    battery_end: int = 0
    errors_encountered: int = 0
    stream_status: bool = False
    detection_count: int = 0
    patrol_type: str = ""
    completion_status: str = ""
    patrol_size: float = PatrolConfig.PATROL_SIZE  # Track patrol size used
    height_deviations: List[float] = None
    position_deviations: List[Tuple[float, float]] = None
    scan_durations: List[float] = None
    
    def __post_init__(self):
        """Initialize mutable defaults."""
        self.height_deviations = []
        self.position_deviations = []
        self.scan_durations = []

class PatrolDrone:
    """Manages automated drone patrol sequences."""
    
    def __init__(self, drone_manager):
        """Initialize patrol drone with configuration."""
        try:
            self.drone_manager = drone_manager
            self.video_streamer = drone_manager.video_streamer
            
            # Load configuration
            self.config = PatrolConfig
            self.CORNERS = self.config.get_corners()
            self.SEQUENCES = self.config.get_corner_sequences()
            
            # Flight status
            self.is_patrolling = False
            self.current_corner = 'bottom_right'
            self.status = PatrolStatus.IDLE
            self._patrol_lock = threading.Lock()
            
            # Performance tracking
            self.metrics = PatrolMetrics()
            self.patrol_history: List[PatrolMetrics] = []
            
            # Event flags
            self.stop_requested = threading.Event()
            
            patrol_logger.info(f"Patrol Drone initialized with {self.config.PATROL_SIZE}m patrol size")
            
        except Exception as e:
            patrol_logger.error(f"Failed to initialize Patrol Drone: {e}")
            raise

    def _start_metrics(self, patrol_type: str) -> None:
        """Initialize metrics for new patrol."""
        try:
            self.metrics = PatrolMetrics()
            self.metrics.start_time = time.time()
            self.metrics.battery_start = self.drone_manager.battery_level
            self.metrics.patrol_type = patrol_type
            self.metrics.patrol_number = len(self.patrol_history) + 1
            self.metrics.patrol_size = self.config.PATROL_SIZE
            
        except Exception as e:
            patrol_logger.error(f"Error initializing metrics: {e}")

    def _update_metrics(self, distance: float = 0.0) -> None:
        """Update patrol metrics."""
        try:
            self.metrics.distance_traveled += distance
            self.metrics.corners_visited += 1
            
            if self.video_streamer:
                self.metrics.stream_status = self.video_streamer.is_streaming()
                
        except Exception as e:
            patrol_logger.error(f"Error updating metrics: {e}")

    def _finalize_metrics(self, completion_status: str) -> None:
        """Finalize metrics for completed patrol."""
        try:
            self.metrics.end_time = time.time()
            self.metrics.battery_end = self.drone_manager.battery_level
            self.metrics.completion_status = completion_status
            
            # Calculate averages and summaries
            duration = self.metrics.end_time - self.metrics.start_time
            battery_used = self.metrics.battery_start - self.metrics.battery_end
            avg_height_deviation = sum(self.metrics.height_deviations) / len(self.metrics.height_deviations) if self.metrics.height_deviations else 0
            avg_scan_duration = sum(self.metrics.scan_durations) / len(self.metrics.scan_durations) if self.metrics.scan_durations else 0
            
            # Add to history
            self.patrol_history.append(self.metrics)
            
            # Log detailed summary
            patrol_logger.info(
                f"Patrol {self.metrics.patrol_number} completed:\n"
                f"Type: {self.metrics.patrol_type}\n"
                f"Size: {self.metrics.patrol_size}m\n"
                f"Duration: {duration:.1f}s\n"
                f"Distance: {self.metrics.distance_traveled}cm\n"
                f"Battery used: {battery_used}%\n"
                f"Corners visited: {self.metrics.corners_visited}\n"
                f"Scans completed: {self.metrics.scans_completed}\n"
                f"Avg height deviation: {avg_height_deviation:.1f}cm\n"
                f"Avg scan duration: {avg_scan_duration:.1f}s\n"
                f"Status: {completion_status}"
            )
            
        except Exception as e:
            patrol_logger.error(f"Error finalizing metrics: {e}")

    async def takeoff(self) -> bool:
        """Execute safe takeoff sequence."""
        try:
            patrol_logger.info("Initiating takeoff sequence")
            self.status = PatrolStatus.TAKEOFF
            
            # Safety checks
            if self.drone_manager.battery_level < self.config.MIN_BATTERY:
                raise Exception("Battery too low for takeoff")
                
            # Initial takeoff
            if not self.drone_manager.take_off():
                raise Exception("Takeoff failed")
            
            # Wait for stability
            await asyncio.sleep(self.config.TAKEOFF_STABILIZATION_TIME)
            
            # Rise to patrol height
            self.drone_manager.send_command('move_up', self.config.TAKEOFF_HEIGHT)
            await asyncio.sleep(self.config.HEIGHT_STABILIZATION_TIME)
            
            # Verify height and record deviation
            height = self.drone_manager.get_height()
            deviation = abs(height - self.config.TAKEOFF_HEIGHT)
            self.metrics.height_deviations.append(deviation)
            
            if deviation > self.config.POSITION_TOLERANCE:
                patrol_logger.warning(f"Height deviation detected: {height}cm vs {self.config.TAKEOFF_HEIGHT}cm")
                self.drone_manager.send_command('move_up', self.config.TAKEOFF_HEIGHT - height)
                await asyncio.sleep(self.config.HEIGHT_STABILIZATION_TIME)
            
            # Start streaming if not already active
            if not self.video_streamer.is_streaming():
                self.video_streamer.start_streaming(self.drone_manager.drone)
                await asyncio.sleep(1)
            
            patrol_logger.info(f"Takeoff complete at height {self.config.TAKEOFF_HEIGHT}cm")
            return True
            
        except Exception as e:
            patrol_logger.error(f"Takeoff error: {e}")
            self.status = PatrolStatus.ERROR
            await self.emergency()
            return False
        
    async def land(self) -> bool:
        """Execute safe landing sequence."""
        try:
            patrol_logger.info("Initiating landing sequence")
            self.status = PatrolStatus.LANDING
            
            # Stop streaming if active
            if self.video_streamer.is_streaming():
                self.video_streamer.stop_streaming()
            
            # Verify position
            if self.current_corner != 'bottom_right':
                patrol_logger.warning("Not at landing corner, returning to bottom right")
                await self.move_to_corner('bottom_right')
            
            # Gradual descent
            height = self.drone_manager.get_height()
            if height > 20:  # If above 20cm
                self.drone_manager.send_command('move_down', height - 20)
                await asyncio.sleep(self.config.LANDING_STABILIZATION_TIME)
            
            # Final landing
            if not self.drone_manager.land():
                raise Exception("Landing failed")
                
            await asyncio.sleep(self.config.LANDING_STABILIZATION_TIME)
            patrol_logger.info("Landing complete")
            return True
            
        except Exception as e:
            patrol_logger.error(f"Landing error: {e}")
            self.status = PatrolStatus.ERROR
            await self.emergency()
            return False

    async def emergency(self) -> bool:
        """Execute emergency protocol."""
        try:
            patrol_logger.warning("EMERGENCY PROTOCOL INITIATED")
            self.status = PatrolStatus.EMERGENCY
            self.is_patrolling = False
            self.stop_requested.set()
            
            # Stop streaming if active
            if self.video_streamer.is_streaming():
                self.video_streamer.stop_streaming()
            
            # Emergency stop with timeout
            try:
                async with asyncio.timeout(self.config.EMERGENCY_TIMEOUT):
                    self.drone_manager.emergency_stop()
            except asyncio.TimeoutError:
                patrol_logger.error("Emergency stop timed out")
            
            # Update metrics
            if hasattr(self, 'metrics'):
                self.metrics.errors_encountered += 1
                self._finalize_metrics('emergency')
                
            return True
            
        except Exception as e:
            patrol_logger.error(f"Emergency protocol error: {e}")
            return False

    async def rotate_360(self) -> bool:
        """Execute 360-degree scan."""
        try:
            patrol_logger.info("Executing 360° scan")
            scan_start_time = time.time()
            
            # Calculate rotation time based on speed
            rotation_time = 360 / self.config.ROTATION_SPEED
            
            # Reset stream buffer before scan
            if self.video_streamer.is_streaming():
                self.video_streamer.frame_buffer.clear()
            
            # Rotate clockwise with stability checks
            start_heading = self.drone_manager.get_heading()
            self.drone_manager.send_command('rotate_clockwise', 360)
            
            # Monitor rotation
            elapsed = 0
            while elapsed < (rotation_time + self.config.ROTATION_STABILIZATION_TIME):
                if self.stop_requested.is_set():
                    return False
                    
                await asyncio.sleep(0.5)
                elapsed += 0.5
                
                # Check for stuck rotation
                current_heading = self.drone_manager.get_heading()
                if abs(current_heading - start_heading) < 10 and elapsed > 2:
                    patrol_logger.warning("Rotation appears stuck, retrying")
                    self.drone_manager.send_command('rotate_clockwise', 360)
            
            # Update metrics
            scan_duration = time.time() - scan_start_time
            self.metrics.scan_durations.append(scan_duration)
            self.metrics.scans_completed += 1
            
            patrol_logger.info(f"360° scan complete in {scan_duration:.1f}s")
            return True
            
        except Exception as e:
            patrol_logger.error(f"Rotation error: {e}")
            return False

    async def move_to_corner(self, target_corner: str) -> bool:
        """Move to specified corner with precise control."""
        try:
            if target_corner not in self.CORNERS:
                raise ValueError(f"Invalid corner: {target_corner}")
                
            patrol_logger.info(f"Moving to corner: {target_corner}")
            
            # Get current and target positions
            current = self.CORNERS[self.current_corner]
            target = self.CORNERS[target_corner]
            
            # Calculate movements
            dx = target[0] - current[0]
            dy = target[1] - current[1]
            
            # Track distance for metrics
            distance = math.sqrt(dx*dx + dy*dy)
            
            # Execute movements with stability checks
            for movement in [('x', dx), ('y', dy)]:
                axis, delta = movement
                if delta == 0:
                    continue
                
                if self.stop_requested.is_set():
                    return False
                
                # Determine movement direction and command
                if axis == 'x':
                    direction = 'move_right' if delta > 0 else 'move_left'
                else:
                    direction = 'move_forward' if delta > 0 else 'move_back'
                
                # Execute movement
                self.drone_manager.send_command(direction, abs(delta))
                
                # Wait for movement completion with extra stability time
                move_time = abs(delta) / self.config.SPEED
                await asyncio.sleep(move_time + self.config.CORNER_STABILIZATION_TIME)
            
            # Update tracking
            self.current_corner = target_corner
            self._update_metrics(distance)
            
            patrol_logger.info(f"Reached corner: {target_corner}")
            return True
            
        except Exception as e:
            patrol_logger.error(f"Movement error: {e}")
            return False

    async def clockwise_patrol(self) -> bool:
        """Execute clockwise patrol route."""
        return await self._execute_patrol('clockwise')

    async def counterclockwise_patrol(self) -> bool:
        """Execute counterclockwise patrol route."""
        return await self._execute_patrol('counterclockwise')

    async def _execute_patrol(self, direction: str) -> bool:
        """Execute patrol sequence in specified direction."""
        try:
            if not self._patrol_lock.acquire(blocking=False):
                patrol_logger.warning("Another patrol is already in progress")
                return False
            
            try:
                patrol_logger.info(f"Starting {direction} patrol")
                self.is_patrolling = True
                self.status = PatrolStatus.PATROLLING
                self.stop_requested.clear()
                
                # Initialize metrics
                self._start_metrics(direction)
                
                # Takeoff and initialization
                if not await self.takeoff():
                    return False
                
                # Execute patrol sequence
                for corner in self.SEQUENCES[direction]:
                    if self.stop_requested.is_set():
                        patrol_logger.info("Patrol stop requested")
                        break
                    
                    if not await self.move_to_corner(corner):
                        await self.emergency()
                        return False
                    
                    if not await self.rotate_360():
                        await self.emergency()
                        return False
                    
                    await asyncio.sleep(self.config.CORNER_STABILIZATION_TIME)
                
                # Return and land
                await self.land()
                
                # Finalize metrics
                self._finalize_metrics("completed" if not self.stop_requested.is_set() else "stopped")
                
                patrol_logger.info(f"{direction} patrol complete")
                return True
                
            finally:
                self.is_patrolling = False
                self.status = PatrolStatus.IDLE
                self._patrol_lock.release()
            
        except Exception as e:
            patrol_logger.error(f"{direction} patrol error: {e}")
            await self.emergency()
            return False

    def stop_patrol(self) -> bool:
        """Safely stop current patrol."""
        try:
            patrol_logger.info("Stop patrol requested")
            self.stop_requested.set()
            return True
        except Exception as e:
            patrol_logger.error(f"Error stopping patrol: {e}")
            return False

    def get_status(self) -> Dict:
        """Get current patrol status and metrics."""
        try:
            current_metrics = None
            if hasattr(self, 'metrics'):
                current_metrics = {
                    'start_time': self.metrics.start_time,
                    'corners_visited': self.metrics.corners_visited,
                    'scans_completed': self.metrics.scans_completed,
                    'distance_traveled': self.metrics.distance_traveled,
                    'patrol_type': self.metrics.patrol_type,
                    'patrol_size': self.metrics.patrol_size,
                    'battery_start': self.metrics.battery_start,
                    'errors_encountered': self.metrics.errors_encountered
                }

            status = {
                'status': self.status.value,
                'is_patrolling': self.is_patrolling,
                'current_corner': self.current_corner,
                'battery_level': self.drone_manager.battery_level,
                'streaming': self.video_streamer.is_streaming() if self.video_streamer else False,
                'current_metrics': current_metrics,
                'total_patrols': len(self.patrol_history),
                'last_patrol': self.patrol_history[-1] if self.patrol_history else None
            }
            
            return status
            
        except Exception as e:
            patrol_logger.error(f"Error getting status: {e}")
            return {
                'status': PatrolStatus.ERROR.value,
                'error': str(e)
            }

    def get_patrol_history(self) -> List[Dict]:
        """Get history of completed patrols."""
        try:
            history = []
            for patrol in self.patrol_history:
                history.append({
                    'patrol_number': patrol.patrol_number,
                    'patrol_type': patrol.patrol_type,
                    'patrol_size': patrol.patrol_size,
                    'start_time': patrol.start_time,
                    'end_time': patrol.end_time,
                    'duration': patrol.end_time - patrol.start_time,
                    'distance_traveled': patrol.distance_traveled,
                    'corners_visited': patrol.corners_visited,
                    'scans_completed': patrol.scans_completed,
                    'battery_used': patrol.battery_start - patrol.battery_end,
                    'completion_status': patrol.completion_status,
                    'detection_count': patrol.detection_count,
                    'errors_encountered': patrol.errors_encountered,
                    'avg_height_deviation': sum(patrol.height_deviations) / len(patrol.height_deviations) if patrol.height_deviations else 0,
                    'avg_scan_duration': sum(patrol.scan_durations) / len(patrol.scan_durations) if patrol.scan_durations else 0
                })
            return history
            
        except Exception as e:
            patrol_logger.error(f"Error getting patrol history: {e}")
            return []

    def cleanup(self) -> None:
        """Cleanup patrol resources."""
        try:
            patrol_logger.info("Cleaning up patrol resources")
            
            # Stop any active patrol
            self.stop_requested.set()
            self.is_patrolling = False
            
            # Release lock if held
            if self._patrol_lock.locked():
                self._patrol_lock.release()
            
            # Reset status
            self.status = PatrolStatus.IDLE
            self.current_corner = 'bottom_right'
            
            patrol_logger.info("Patrol cleanup complete")
            
        except Exception as e:
            patrol_logger.error(f"Cleanup error: {e}")

    def validate_patrol_conditions(self) -> Tuple[bool, str]:
        """Validate conditions for starting a patrol."""
        try:
            if self.is_patrolling:
                return False, "Patrol already in progress"
                
            if self.drone_manager.battery_level < self.config.MIN_BATTERY:
                return False, "Battery level too low"
                
            if not self.drone_manager.is_connected:
                return False, "Drone not connected"
                
            if self.status == PatrolStatus.ERROR:
                return False, "Drone in error state"
                
            if self.current_corner != 'bottom_right':
                return False, "Drone not at starting position"
                
            return True, "OK"
            
        except Exception as e:
            patrol_logger.error(f"Validation error: {e}")
            return False, f"Validation error: {str(e)}"