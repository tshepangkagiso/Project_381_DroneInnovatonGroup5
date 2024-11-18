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

class DetectionCache:
    """Cache for recent detections with thread-safe operations."""
    
    def __init__(self, max_size: int = 100, ttl: float = 1.0):
        self.max_size = max_size
        self.ttl = ttl
        self.cache = {}
        self.lock = threading.Lock()
        self.last_cleanup = time.time()
    
    def add(self, key: str, detection: Dict) -> None:
        try:
            with self.lock:
                if 'timestamp' not in detection:
                    detection['timestamp'] = time.time()
                self.cache[key] = detection
                if len(self.cache) > self.max_size:
                    self._cleanup()
        except Exception as e:
            logger.error(f"Cache addition error: {e}")
    
    def get(self, key: str) -> Optional[Dict]:
        try:
            with self.lock:
                if key not in self.cache:
                    return None
                
                entry = self.cache[key]
                current_time = time.time()
                
                if current_time - entry.get('timestamp', 0) > self.ttl:
                    del self.cache[key]
                    return None
                
                if current_time - self.last_cleanup > self.ttl * 2:
                    self._cleanup()
                
                return entry
        except Exception as e:
            logger.error(f"Cache retrieval error: {e}")
            return None
    
    def _cleanup(self) -> None:
        try:
            current_time = time.time()
            expired = [
                key for key, value in self.cache.items()
                if current_time - value.get('timestamp', 0) > self.ttl
            ]
            for key in expired:
                del self.cache[key]
            self.last_cleanup = current_time
        except Exception as e:
            logger.error(f"Cache cleanup error: {e}")
    
    def clear(self) -> None:
        try:
            with self.lock:
                self.cache.clear()
                self.last_cleanup = time.time()
        except Exception as e:
            logger.error(f"Cache clear error: {e}")

class DetectionCategories:
    """Classification system for farm security threats."""
    
    LOW_THREATS = {
        'person': {'threshold': 0.3, 'description': 'Single person'},
        'people': {'threshold': 0.3, 'description': 'Group of people'},
        'cow': {'threshold': 0.3, 'description': 'Cattle'},
        'sheep': {'threshold': 0.3, 'description': 'Sheep'},
        'goat': {'threshold': 0.3, 'description': 'Goat'},
        'dog': {'threshold': 0.3, 'description': 'Domestic dog'},
        'cat': {'threshold': 0.3, 'description': 'Domestic cat'},
        'bird': {'threshold': 0.3, 'description': 'Bird'},
        'horse': {'threshold': 0.3, 'description': 'Horse'}
    }
    
    MEDIUM_THREATS = {
        'zebra': {'threshold': 0.35, 'description': 'Zebra'},
        'giraffe': {'threshold': 0.35, 'description': 'Giraffe'},
        'antelope': {'threshold': 0.35, 'description': 'Antelope'},
        'warthog': {'threshold': 0.35, 'description': 'Warthog'},
        'baboon': {'threshold': 0.4, 'description': 'Baboon'},
        'monkey': {'threshold': 0.4, 'description': 'Monkey'},
        'wildebeest': {'threshold': 0.35, 'description': 'Wildebeest'}
    }
    
    HIGH_THREATS = {
        'person with weapon': {'threshold': 0.45, 'description': 'Armed person'},
        'armed group': {'threshold': 0.45, 'description': 'Armed group'},
        'lion': {'threshold': 0.4, 'description': 'Lion'},
        'leopard': {'threshold': 0.4, 'description': 'Leopard'},
        'elephant': {'threshold': 0.4, 'description': 'Elephant'},
        'rhinoceros': {'threshold': 0.4, 'description': 'Rhinoceros'},
        'buffalo': {'threshold': 0.4, 'description': 'Cape Buffalo'},
        'hyena': {'threshold': 0.4, 'description': 'Hyena'},
        'cheetah': {'threshold': 0.4, 'description': 'Cheetah'}
    }
    
    WEAPONS = {
        'knife': {'threshold': 0.45},
        'gun': {'threshold': 0.45},
        'rifle': {'threshold': 0.45},
        'pistol': {'threshold': 0.45}
    }
    
    @classmethod
    def get_threat_level(cls, class_name: str) -> str:
        if class_name in cls.HIGH_THREATS:
            return 'high'
        elif class_name in cls.MEDIUM_THREATS:
            return 'medium'
        elif class_name in cls.LOW_THREATS:
            return 'low'
        return 'unknown'
    
    @classmethod
    def get_threshold(cls, class_name: str) -> float:
        for category in [cls.HIGH_THREATS, cls.MEDIUM_THREATS, cls.LOW_THREATS, cls.WEAPONS]:
            if class_name in category:
                return category[class_name]['threshold']
        return 0.3

class ThreatTracker:
    """Track threats across frames with confidence weighting."""
    
    def __init__(self, history_size: int = 5):
        self.history = deque(maxlen=history_size)
        self.threat_confidence = 0.0
        self.threat_level = 'low'
        self.last_update = time.time()
        self.lock = threading.Lock()
        self.consecutive_detections = 0
    
    def update(self, detection: Dict) -> None:
        with self.lock:
            self.history.append(detection)
            self.threat_confidence = self._calculate_confidence()
            self.threat_level = detection.get('threat_level', 'low')
            self.last_update = time.time()
            
            if len(self.history) >= 3:
                recent_levels = [d.get('threat_level') for d in list(self.history)[-3:]]
                if all(level == self.threat_level for level in recent_levels):
                    self.consecutive_detections += 1
                else:
                    self.consecutive_detections = 0
    
    def _calculate_confidence(self) -> float:
        if not self.history:
            return 0.0
        weights = np.linspace(0.5, 1.0, len(self.history))
        confidences = [det.get('confidence', 0) for det in self.history]
        confidence = np.average(confidences, weights=weights)
        if self.consecutive_detections >= 3:
            confidence *= 1.2
        return min(confidence, 1.0)

class ObjectDetector:
    """Single-model object detector optimized for farm security."""
    
    def __init__(self):
        try:
            logger.info("Initializing Farm Security Object Detector...")
            
            # Initialize models directory
            self.models_dir = Path("models/weights")
            self.models_dir.mkdir(parents=True, exist_ok=True)
            
            # Load categories and single model
            self.categories = DetectionCategories
            self.model = self._load_or_download_model('yolov8m', "Primary detection model")
            
            # Initialize components
            self._init_detection_settings()
            self._lock = threading.Lock()
            self.detection_cache = DetectionCache()
            self.threat_trackers = {}
            self.motion_detector = self._init_motion_detector()
            self._init_metrics()
            
            logger.info("Farm Security Object Detector initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Object Detector: {e}")
            raise

    def _init_detection_settings(self) -> None:
        self.settings = {
            'detection': {
                'conf_threshold': 0.3,
                'iou_threshold': 0.45,
                'max_det': 50
            },
            'group_detection': {
                'proximity_threshold': 100,
                'min_group_size': 3
            },
            'armed_detection': {
                'proximity_threshold': 50,
                'confidence_threshold': 0.4
            },
            'animal_detection': {
                'movement_threshold': 50,
                'species_confidence': 0.35
            },
            'processing': {
                'max_frame_size': (640, 640),
                'target_fps': 30
            }
        }

    def _init_motion_detector(self) -> Dict:
        return {
            'prev_frame': None,
            'min_area': 500,
            'blur_size': (21, 21),
            'threshold': 25,
            'dilate_iter': 2
        }

    def _init_metrics(self) -> None:
        self.metrics = {
            'start_time': time.time(),
            'total_frames': 0,
            'detection_times': deque(maxlen=100),
            'high_threats': 0,
            'medium_threats': 0,
            'low_threats': 0,
            'cached_hits': 0
        }

    def _load_or_download_model(self, model_name: str, description: str) -> Optional[YOLO]:
        try:
            logger.info(f"Loading {description} ({model_name})...")
            model_path = self.models_dir / f"{model_name}.pt"
            
            if not model_path.exists():
                logger.info(f"Downloading {model_name} model...")
                model = YOLO(f"{model_name}.pt")
                model.save(str(model_path))
                logger.info(f"Model downloaded and saved to {model_path}")
            
            model = YOLO(str(model_path))
            logger.info(f"Successfully loaded {description}")
            return model
            
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            return None

    def detect_objects(self, frame: np.ndarray) -> List[Dict]:
        """Main detection method."""
        try:
            start_time = time.time()
            
            if frame is None or frame.size == 0:
                return []
            
            # Process frame
            frame = self._preprocess_frame(frame)
            if not self._check_motion(frame):
                return self.last_detections if hasattr(self, 'last_detections') else []
            
            # Run detection
            results = self.model(
                frame,
                conf=self.settings['detection']['conf_threshold'],
                iou=self.settings['detection']['iou_threshold'],
                max_det=self.settings['detection']['max_det']
            )
            
            # Process detections
            detections = []
            for result in results:
                for box in result.boxes:
                    detection = self._create_detection(box, frame.shape[:2])
                    if detection and self._is_valid_detection(detection):
                        detections.append(detection)
            
            # Analyze threats
            detections = self._analyze_threats(frame, detections)
            
            # Update metrics
            self._update_metrics(time.time() - start_time)
            
            self.last_detections = detections
            return detections
            
        except Exception as e:
            logger.error(f"Detection error: {e}")
            return []

    def _preprocess_frame(self, frame: np.ndarray) -> np.ndarray:
        try:
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
        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, self.motion_detector['blur_size'], 0)
            
            if self.motion_detector['prev_frame'] is None:
                self.motion_detector['prev_frame'] = gray
                return True
            
            frame_delta = cv2.absdiff(self.motion_detector['prev_frame'], gray)
            thresh = cv2.threshold(frame_delta, self.motion_detector['threshold'], 
                                 255, cv2.THRESH_BINARY)[1]
            thresh = cv2.dilate(thresh, None, 
                              iterations=self.motion_detector['dilate_iter'])
            
            contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, 
                                         cv2.CHAIN_APPROX_SIMPLE)
            
            self.motion_detector['prev_frame'] = gray
            
            return any(cv2.contourArea(c) > self.motion_detector['min_area'] 
                      for c in contours)
            
        except Exception as e:
            logger.error(f"Motion detection error: {e}")
            return True

    def _create_detection(self, box, image_shape: Tuple[int, int]) -> Optional[Dict]:
        try:
            cls = int(box.cls[0])
            conf = float(box.conf[0])
            class_name = self.model.names[cls]
            
            xyxy = box.xyxy[0].cpu().numpy()
            x1, y1, x2, y2 = map(float, xyxy)
            
            height, width = image_shape
            x1 = max(0, min(x1, width))
            x2 = max(0, min(x2, width))
            y1 = max(0, min(y1, height))
            y2 = max(0, min(y2, height))
            
            detection = {
                'id': f"{class_name}_{int(time.time()*1000)}",
                'class': class_name,
                'confidence': conf,
                'box': [x1, y1, x2, y2],
                'center': ((x1 + x2) / 2, (y1 + y2) / 2),
                'area': (x2 - x1) * (y2 - y1),
                'timestamp': time.time(),
                'threat_level': self.categories.get_threat_level(class_name)
            }
            
            return detection
            
        except Exception as e:
            logger.error(f"Detection creation error: {e}")
            return None

    def _is_valid_detection(self, detection: Dict) -> bool:
        try:
            if not all(key in detection for key in ['id', 'class', 'confidence', 'box']):
                return False
            
            if not (isinstance(detection['confidence'], (int, float)) and 
                   0 <= detection['confidence'] <= 1):
                return False
            
            if not (isinstance(detection['box'], (list, tuple)) and 
                   len(detection['box']) == 4 and
                   all(isinstance(x, (int, float)) for x in detection['box'])):
                return False
            
            x1, y1, x2, y2 = detection['box']
            if x1 >= x2 or y1 >= y2:
                return False
            
            threshold = self.categories.get_threshold(detection['class'])
            if detection['confidence'] < threshold:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Detection validation error: {e}")
            return False

    def _analyze_threats(self, frame: np.ndarray, detections: List[Dict]) -> List[Dict]:
        """Analyze and classify all threats in the frame."""
        try:
            # Group people detections
            people = [d for d in detections if d['class'] == 'person']
            if len(people) >= self.settings['group_detection']['min_group_size']:
                groups = self._detect_groups(people)
                detections.extend(groups)
            
            # Analyze armed threats
            weapons = [d for d in detections if d['class'] in self.categories.WEAPONS]
            if people and weapons:
                armed_threats = self._detect_armed_threats(people, weapons)
                detections.extend(armed_threats)
            
            # Analyze animal threats
            animals = [d for d in detections if d['class'] in 
                      {**self.categories.HIGH_THREATS, **self.categories.MEDIUM_THREATS}]
            if animals:
                animal_threats = self._analyze_animal_threats(animals)
                detections.extend(animal_threats)
            
            return detections
            
        except Exception as e:
            logger.error(f"Threat analysis error: {e}")
            return detections

    def _detect_groups(self, people: List[Dict]) -> List[Dict]:
        """Detect and classify groups of people."""
        try:
            groups = []
            processed = set()
            
            for i, person in enumerate(people):
                if i in processed:
                    continue
                
                group_members = [person]
                center = person['center']
                
                for j, other in enumerate(people[i+1:], i+1):
                    if j not in processed:
                        distance = np.sqrt(
                            (center[0] - other['center'][0])**2 +
                            (center[1] - other['center'][1])**2
                        )
                        if distance <= self.settings['group_detection']['proximity_threshold']:
                            group_members.append(other)
                            processed.add(j)
                
                if len(group_members) >= self.settings['group_detection']['min_group_size']:
                    group = self._create_group_detection(group_members)
                    if group:
                        groups.append(group)
                        processed.add(i)
            
            return groups
            
        except Exception as e:
            logger.error(f"Group detection error: {e}")
            return []

    def _create_group_detection(self, members: List[Dict]) -> Optional[Dict]:
        """Create group detection from members."""
        try:
            x1 = min(m['box'][0] for m in members)
            y1 = min(m['box'][1] for m in members)
            x2 = max(m['box'][2] for m in members)
            y2 = max(m['box'][3] for m in members)
            
            confidence = np.mean([m['confidence'] for m in members])
            
            return {
                'id': f"group_{int(time.time()*1000)}",
                'class': 'people',
                'confidence': confidence,
                'box': [x1, y1, x2, y2],
                'center': ((x1 + x2) / 2, (y1 + y2) / 2),
                'threat_level': 'low',
                'member_count': len(members),
                'timestamp': time.time()
            }
            
        except Exception as e:
            logger.error(f"Group creation error: {e}")
            return None

    def _detect_armed_threats(self, people: List[Dict], weapons: List[Dict]) -> List[Dict]:
        """Detect armed threats by analyzing person-weapon proximity."""
        try:
            armed_threats = []
            
            for person in people:
                person_center = person['center']
                nearby_weapons = []
                
                for weapon in weapons:
                    distance = np.sqrt(
                        (person_center[0] - weapon['center'][0])**2 +
                        (person_center[1] - weapon['center'][1])**2
                    )
                    if distance <= self.settings['armed_detection']['proximity_threshold']:
                        nearby_weapons.append(weapon)
                
                if nearby_weapons:
                    threat = self._create_armed_threat(person, nearby_weapons)
                    if threat:
                        armed_threats.append(threat)
            
            return armed_threats
            
        except Exception as e:
            logger.error(f"Armed threat detection error: {e}")
            return []

    def _create_armed_threat(self, person: Dict, weapons: List[Dict]) -> Optional[Dict]:
        """Create armed threat detection."""
        try:
            x1 = min(person['box'][0], min(w['box'][0] for w in weapons))
            y1 = min(person['box'][1], min(w['box'][1] for w in weapons))
            x2 = max(person['box'][2], max(w['box'][2] for w in weapons))
            y2 = max(person['box'][3], max(w['box'][3] for w in weapons))
            
            weapon_conf = max(w['confidence'] for w in weapons)
            confidence = np.sqrt(person['confidence'] * weapon_conf)
            
            threat = {
                'id': f"armed_{person['id']}_{int(time.time()*1000)}",
                'class': 'person with weapon',
                'confidence': confidence,
                'box': [x1, y1, x2, y2],
                'center': ((x1 + x2) / 2, (y1 + y2) / 2),
                'threat_level': 'high',
                'weapon_types': [w['class'] for w in weapons],
                'person': person,
                'weapons': weapons,
                'timestamp': time.time()
            }
            
            tracker_id = f"armed_{person['id']}"
            if tracker_id not in self.threat_trackers:
                self.threat_trackers[tracker_id] = ThreatTracker()
            self.threat_trackers[tracker_id].update(threat)
            
            return threat
            
        except Exception as e:
            logger.error(f"Armed threat creation error: {e}")
            return None

    def _analyze_animal_threats(self, animals: List[Dict]) -> List[Dict]:
        """Analyze and classify animal threats."""
        try:
            animal_threats = []
            
            for animal in animals:
                if 'threat_verified' in animal:
                    animal_threats.append(animal)
                    continue
                
                cache_key = f"animal_{animal['id']}"
                cached = self.detection_cache.get(cache_key)
                if cached:
                    animal.update(cached)
                    animal_threats.append(animal)
                    continue
                
                threat_level = self.categories.get_threat_level(animal['class'])
                if threat_level in ['medium', 'high']:
                    analysis = self._analyze_single_animal(animal)
                    if analysis:
                        animal.update(analysis)
                        animal_threats.append(animal)
                        self.detection_cache.add(cache_key, analysis)
            
            return animal_threats
            
        except Exception as e:
            logger.error(f"Animal threat analysis error: {e}")
            return []

    def _analyze_single_animal(self, animal: Dict) -> Dict:
        """Analyze individual animal threat."""
        try:
            analysis = {
                'threat_verified': True,
                'threat_level': self.categories.get_threat_level(animal['class']),
                'behavior_indicators': [],
                'risk_factors': []
            }
            
            if animal['class'] in self.categories.HIGH_THREATS:
                analysis['risk_factors'].extend([
                    'dangerous_species',
                    'potential_aggression'
                ])
                analysis['priority'] = 'immediate'
                
            elif animal['class'] in self.categories.MEDIUM_THREATS:
                analysis['risk_factors'].extend([
                    'wild_animal',
                    'unpredictable_behavior'
                ])
                analysis['priority'] = 'moderate'
            
            area = (animal['box'][2] - animal['box'][0]) * (animal['box'][3] - animal['box'][1])
            if area > 10000:
                analysis['risk_factors'].append('large_size')
            
            analysis['confidence'] = min(animal['confidence'] * 1.2, 1.0)
            
            return analysis
            
        except Exception as e:
            logger.error(f"Animal analysis error: {e}")
            return {
                'threat_verified': False,
                'threat_level': self.categories.get_threat_level(animal['class']),
                'confidence': animal['confidence']
            }

    def draw_detections(self, frame: np.ndarray, detections: List[Dict]) -> np.ndarray:
        """Draw detections with threat-level visualization."""
        try:
            frame_copy = frame.copy()
            
            # Sort by threat level for layered drawing
            detections = sorted(
                detections,
                key=lambda x: (
                    {'high': 3, 'medium': 2, 'low': 1, 'unknown': 0}[x.get('threat_level', 'unknown')],
                    x.get('confidence', 0)
                ),
                reverse=True
            )
            
            # Draw each detection
            for det in detections:
                self._draw_single_detection(frame_copy, det)
            
            # Add security overlay
            self._add_security_overlay(frame_copy, detections)
            
            return frame_copy
            
        except Exception as e:
            logger.error(f"Detection visualization error: {e}")
            return frame

    def _draw_single_detection(self, frame: np.ndarray, det: Dict) -> None:
        """Draw single detection with enhanced visualization."""
        try:
            x1, y1, x2, y2 = map(int, det['box'])
            color = self._get_threat_color(det)
            thickness = 3 if det.get('threat_level') == 'high' else 2
            
            # Draw main box
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)
            
            # Create and draw label
            label = self._create_security_label(det)
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
            
            cv2.putText(
                frame,
                label,
                (x1, y1 - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                2
            )
            
            # Add threat-specific visualizations
            if det.get('threat_level') == 'high':
                self._add_threat_indicators(frame, det)
                
            if det.get('class') == 'person with weapon':
                self._add_armed_threat_visualization(frame, det)
            elif det.get('class') == 'people':
                self._add_group_visualization(frame, det)
                
        except Exception as e:
            logger.error(f"Detection drawing error: {e}")

    def _get_threat_color(self, det: Dict) -> Tuple[int, int, int]:
        """Get color based on threat level."""
        colors = {
            'high': (0, 0, 255),     # Red
            'medium': (0, 165, 255),  # Orange
            'low': (0, 255, 0),       # Green
            'unknown': (128, 128, 128) # Gray
        }
        return colors.get(det.get('threat_level', 'unknown'), colors['unknown'])

    def _create_security_label(self, det: Dict) -> str:
        """Create detailed security-focused label."""
        try:
            base_label = det['class'].replace('_', ' ').title()
            
            if det.get('class') == 'person with weapon':
                weapons = ', '.join(det.get('weapon_types', []))
                base_label = f"⚠️ ARMED ({weapons})"
            elif det.get('class') == 'people':
                base_label = f"Group ({det.get('member_count', 0)})"
            
            conf_str = f"{det.get('confidence', 0):.2f}"
            
            if det.get('threat_level') == 'high':
                return f"❗{base_label} {conf_str}"
            elif det.get('threat_level') == 'medium':
                return f"⚠️{base_label} {conf_str}"
            else:
                return f"{base_label} {conf_str}"
                
        except Exception as e:
            logger.error(f"Label creation error: {e}")
            return "Unknown"

    def _add_security_overlay(self, frame: np.ndarray, detections: List[Dict]) -> None:
        """Add security information overlay."""
        try:
            # Count threats by level
            threat_counts = {
                'high': len([d for d in detections if d.get('threat_level') == 'high']),
                'medium': len([d for d in detections if d.get('threat_level') == 'medium']),
                'low': len([d for d in detections if d.get('threat_level') == 'low'])
            }
            
            # Create overlay text
            text_lines = [
                f"High Threats: {threat_counts['high']}",
                f"Medium Threats: {threat_counts['medium']}",
                f"Low Threats: {threat_counts['low']}",
                f"FPS: {1.0/np.mean(self.metrics['detection_times']):.1f}" if self.metrics['detection_times'] else "FPS: --"
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
            logger.error(f"Security overlay error: {e}")

    def _add_threat_indicators(self, frame: np.ndarray, det: Dict) -> None:
        """Add visual indicators for high-threat detections."""
        try:
            x1, y1, x2, y2 = map(int, det['box'])
            color = self._get_threat_color(det)
            
            # Corner indicators
            length = 20
            thickness = 3
            
            # Draw corner brackets
            corners = [
                [(x1, y1), (x1 + length, y1), (x1, y1), (x1, y1 + length)],
                [(x2 - length, y1), (x2, y1), (x2, y1), (x2, y1 + length)],
                [(x1, y2 - length), (x1, y2), (x1, y2), (x1 + length, y2)],
                [(x2 - length, y2), (x2, y2), (x2, y2 - length), (x2, y2)]
            ]
            
            for c1, c2, c3, c4 in corners:
                cv2.line(frame, c1, c2, color, thickness)
                cv2.line(frame, c3, c4, color, thickness)
                
        except Exception as e:
            logger.error(f"Threat indicator error: {e}")

    def _add_armed_threat_visualization(self, frame: np.ndarray, det: Dict) -> None:
        """Add specific visualization for armed threats."""
        try:
            person = det.get('person', {})
            weapons = det.get('weapons', [])
            
            if person and weapons:
                person_center = person.get('center', (0, 0))
                
                for weapon in weapons:
                    weapon_center = weapon.get('center', (0, 0))
                    
                    # Draw dashed line connecting person to weapon
                    pt1 = (int(person_center[0]), int(person_center[1]))
                    pt2 = (int(weapon_center[0]), int(weapon_center[1]))
                    
                    # Create dashed line effect
                    dist = np.sqrt(
                        (pt2[0] - pt1[0])**2 + 
                        (pt2[1] - pt1[1])**2
                    )
                    dash_length = 10
                    dashes = int(dist / dash_length)
                    
                    for i in range(dashes):
                        x1 = int(pt1[0] + (pt2[0] - pt1[0]) * i / dashes)
                        y1 = int(pt1[1] + (pt2[1] - pt1[1]) * i / dashes)
                        x2 = int(pt1[0] + (pt2[0] - pt1[0]) * (i + 0.5) / dashes)
                        y2 = int(pt1[1] + (pt2[1] - pt1[1]) * (i + 0.5) / dashes)
                        
                        cv2.line(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                    
                    # Add weapon label
                    weapon_label = f"{weapon['class']} ({weapon['confidence']:.2f})"
                    cv2.putText(
                        frame,
                        weapon_label,
                        (int(weapon_center[0]), int(weapon_center[1] - 10)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (0, 0, 255),
                        2
                    )
            
            # Add alert box
            self._add_alert_box(frame, det)
            
        except Exception as e:
            logger.error(f"Armed threat visualization error: {e}")

    def _add_alert_box(self, frame: np.ndarray, det: Dict) -> None:
        """Add prominent alert box for high-priority threats."""
        try:
            height, width = frame.shape[:2]
            box_height = 60
            margin = 10
            
            # Draw semi-transparent background
            overlay = frame.copy()
            cv2.rectangle(
                overlay,
                (margin, margin),
                (width - margin, margin + box_height),
                (0, 0, 255),
                -1
            )
            
            # Apply transparency
            alpha = 0.7
            cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
            
            # Add alert text
            alert_text = f"⚠️ HIGH THREAT DETECTED: {det['class'].upper()}"
            cv2.putText(
                frame,
                alert_text,
                (margin + 10, margin + 35),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0,
                (255, 255, 255),
                2
            )
            
        except Exception as e:
            logger.error(f"Alert box creation error: {e}")

    def _add_group_visualization(self, frame: np.ndarray, det: Dict) -> None:
        """Add visualization for group detections."""
        try:
            x1, y1, x2, y2 = map(int, det['box'])
            
            # Draw group boundary
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 255), 2)
            
            # Add group size indicator
            count_text = f"Group Size: {det.get('member_count', 0)}"
            cv2.putText(
                frame,
                count_text,
                (x1, y1 - 25),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 255),
                2
            )
            
        except Exception as e:
            logger.error(f"Group visualization error: {e}")

    def cleanup(self) -> None:
        """Cleanup detector resources."""
        try:
            logger.info("Cleaning up Object Detector resources")
            
            self.model = None
            self.detection_cache.clear()
            self.threat_trackers.clear()
            self.motion_detector['prev_frame'] = None
            self._init_metrics()
            
            logger.info("Object Detector cleanup completed")
            
        except Exception as e:
            logger.error(f"Cleanup error: {e}")

    def get_metrics(self) -> Dict:
        """Get detection performance metrics."""
        try:
            with self._lock:
                return {
                    'detection_rate': len(self.metrics['detection_times']) / 
                                    max(time.time() - self.metrics['start_time'], 1),
                    'avg_detection_time': np.mean(self.metrics['detection_times']) 
                                        if self.metrics['detection_times'] else 0,
                    'total_detections': self.metrics['total_frames'],
                    'threat_counts': {
                        'high': self.metrics['high_threats'],
                        'medium': self.metrics['medium_threats'],
                        'low': self.metrics['low_threats']
                    },
                    'cache_hits': self.metrics['cached_hits']
                }
                
        except Exception as e:
            logger.error(f"Error getting metrics: {e}")
            return {}

    def update_settings(self, settings: Dict) -> bool:
        """Update detector settings."""
        try:
            with self._lock:
                if 'detection' in settings:
                    self.settings['detection'].update(settings['detection'])
                
                if 'processing' in settings:
                    self.settings['processing'].update(settings['processing'])
                
                if 'threats' in settings:
                    self.settings['armed_detection'].update(settings['threats'])
                    self.settings['group_detection'].update(settings['threats'])
                
                logger.info("Detection settings updated successfully")
                return True
                
        except Exception as e:
            logger.error(f"Settings update error: {e}")
            return False

    def _update_metrics(self, detection_time: float) -> None:
        """Update performance metrics."""
        try:
            with self._lock:
                self.metrics['total_frames'] += 1
                self.metrics['detection_times'].append(detection_time)
                
        except Exception as e:
            logger.error(f"Metrics update error: {e}")