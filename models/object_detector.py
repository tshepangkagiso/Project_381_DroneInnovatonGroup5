import logging
import time
import cv2
import numpy as np
import os
import threading
from typing import List, Dict, Optional, Tuple, Set
from ultralytics import YOLO
from pathlib import Path
from collections import deque

# Configure logging
logger = logging.getLogger(__name__)

class ThreatTracker:
    """Track potential threats across frames."""
    def __init__(self, history_size: int = 5):
        self.history = deque(maxlen=history_size)
        self.threat_confidence = 0.0
        self.last_update = time.time()
        self.lock = threading.Lock()
        
    def update(self, detection: Dict) -> None:
        """Update threat tracking."""
        with self.lock:
            self.history.append(detection)
            self.threat_confidence = self._calculate_confidence()
            self.last_update = time.time()
            
    def _calculate_confidence(self) -> float:
        """Calculate overall threat confidence."""
        if not self.history:
            return 0.0
        weights = np.linspace(0.5, 1.0, len(self.history))
        confidences = [det.get('confidence', 0) for det in self.history]
        return np.average(confidences, weights=weights)
    
    def is_stable(self) -> bool:
        """Check if threat detection is stable."""
        return len(self.history) >= self.history.maxlen // 2

class DetectionCache:
    """Cache recent detections for performance."""
    def __init__(self, max_size: int = 10):
        self.cache = {}
        self.max_size = max_size
        self.lock = threading.Lock()
        
    def add(self, key: str, detection: Dict) -> None:
        """Add detection to cache."""
        with self.lock:
            self.cache[key] = {
                'detection': detection,
                'timestamp': time.time()
            }
            if len(self.cache) > self.max_size:
                oldest = min(self.cache.items(), key=lambda x: x[1]['timestamp'])
                del self.cache[oldest[0]]
                
    def get(self, key: str) -> Optional[Dict]:
        """Get cached detection if recent."""
        with self.lock:
            if key in self.cache:
                entry = self.cache[key]
                if time.time() - entry['timestamp'] < 1.0:  # 1 second validity
                    return entry['detection']
                del self.cache[key]
        return None

class ObjectDetector:
    def __init__(self):
        """Initialize optimized object detector."""
        try:
            logger.info("Initializing Optimized Object Detector...")
            
            # Initialize models directory
            self.models_dir = Path("models/weights")
            self.models_dir.mkdir(parents=True, exist_ok=True)
            
            # Primary model for fast inference
            #self.fast_model = self._load_or_download_model('yolov8n', "Fast detection model")
            self.fast_model = self._load_or_download_model('yolov8s', "Fast detection model")
            #self.fast_model = self._load_or_download_model('yolov8m', "Fast detection model")
            self.model = self.fast_model  # Save reference to current model
            
            # Secondary model for threat verification
            self.threat_model = None
            
            # Detection settings
            self._init_detection_settings()
            
            # Threading and synchronization
            self._lock = threading.Lock()
            self.processing_thread = None
            self.is_processing = False
            
            # Caching and tracking
            self.detection_cache = DetectionCache()
            self.threat_trackers = {}
            self.motion_detector = self._init_motion_detector()
            
            # Performance metrics
            self._init_metrics()
            
            logger.info("Object Detector initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Object Detector: {e}")
            raise

    def _init_detection_settings(self) -> None:
        """Initialize optimized detection settings."""
        self.settings = {
            'fast_model': {
                'conf_threshold': 0.3,
                'iou_threshold': 0.45
            },
            'threat_model': {
                'conf_threshold': 0.4,
                'iou_threshold': 0.5
            },
            'motion': {
                'threshold': 1000,
                'blur_size': (21, 21)
            },
            'weapon_detection': {
                'proximity_threshold': 100,  # pixels
                'confidence_threshold': 0.25,
                'verification_interval': 0.5  # seconds
            },
            'processing': {
                'max_frame_size': (640, 640),
                'target_fps': 30
            }
        }
        
        # Target classes with optimized thresholds
        self.target_classes = {
            'person': {'threshold': 0.3},
            'knife': {'threshold': 0.25},
            'scissors': {'threshold': 0.25},
            'cell phone': {'threshold': 0.3},
            'remote': {'threshold': 0.3},
            'bottle': {'threshold': 0.3}
        }
        
        # Weapon class mappings
        self.weapon_classes = {
            'high_threat': ['knife', 'scissors'],
            'potential_threat': ['cell phone', 'remote', 'bottle']
        }

    def _init_motion_detector(self) -> Dict:
        """Initialize motion detection."""
        return {
            'prev_frame': None,
            'min_area': 500,
            'blur_size': (21, 21),
            'threshold': 25,
            'dilate_iter': 2
        }

    def _init_metrics(self) -> None:
        """Initialize performance metrics."""
        self.metrics = {
            'total_frames': 0,
            'detection_times': deque(maxlen=100),
            'true_positives': 0,
            'false_positives': 0,
            'cached_hits': 0,
            'model_switches': 0
        }

    def _load_or_download_model(self, model_name: str, description: str) -> Optional[YOLO]:
        """
        Load or download YOLO model with optimized error handling.
        """
        try:
            logger.info(f"Loading {description} ({model_name})...")
            
            # Define model paths
            model_path = self.models_dir / f"{model_name}.pt"
            
            # Check if model exists
            if not model_path.exists():
                logger.info(f"Downloading {model_name} model...")
                try:
                    # Download and save model
                    model = YOLO(f"{model_name}.pt")
                    model.save(str(model_path))
                    logger.info(f"Model downloaded and saved to {model_path}")
                except Exception as download_error:
                    logger.error(f"Error downloading model: {download_error}")
                    return None
            
            # Load model with error handling
            try:
                model = YOLO(str(model_path))
                logger.info(f"Successfully loaded {description}")
                return model
            except Exception as load_error:
                logger.error(f"Error loading model from {model_path}: {load_error}")
                # If loading fails, try to delete corrupted file
                if model_path.exists():
                    model_path.unlink()
                return None
                
        except Exception as e:
            logger.error(f"Unexpected error loading {description}: {e}")
            return None

    def detect_objects(self, frame: np.ndarray) -> List[Dict]:
        """Main detection function optimized for speed."""
        try:
            start_time = time.time()
            
            # Check frame validity
            if frame is None or frame.size == 0:
                return []
            
            # Resize if needed
            frame = self._preprocess_frame(frame)
            
            # Check motion
            if not self._check_motion(frame):
                # Return last detections if no significant motion
                return self.last_detections if hasattr(self, 'last_detections') else []
            
            # Run detection
            results = self.model(
                frame,
                conf=self.settings['fast_model']['conf_threshold'],
                iou=self.settings['fast_model']['iou_threshold']
            )
            
            # Process detections
            detections = []
            for result in results:
                boxes = result.boxes
                for box in boxes:
                    detection = self._create_detection(box, frame.shape[:2])
                    if detection and self._is_valid_detection(detection):
                        detections.append(detection)
            
            # Update metrics
            self._update_metrics(time.time() - start_time)
            
            self.last_detections = detections
            return detections
            
        except Exception as e:
            logger.error(f"Detection error: {e}")
            return []

    def _preprocess_frame(self, frame: np.ndarray) -> np.ndarray:
        """Preprocess frame for efficient detection."""
        try:
            # Calculate target size while maintaining aspect ratio
            target_size = self.settings['processing']['max_frame_size']
            h, w = frame.shape[:2]
            scale = min(target_size[0]/w, target_size[1]/h)
            
            if scale < 1:
                new_size = (int(w*scale), int(h*scale))
                frame = cv2.resize(frame, new_size)
            
            return frame
            
        except Exception as e:
            logger.error(f"Frame preprocessing error: {e}")
            return frame

    def _check_motion(self, frame: np.ndarray) -> bool:
        """Detect significant motion in frame."""
        try:
            # Convert to grayscale and blur
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, self.motion_detector['blur_size'], 0)
            
            # Initialize previous frame
            if self.motion_detector['prev_frame'] is None:
                self.motion_detector['prev_frame'] = gray
                return True
            
            # Calculate difference
            frame_delta = cv2.absdiff(self.motion_detector['prev_frame'], gray)
            thresh = cv2.threshold(frame_delta, self.motion_detector['threshold'], 255, cv2.THRESH_BINARY)[1]
            
            # Dilate to fill holes
            thresh = cv2.dilate(thresh, None, iterations=self.motion_detector['dilate_iter'])
            
            # Find contours
            contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # Update previous frame
            self.motion_detector['prev_frame'] = gray
            
            # Check if any contour is large enough
            return any(cv2.contourArea(c) > self.motion_detector['min_area'] for c in contours)
            
        except Exception as e:
            logger.error(f"Motion detection error: {e}")
            return True  # Default to processing frame if motion detection fails
    
    def _create_detection(self, box, image_shape: Tuple[int, int]) -> Optional[Dict]:
        """Create detection dictionary from YOLO box with optimized processing."""
        try:
            # Extract basic information
            cls = int(box.cls[0])
            conf = float(box.conf[0])
            
            # Get class name from model names
            class_name = self.model.names[cls]
            
            # Get coordinates
            xyxy = box.xyxy[0].cpu().numpy()
            x1, y1, x2, y2 = map(float, xyxy)
            
            # Ensure coordinates are within image bounds
            height, width = image_shape
            x1 = max(0, min(x1, width))
            x2 = max(0, min(x2, width))
            y1 = max(0, min(y1, height))
            y2 = max(0, min(y2, height))
            
            # Create detection dictionary
            detection = {
                'id': f"{class_name}_{int(time.time()*1000)}",
                'class': class_name,
                'confidence': conf,
                'box': [x1, y1, x2, y2],
                'center': ((x1 + x2) / 2, (y1 + y2) / 2),
                'area': (x2 - x1) * (y2 - y1),
                'timestamp': time.time()
            }
            
            # Add threat level if applicable
            if class_name in self.target_classes:
                detection['threat_level'] = (
                    'high' if class_name in self.weapon_classes['high_threat']
                    else 'medium' if class_name in self.weapon_classes['potential_threat']
                    else 'low'
                )
            
            return detection
            
        except Exception as e:
            logger.error(f"Error creating detection: {e}")
            return None

    def _is_valid_detection(self, detection: Dict) -> bool:
        """Validate detection with optimized checks."""
        try:
            # Required fields check
            required_fields = {'id', 'class', 'confidence', 'box'}
            if not all(field in detection for field in required_fields):
                return False
                
            # Confidence check
            if not isinstance(detection['confidence'], (int, float)):
                return False
            if not 0 <= detection['confidence'] <= 1:
                return False
                
            # Box coordinates check
            if not isinstance(detection['box'], (list, tuple)) or len(detection['box']) != 4:
                return False
            if not all(isinstance(coord, (int, float)) for coord in detection['box']):
                return False
                
            # Box dimensions check
            x1, y1, x2, y2 = detection['box']
            if x1 >= x2 or y1 >= y2:
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Error validating detection: {e}")
            return False

    def _check_threats(self, frame: np.ndarray, detections: List[Dict]) -> List[Dict]:
        """Check for potential threats using detailed analysis."""
        try:
            # Extract persons and weapons
            persons = [d for d in detections if d['class'] == 'person']
            weapons = [d for d in detections if d['class'] in 
                      self.weapon_classes['high_threat'] + self.weapon_classes['potential_threat']]
            
            if not persons or not weapons:
                return []
            
            threats = []
            for person in persons:
                person_threats = self._analyze_person_threats(person, weapons, frame)
                if person_threats:
                    threats.extend(person_threats)
            
            return threats
            
        except Exception as e:
            logger.error(f"Threat checking error: {e}")
            return []

    def _analyze_person_threats(self, person: Dict, weapons: List[Dict], frame: np.ndarray) -> List[Dict]:
        """Detailed threat analysis for a person."""
        try:
            threats = []
            person_box = person['box']
            person_center = self._get_box_center(person_box)
            
            for weapon in weapons:
                # Check proximity
                if self._check_weapon_proximity(person_box, weapon['box']):
                    # Verify with threat model if needed
                    if self._should_verify_threat(person, weapon):
                        if self._verify_threat(frame, person, weapon):
                            threat = self._create_threat_detection(person, weapon)
                            threats.append(threat)
                    else:
                        # Use cached verification
                        threat = self._create_threat_detection(person, weapon)
                        threats.append(threat)
            
            return threats
            
        except Exception as e:
            logger.error(f"Person threat analysis error: {e}")
            return []

    def _check_weapon_proximity(self, person_box: List[float], weapon_box: List[float]) -> bool:
        """Check if weapon is close to person."""
        try:
            # Calculate centers
            person_center = self._get_box_center(person_box)
            weapon_center = self._get_box_center(weapon_box)
            
            # Calculate distance
            distance = np.sqrt(
                (person_center[0] - weapon_center[0])**2 +
                (person_center[1] - weapon_center[1])**2
            )
            
            # Check if within threshold
            return distance <= self.settings['weapon_detection']['proximity_threshold']
            
        except Exception as e:
            logger.error(f"Weapon proximity check error: {e}")
            return False

    def _should_verify_threat(self, person: Dict, weapon: Dict) -> bool:
        """Determine if threat needs verification."""
        try:
            # Generate cache key
            cache_key = f"{person['id']}_{weapon['id']}"
            
            # Check cache
            cached = self.detection_cache.get(cache_key)
            if cached:
                self.metrics['cached_hits'] += 1
                return False
            
            # Always verify high threat weapons
            if weapon['class'] in self.weapon_classes['high_threat']:
                return True
            
            # Verify if confidence is low
            return weapon['confidence'] < self.settings['weapon_detection']['confidence_threshold']
            
        except Exception as e:
            logger.error(f"Threat verification check error: {e}")
            return True

    def _verify_threat(self, frame: np.ndarray, person: Dict, weapon: Dict) -> bool:
        """Verify threat using detailed analysis."""
        try:
            # Load threat model if needed
            if self.threat_model is None:
                self.threat_model = self._load_or_download_model('yolov8x', "Threat verification model")
                self.metrics['model_switches'] += 1
            
            # Get region of interest
            roi = self._get_roi(frame, person['box'], weapon['box'])
            
            # Run verification
            results = self.threat_model(
                roi,
                conf=self.settings['threat_model']['conf_threshold'],
                iou=self.settings['threat_model']['iou_threshold']
            )
            
            # Check results
            verified = False
            for result in results:
                for box in result.boxes:
                    cls = int(box.cls[0])
                    conf = float(box.conf[0])
                    class_name = self.threat_model.names[cls]
                    
                    if class_name == weapon['class'] and conf > weapon['confidence']:
                        verified = True
                        break
            
            # Cache result
            if verified:
                cache_key = f"{person['id']}_{weapon['id']}"
                self.detection_cache.add(cache_key, {
                    'verified': True,
                    'confidence': max(weapon['confidence'], conf)
                })
            
            return verified
            
        except Exception as e:
            logger.error(f"Threat verification error: {e}")
            return False

    def _create_threat_detection(self, person: Dict, weapon: Dict) -> Dict:
        """Create armed person detection."""
        try:
            # Combine boxes to encompass both person and weapon
            x1 = min(person['box'][0], weapon['box'][0])
            y1 = min(person['box'][1], weapon['box'][1])
            x2 = max(person['box'][2], weapon['box'][2])
            y2 = max(person['box'][2], weapon['box'][2])
            
            # Calculate combined confidence
            confidence = np.sqrt(person['confidence'] * weapon['confidence'])
            
            # Create threat detection
            threat = {
                'id': f"threat_{person['id']}_{weapon['id']}",
                'class': 'armed_person',
                'confidence': confidence,
                'box': [x1, y1, x2, y2],
                'threat_level': 'high',
                'person': person,
                'weapon': weapon,
                'timestamp': time.time()
            }
            
            # Update threat tracker
            if threat['id'] not in self.threat_trackers:
                self.threat_trackers[threat['id']] = ThreatTracker()
            self.threat_trackers[threat['id']].update(threat)
            
            return threat
            
        except Exception as e:
            logger.error(f"Threat detection creation error: {e}")
            return None
    
    def draw_detections(self, frame: np.ndarray, detections: List[Dict]) -> np.ndarray:
        """Draw detections with improved visualization."""
        try:
            frame_copy = frame.copy()
            
            # Sort detections by threat level
            detections = sorted(
                detections,
                key=lambda x: self._get_threat_priority(x.get('threat_level', 'none')),
                reverse=True
            )
            
            # Draw each detection
            for det in detections:
                try:
                    self._draw_single_detection(frame_copy, det)
                except Exception as e:
                    logger.error(f"Error drawing detection: {e}")
                    continue
            
            # Add performance metrics
            self._add_metrics_overlay(frame_copy)
            
            return frame_copy
            
        except Exception as e:
            logger.error(f"Detection drawing error: {e}")
            return frame

    def _draw_single_detection(self, frame: np.ndarray, det: Dict) -> None:
        """Draw a single detection with enhanced visuals."""
        try:
            x1, y1, x2, y2 = map(int, det['box'])
            
            # Get color based on threat level
            color = self._get_threat_color(det.get('threat_level', 'none'))
            
            # Draw box
            thickness = 3 if det.get('threat_level') == 'high' else 2
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)
            
            # Create label
            label = self._create_label(det)
            
            # Draw label background
            label_size, baseline = cv2.getTextSize(
                label,
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                2
            )
            
            cv2.rectangle(
                frame,
                (x1, y1 - label_size[1] - 10),
                (x1 + label_size[0], y1),
                color,
                -1
            )
            
            # Draw label text
            cv2.putText(
                frame,
                label,
                (x1, y1 - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                2
            )
            
            # Add additional indicators for threats
            if det.get('threat_level') == 'high':
                self._add_threat_indicators(frame, det)
            
        except Exception as e:
            logger.error(f"Error drawing single detection: {e}")

    def _get_threat_color(self, threat_level: str) -> Tuple[int, int, int]:
        """Get color for threat level."""
        colors = {
            'high': (0, 0, 255),    # Red
            'medium': (0, 165, 255), # Orange
            'low': (0, 255, 0),      # Green
            'none': (255, 255, 0)    # Yellow
        }
        return colors.get(threat_level, colors['none'])

    def _get_threat_priority(self, threat_level: str) -> int:
        """Get numerical priority for threat level sorting."""
        priorities = {
            'high': 3,
            'medium': 2,
            'low': 1,
            'none': 0
        }
        return priorities.get(threat_level, 0)

    def _create_label(self, det: Dict) -> str:
        """Create detection label."""
        try:
            # Base label
            base = f"{det['class']} {det['confidence']:.2f}"
            
            # Add threat level for armed persons
            if det['class'] == 'armed_person':
                weapon_type = det['weapon']['class']
                base = f"⚠️ ARMED ({weapon_type}) {det['confidence']:.2f}"
            
            return base
            
        except Exception as e:
            logger.error(f"Label creation error: {e}")
            return "Unknown"

    def _add_threat_indicators(self, frame: np.ndarray, det: Dict) -> None:
        """Add visual indicators for threats."""
        try:
            x1, y1, x2, y2 = map(int, det['box'])
            
            # Draw corner indicators
            length = 20
            color = self._get_threat_color('high')
            
            # Top-left
            cv2.line(frame, (x1, y1), (x1 + length, y1), color, 3)
            cv2.line(frame, (x1, y1), (x1, y1 + length), color, 3)
            
            # Top-right
            cv2.line(frame, (x2, y1), (x2 - length, y1), color, 3)
            cv2.line(frame, (x2, y1), (x2, y1 + length), color, 3)
            
            # Bottom-left
            cv2.line(frame, (x1, y2), (x1 + length, y2), color, 3)
            cv2.line(frame, (x1, y2), (x1, y2 - length), color, 3)
            
            # Bottom-right
            cv2.line(frame, (x2, y2), (x2 - length, y2), color, 3)
            cv2.line(frame, (x2, y2), (x2, y2 - length), color, 3)
            
        except Exception as e:
            logger.error(f"Error adding threat indicators: {e}")

    def _add_metrics_overlay(self, frame: np.ndarray) -> None:
        """Add performance metrics overlay."""
        try:
            metrics = self._get_performance_metrics()
            
            # Create metrics text
            text_lines = [
                f"FPS: {metrics['fps']:.1f}",
                f"Detection time: {metrics['avg_detection_time']:.3f}s",
                f"Cache hits: {metrics['cache_hits']}"
            ]
            
            # Add text to frame
            y = 30
            for line in text_lines:
                cv2.putText(
                    frame,
                    line,
                    (10, y),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (255, 255, 255),
                    2
                )
                y += 25
                
        except Exception as e:
            logger.error(f"Error adding metrics overlay: {e}")

    def _get_performance_metrics(self) -> Dict:
        """Get current performance metrics."""
        try:
            with self._lock:
                avg_time = (
                    np.mean(self.metrics['detection_times'])
                    if self.metrics['detection_times']
                    else 0
                )
                
                return {
                    'fps': 1 / avg_time if avg_time > 0 else 0,
                    'avg_detection_time': avg_time,
                    'total_frames': self.metrics['total_frames'],
                    'cache_hits': self.metrics['cached_hits'],
                    'model_switches': self.metrics['model_switches']
                }
                
        except Exception as e:
            logger.error(f"Error getting performance metrics: {e}")
            return {}

    def _update_metrics(self, detection_time: float) -> None:
        """Update performance metrics."""
        try:
            with self._lock:
                self.metrics['total_frames'] += 1
                self.metrics['detection_times'].append(detection_time)
                
        except Exception as e:
            logger.error(f"Error updating metrics: {e}")

    def _get_roi(self, frame: np.ndarray, person_box: List[float], weapon_box: List[float]) -> np.ndarray:
        """Get region of interest containing person and weapon."""
        try:
            # Calculate ROI bounds with padding
            padding = 20  # pixels
            x1 = max(0, min(person_box[0], weapon_box[0]) - padding)
            y1 = max(0, min(person_box[1], weapon_box[1]) - padding)
            x2 = min(frame.shape[1], max(person_box[2], weapon_box[2]) + padding)
            y2 = min(frame.shape[0], max(person_box[3], weapon_box[3]) + padding)
            
            return frame[int(y1):int(y2), int(x1):int(x2)]
            
        except Exception as e:
            logger.error(f"ROI extraction error: {e}")
            return frame

    def _get_box_center(self, box: List[float]) -> Tuple[float, float]:
        """Calculate center point of a bounding box."""
        try:
            x1, y1, x2, y2 = box
            return ((x1 + x2) / 2, (y1 + y2) / 2)
        except Exception as e:
            logger.error(f"Box center calculation error: {e}")
            return (0, 0)

    def cleanup(self) -> None:
        """Cleanup resources."""
        try:
            # Clear models
            self.fast_model = None
            self.threat_model = None
            
            # Clear caches
            self.detection_cache = DetectionCache()
            self.threat_trackers.clear()
            
            # Reset motion detector
            self.motion_detector['prev_frame'] = None
            
            logger.info("Object detector cleanup completed")
            
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
    
    