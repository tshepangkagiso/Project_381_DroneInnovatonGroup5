from typing import List, Dict, Optional, Tuple
import threading
import asyncio
import time
import logging
import math
import json
from datetime import datetime
from pathlib import Path
from enum import Enum
import cv2
import numpy as np

logger = logging.getLogger(__name__)

class PatrolStatus(Enum):
    IDLE = "idle"
    PATROLLING = "patrolling"
    SCANNING = "scanning"
    RETURNING = "returning"
    EMERGENCY = "emergency"

class Point:
    def __init__(self, x: float, y: float, z: float):
        self.x = x
        self.y = y
        self.z = z

    def __str__(self):
        return f"Point(x={self.x:.2f}, y={self.y:.2f}, z={self.z:.2f})"

    def distance_to(self, other: 'Point') -> float:
        return math.sqrt(
            (self.x - other.x) ** 2 +
            (self.y - other.y) ** 2 +
            (self.z - other.z) ** 2
        )

class PatrolSystem:
    def __init__(self, drone_manager, socketio):
        """Initialize patrol system with drone manager and socketio."""
        self.drone_manager = drone_manager
        self.socketio = socketio
        self.status = PatrolStatus.IDLE
        
        # Configuration
        self.patrol_height = 10.0  # Default height in meters
        self.square_size = 0.0     # Size of square perimeter
        self.scan_duration = 30    # Seconds for 360° scan
        
        # Points and positions
        self.home_point = Point(0, 0, 0)
        self.current_point = None
        self.patrol_points: List[Point] = []
        
        # Corner definitions
        self.corners = {
            'top_right': {'x': 1, 'y': 1, 'name': 'Top Right'},
            'top_left': {'x': 0, 'y': 1, 'name': 'Top Left'},
            'bottom_left': {'x': 0, 'y': 0, 'name': 'Bottom Left'},
            'bottom_right': {'x': 1, 'y': 0, 'name': 'Bottom Right'}
        }
        
        # Control flags
        self.stop_event = threading.Event()
        
        # Monitoring
        self.mission_start_time = None
        self.points_covered = 0
        self.threats_detected = 0
        
        # Threat logging
        self.threats_dir = Path("threats")
        self.threats_dir.mkdir(exist_ok=True)
        
        logger.info("Patrol System initialized")

    def set_height(self, height: float) -> bool:
        """Set patrol height in meters."""
        try:
            if 2.0 <= height <= 30.0:
                self.patrol_height = height
                logger.info(f"Patrol height set to {height}m")
                return True
            logger.error(f"Invalid height: {height}m. Must be between 2-30m")
            return False
        except Exception as e:
            logger.error(f"Error setting height: {e}")
            return False

    def calculate_square_points(self, size: float) -> bool:
        """Calculate patrol points for square perimeter."""
        try:
            if size <= 0:
                logger.error("Square size must be positive")
                return False
                
            self.square_size = size
            # Always starts from bottom right
            self.patrol_points = [
                Point(size, 0, self.patrol_height),     # Bottom right (start)
                Point(size, size, self.patrol_height),  # Top right
                Point(0, size, self.patrol_height),     # Top left
                Point(0, 0, self.patrol_height)         # Bottom left
            ]
            logger.info(f"Square patrol points calculated for {size}m perimeter")
            return True
        except Exception as e:
            logger.error(f"Error calculating square points: {e}")
            return False

    def generate_random_points(self) -> List[Point]:
        """Generate random patrol points based on battery level."""
        try:
            battery = self.drone_manager.battery_level
            num_points = 3 if battery > 75 else 1
            
            points = []
            for _ in range(num_points):
                x = np.random.uniform(0, self.square_size)
                y = np.random.uniform(0, self.square_size)
                points.append(Point(x, y, self.patrol_height))
            
            return points
        except Exception as e:
            logger.error(f"Error generating random points: {e}")
            return []

    async def patrol_specific_corner(self, corner_id: str) -> bool:
        """Patrol a specific corner from bottom right."""
        try:
            if self.status != PatrolStatus.IDLE:
                logger.error("Patrol already in progress")
                return False
            
            if corner_id not in self.corners:
                logger.error(f"Invalid corner: {corner_id}")
                return False

            self.status = PatrolStatus.PATROLLING
            self.mission_start_time = time.time()
            self.stop_event.clear()

            # Start from bottom right
            start_point = Point(self.square_size, 0, self.patrol_height)
            
            # Calculate target corner position
            corner = self.corners[corner_id]
            target_x = corner['x'] * self.square_size
            target_y = corner['y'] * self.square_size
            target_point = Point(target_x, target_y, self.patrol_height)

            # Move to target corner
            if await self.drone_manager.move_to(target_point.x, target_point.y, target_point.z):
                self.current_point = target_point
                
                # Perform scan at corner
                await self.perform_scan()
                
                # Return to start point
                await self.drone_manager.move_to(start_point.x, start_point.y, start_point.z)
                
            self.status = PatrolStatus.IDLE
            self.emit_mission_summary()
            return True

        except Exception as e:
            logger.error(f"Error during corner patrol: {e}")
            await self.emergency_return()
            return False

    async def perform_scan(self) -> Optional[Dict]:
        """Perform 360° scan at current position."""
        try:
            self.status = PatrolStatus.SCANNING
            
            # Start the 360° rotation
            if not await self.drone_manager.scan_360():
                return None

            threats_detected = []
            
            # Process detections during scan
            for _ in range(8):  # 8 * 45° = 360°
                frame = self.drone_manager.video_streamer.get_frame(
                    self.drone_manager.drone
                )
                if frame is not None:
                    detections = self.drone_manager.video_streamer.detector.detect_objects(
                        frame
                    )
                    
                    # Check for threats
                    threats = [d for d in detections if d['threat_level'] == 'high']
                    if threats:
                        await self.log_threat(threats, frame)
                        threats_detected.extend(threats)
                
                await asyncio.sleep(self.scan_duration / 8)
            
            return {'threats': threats_detected} if threats_detected else None
            
        except Exception as e:
            logger.error(f"Error during scan: {e}")
            return None

    async def log_threat(self, threats: List[Dict], frame: np.ndarray) -> None:
        """Log detected threats with images and metadata."""
        try:
            # Create date-based directory
            date_dir = self.threats_dir / datetime.now().strftime('%Y-%m-%d')
            date_dir.mkdir(exist_ok=True)

            # Save threat data
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            # Save image
            image_path = date_dir / f"threat_{timestamp}.jpg"
            cv2.imwrite(str(image_path), frame)

            # Save metadata
            metadata = {
                'timestamp': timestamp,
                'location': str(self.current_point),
                'threats': threats,
                'patrol_context': {
                    'battery_level': self.drone_manager.battery_level,
                    'points_covered': self.points_covered,
                    'total_points': len(self.patrol_points)
                }
            }
            
            json_path = date_dir / f"threat_{timestamp}.json"
            with open(json_path, 'w') as f:
                json.dump(metadata, f, indent=2)

            # Emit alert to dashboard
            self.socketio.emit('threat_alert', {
                'threats': threats,
                'location': str(self.current_point),
                'image_path': str(image_path),
                'timestamp': timestamp
            })

        except Exception as e:
            logger.error(f"Error logging threat: {e}")

    async def start_patrol(self, patrol_type: str = 'square') -> bool:
        """Start patrol mission."""
        try:
            if self.status != PatrolStatus.IDLE:
                logger.error("Patrol already in progress")
                return False
            
            if self.drone_manager.battery_level < 20:
                logger.error("Battery too low for patrol")
                return False

            self.mission_start_time = time.time()
            self.points_covered = 0
            self.threats_detected = 0
            self.stop_event.clear()
            self.status = PatrolStatus.PATROLLING

            points_to_patrol = (
                self.patrol_points if patrol_type == 'square'
                else self.generate_random_points()
            )

            # Execute patrol
            for point in points_to_patrol:
                if self.stop_event.is_set():
                    break

                # Move to point
                if await self.drone_manager.move_to(point.x, point.y, point.z):
                    self.current_point = point
                    self.points_covered += 1
                    
                    # Notify point reached
                    self.socketio.emit('point_reached', {
                        'point': str(point),
                        'total_points': len(points_to_patrol)
                    })

                    # Perform scan at point
                    threat_data = await self.perform_scan()
                    if threat_data:
                        self.threats_detected += 1
                        await self.handle_threat(threat_data)

                await self.emit_status()

            await self.return_home()
            return True

        except Exception as e:
            logger.error(f"Error during patrol: {e}")
            await self.emergency_return()
            return False

    async def handle_threat(self, threat_data: Dict) -> None:
        """Handle detected threat."""
        try:
            position = str(self.current_point)
            
            threat_info = {
                'threats': threat_data['threats'],
                'location': position,
                'timestamp': datetime.now().isoformat(),
                'patrol_stats': {
                    'points_covered': self.points_covered,
                    'threats_detected': self.threats_detected
                }
            }
            
            self.socketio.emit('threat_detected', threat_info)
            logger.warning(f"Threat detected at {position}")
            
        except Exception as e:
            logger.error(f"Error handling threat: {e}")

    async def return_home(self) -> bool:
        """Return drone to home position (bottom right)."""
        try:
            self.status = PatrolStatus.RETURNING
            success = await self.drone_manager.move_to(
                self.square_size, 0, self.patrol_height
            )
            self.status = PatrolStatus.IDLE
            self.emit_mission_summary()
            return success
        except Exception as e:
            logger.error(f"Error returning home: {e}")
            return False

    async def emergency_return(self) -> None:
        """Emergency return procedure."""
        try:
            self.status = PatrolStatus.EMERGENCY
            self.stop_event.set()
            await self.return_home()
        except Exception as e:
            logger.error(f"Error during emergency return: {e}")

    def stop_patrol(self) -> None:
        """Stop current patrol."""
        self.stop_event.set()
        logger.info("Patrol stop requested")

    async def emit_status(self) -> None:
        """Emit current status to clients."""
        try:
            status = {
                'status': self.status.value,
                'current_point': str(self.current_point) if self.current_point else None,
                'battery': self.drone_manager.battery_level,
                'height': self.patrol_height,
                'points_covered': self.points_covered,
                'threats_detected': self.threats_detected
            }
            self.socketio.emit('patrol_status', status)
        except Exception as e:
            logger.error(f"Error emitting status: {e}")

    def emit_mission_summary(self) -> None:
        """Emit mission summary."""
        if self.mission_start_time:
            try:
                duration = int(time.time() - self.mission_start_time)
                summary = {
                    'duration': duration,
                    'points_covered': self.points_covered,
                    'threats_detected': self.threats_detected,
                    'battery_used': self.drone_manager.battery_level
                }
                self.socketio.emit('mission_complete', summary)
            except Exception as e:
                logger.error(f"Error emitting mission summary: {e}")