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

class PatrolDrone:
    """Manages automated drone patrol sequences."""
    
    def __init__(self, drone_manager):
        """Initialize patrol drone with configuration."""
        try:
            # Store reference to drone_manager instead of importing the class
            self.drone_manager = drone_manager
            self.video_streamer = drone_manager.video_streamer
            
            # Patrol configuration
            self.PERIMETER = {
                'width': 400,  # 4 meters in cm
                'height': 400  # 4 meters in cm
            }
            self.TAKEOFF_HEIGHT = 200  # 2 meters in cm
            self.SPEED = 15  # 15 cm/s
            self.BUFFER = 15  # 15cm buffer from edges
            self.ROTATION_SPEED = 45  # degrees per second
            
            # Corner coordinates (x, y) in cm from bottom right origin
            self.CORNERS = {
                'bottom_right': (0, 0),
                'top_right': (0, self.PERIMETER['height'] - self.BUFFER),
                'top_left': (self.PERIMETER['width'] - self.BUFFER, self.PERIMETER['height'] - self.BUFFER),
                'bottom_left': (self.PERIMETER['width'] - self.BUFFER, 0)
            }
            
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
            
            patrol_logger.info("Patrol Drone initialized successfully")
            
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
            
            # Add to history
            self.patrol_history.append(self.metrics)
            
            # Log summary
            duration = self.metrics.end_time - self.metrics.start_time
            battery_used = self.metrics.battery_start - self.metrics.battery_end
            
            patrol_logger.info(
                f"Patrol {self.metrics.patrol_number} completed:\n"
                f"Type: {self.metrics.patrol_type}\n"
                f"Duration: {duration:.1f}s\n"
                f"Distance: {self.metrics.distance_traveled}cm\n"
                f"Battery used: {battery_used}%\n"
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
            if self.drone_manager.battery_level < 20:
                raise Exception("Battery too low for takeoff")
                
            # Initial takeoff
            if not self.drone_manager.take_off():
                raise Exception("Takeoff failed")
            
            # Wait for stability
            await asyncio.sleep(2)
            
            # Rise to patrol height
            self.drone_manager.send_command('move_up', self.TAKEOFF_HEIGHT)
            await asyncio.sleep(3)  # Extra time for height stability
            
            # Verify height
            height = self.drone_manager.get_height()
            if abs(height - self.TAKEOFF_HEIGHT) > 20:  # 20cm tolerance
                patrol_logger.warning(f"Height deviation detected: {height}cm vs {self.TAKEOFF_HEIGHT}cm")
                self.drone_manager.send_command('move_up', self.TAKEOFF_HEIGHT - height)
                await asyncio.sleep(2)
            
            # Start streaming
            if not self.video_streamer.is_streaming():
                self.video_streamer.start_streaming(self.drone_manager.drone)
                await asyncio.sleep(1)
            
            patrol_logger.info(f"Takeoff complete at height {self.TAKEOFF_HEIGHT}cm")
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
            if height > 100:  # If above 1m
                self.drone_manager.send_command('move_down', height - 50)
                await asyncio.sleep(2)
            
            # Final landing
            if not self.drone_manager.land():
                raise Exception("Landing failed")
                
            await asyncio.sleep(2)
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
            
            # Emergency stop
            self.drone_manager.emergency_stop()
            
            # Update metrics
            if hasattr(self, 'metrics'):
                self._finalize_metrics('emergency')
                
            return True
            
        except Exception as e:
            patrol_logger.error(f"Emergency protocol error: {e}")
            return False

    async def rotate_360(self) -> bool:
        """Execute 360-degree scan."""
        try:
            patrol_logger.info("Executing 360° scan")
            
            # Calculate rotation time based on speed
            rotation_time = 360 / self.ROTATION_SPEED
            
            # Reset stream buffer before scan
            if self.video_streamer.is_streaming():
                self.video_streamer.frame_buffer.clear()
            
            # Rotate clockwise with stability checks
            start_heading = self.drone_manager.get_heading()
            self.drone_manager.send_command('rotate_clockwise', 360)
            
            # Monitor rotation
            elapsed = 0
            while elapsed < (rotation_time + 2):  # Add 2s buffer
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
            self.metrics.scans_completed += 1
            
            patrol_logger.info("360° scan complete")
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
            if dx != 0:
                direction = 'move_right' if dx > 0 else 'move_left'
                self.drone_manager.send_command(direction, abs(dx))
                await asyncio.sleep(abs(dx) / self.SPEED + 1)
                
                # Verify position
                if abs(self.drone_manager.get_position()[0] - target[0]) > 20:
                    patrol_logger.warning("Position deviation detected, adjusting")
                    await asyncio.sleep(1)
            
            if dy != 0 and not self.stop_requested.is_set():
                direction = 'move_forward' if dy > 0 else 'move_back'
                self.drone_manager.send_command(direction, abs(dy))
                await asyncio.sleep(abs(dy) / self.SPEED + 1)
                
                # Verify position
                if abs(self.drone_manager.get_position()[1] - target[1]) > 20:
                    patrol_logger.warning("Position deviation detected, adjusting")
                    await asyncio.sleep(1)
            
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
        try:
            # Ensure no other patrol is running
            if not self._patrol_lock.acquire(blocking=False):
                patrol_logger.warning("Another patrol is already in progress")
                return False
            
            try:
                patrol_logger.info("Starting clockwise patrol")
                self.is_patrolling = True
                self.status = PatrolStatus.PATROLLING
                self.stop_requested.clear()
                
                # Initialize metrics
                self._start_metrics("clockwise")
                
                # Takeoff and initialization
                if not await self.takeoff():
                    return False
                
                # Execute patrol sequence
                corner_sequence = ['top_right', 'top_left', 'bottom_left', 'bottom_right']
                
                for corner in corner_sequence:
                    if self.stop_requested.is_set():
                        patrol_logger.info("Patrol stop requested")
                        break
                    
                    # Move to corner
                    if not await self.move_to_corner(corner):
                        await self.emergency()
                        return False
                    
                    # Execute scan
                    if not await self.rotate_360():
                        await self.emergency()
                        return False
                    
                    await asyncio.sleep(1)  # Stability pause
                
                # Return and land
                await self.land()
                
                # Finalize metrics
                self._finalize_metrics("completed" if not self.stop_requested.is_set() else "stopped")
                
                patrol_logger.info("Clockwise patrol complete")
                return True
                
            finally:
                self.is_patrolling = False
                self.status = PatrolStatus.IDLE
                self._patrol_lock.release()
            
        except Exception as e:
            patrol_logger.error(f"Clockwise patrol error: {e}")
            await self.emergency()
            return False

    async def counterclockwise_patrol(self) -> bool:
        """Execute counterclockwise patrol route."""
        try:
            # Ensure no other patrol is running
            if not self._patrol_lock.acquire(blocking=False):
                patrol_logger.warning("Another patrol is already in progress")
                return False
            
            try:
                patrol_logger.info("Starting counterclockwise patrol")
                self.is_patrolling = True
                self.status = PatrolStatus.PATROLLING
                self.stop_requested.clear()
                
                # Initialize metrics
                self._start_metrics("counterclockwise")
                
                # Takeoff and initialization
                if not await self.takeoff():
                    return False
                
                # Execute patrol sequence
                corner_sequence = ['bottom_left', 'top_left', 'top_right', 'bottom_right']
                
                for corner in corner_sequence:
                    if self.stop_requested.is_set():
                        patrol_logger.info("Patrol stop requested")
                        break
                    
                    # Move to corner
                    if not await self.move_to_corner(corner):
                        await self.emergency()
                        return False
                    
                    # Execute scan
                    if not await self.rotate_360():
                        await self.emergency()
                        return False
                    
                    await asyncio.sleep(1)  # Stability pause
                
                # Return and land
                await self.land()
                
                # Finalize metrics
                self._finalize_metrics("completed" if not self.stop_requested.is_set() else "stopped")
                
                patrol_logger.info("Counterclockwise patrol complete")
                return True
                
            finally:
                self.is_patrolling = False
                self.status = PatrolStatus.IDLE
                self._patrol_lock.release()
            
        except Exception as e:
            patrol_logger.error(f"Counterclockwise patrol error: {e}")
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
                    'battery_start': self.metrics.battery_start
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
                    'start_time': patrol.start_time,
                    'end_time': patrol.end_time,
                    'duration': patrol.end_time - patrol.start_time,
                    'distance_traveled': patrol.distance_traveled,
                    'corners_visited': patrol.corners_visited,
                    'scans_completed': patrol.scans_completed,
                    'battery_used': patrol.battery_start - patrol.battery_end,
                    'completion_status': patrol.completion_status,
                    'detection_count': patrol.detection_count
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
                
            if self.drone_manager.battery_level < 20:
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