import logging
import os
import numpy as np
import cv2
from ultralytics import YOLO
from typing import List, Dict, Optional, Tuple, Any
import time

'''
This ObjectDetector class handles:

    Loading and managing YOLO models for detection
    Threat classification and assessment
    Object detection and tracking
    Armed person detection with weapon proximity analysis
    Detection visualization
    Size analysis for better accuracy
    Tracking ID generation for object persistence

The class is designed to work with surveillance scenarios and includes specialized detection for:

    Armed persons
    Dangerous animals
    Wildlife
    Livestock
    General person detection
'''

# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if not os.path.exists('logs'):
    os.makedirs('logs')
handler = logging.FileHandler('logs/object_detector.log')
handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

class ObjectDetector:
    def __init__(self):
        """Initialize the object detector with specialized detection models."""
        try:
            logger.info("Initializing Object Detector with specialized models...")
            self.animal_model = self._load_model('yolov8x.pt', "Animal detection model")
            
            # Using same model for both to improve efficiency
            self.weapon_model = self.animal_model
            
            self.target_classes = {
                # High Threat - Big Cats and Predators
                'big_cats': {
                    'threat': 'high',
                    'classes': ['cat', 'tiger', 'teddy bear', 'dog'],
                    'confidence_threshold': 0.3,
                    'remap': {
                        'cat': 'lion',
                        'tiger': 'tiger',
                        'teddy bear': 'leopard',
                        'dog': 'wild dog'
                    }
                },
                
                # Armed Persons - High Threat
                'armed_person': {
                    'threat': 'high',
                    'classes': ['person'],
                    'weapons': [
                        'knife', 'scissors', 'cell phone',  # Common objects that might be weapons
                        'bottle', 'baseball bat', 'remote',
                        'gun', 'rifle', 'pistol'
                    ],
                    'confidence_threshold': 0.35
                },
                
                # Wildlife - Medium Threat
                'wildlife': {
                    'threat': 'medium',
                    'classes': ['elephant', 'bear', 'zebra', 'giraffe'],
                    'confidence_threshold': 0.4
                },
                
                # Livestock - Monitoring
                'livestock': {
                    'threat': 'livestock',
                    'classes': ['cow', 'sheep', 'horse', 'cattle'],
                    'confidence_threshold': 0.5
                },
                
                # Low Threat
                'normal': {
                    'threat': 'low',
                    'classes': ['person'],
                    'confidence_threshold': 0.5
                }
            }
            
            # Detection thresholds
            self.animal_confidence_threshold = 0.3
            self.weapon_confidence_threshold = 0.35
            self.person_confidence_threshold = 0.45
            
            # Build class cache for faster lookups
            self._class_to_category = self._build_class_cache()
            
            logger.info("Object Detector initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Object Detector: {e}")
            self.animal_model = None
            self.weapon_model = None
            raise

    def _load_model(self, model_path: str, model_name: str) -> Optional[YOLO]:
        """Load a YOLO model from the specified path."""
        try:
            logger.info(f"Loading {model_name}")
            model = YOLO(model_path)
            return model
        except Exception as e:
            logger.error(f"Failed to load {model_name}: {e}")
            return None

    def _build_class_cache(self) -> Dict[str, str]:
        """Build a cache mapping class names to their categories."""
        cache = {}
        for category, info in self.target_classes.items():
            for class_name in info['classes']:
                cache[class_name] = category
        return cache

    def _remap_class(self, class_name: str, category: str) -> str:
        """Remap class names based on predefined mappings."""
        category_info = self.target_classes.get(category, {})
        remap_dict = category_info.get('remap', {})
        return remap_dict.get(class_name, class_name)

    def _get_category(self, class_name: str) -> str:
        """Get the category for a given class name."""
        return self._class_to_category.get(class_name, 'unknown')

    def _check_for_nearby_weapons(self, person_box: List[float], weapon_boxes: List[Dict]) -> Tuple[bool, List[str]]:
        """Check if any weapons are near a detected person."""
        if not weapon_boxes:
            return False, []
            
        try:
            px1, py1, px2, py2 = person_box
            person_center = ((px1 + px2) / 2, (py1 + py2) / 2)
            person_area = (px2 - px1) * (py2 - py1)
            
            nearby_weapons = []
            
            for weapon in weapon_boxes:
                wx1, wy1, wx2, wy2 = weapon['box']
                weapon_center = ((wx1 + wx2) / 2, (wy1 + wy2) / 2)
                weapon_area = (wx2 - wx1) * (wy2 - wy1)
                
                # Calculate relative distance based on person size
                distance_threshold = np.sqrt(person_area) * 0.8
                distance = np.sqrt(
                    (person_center[0] - weapon_center[0])**2 + 
                    (person_center[1] - weapon_center[1])**2
                )
                
                # Check if weapon is close enough and reasonable size
                if (distance < distance_threshold and 
                    weapon_area < person_area * 0.5):  # Weapon shouldn't be too large
                    nearby_weapons.append(weapon['class'])
            
            return len(nearby_weapons) > 0, nearby_weapons
            
        except Exception as e:
            logger.error(f"Error in weapon proximity check: {e}")
            return False, []

    def detect_objects(self, frame: np.ndarray) -> List[Dict]:
        """Detect objects in the given frame."""
        if not self._check_models():
            return []
            
        try:
            detections = []
            frame_size = frame.shape[:2]
            
            # Get all detections in one pass for efficiency
            results = self.animal_model(frame)
            
            # First pass: collect all potential weapons
            weapon_detections = []
            for result in results:
                for box in result.boxes:
                    cls = int(box.cls[0])
                    conf = float(box.conf[0])
                    class_name = self.animal_model.names[cls]
                    
                    if (class_name in self.target_classes['armed_person']['weapons'] and 
                        conf > self.weapon_confidence_threshold):
                        weapon_detections.append({
                            'box': box.xyxy[0].tolist(),
                            'class': class_name,
                            'confidence': conf
                        })
            
            # Second pass: process all detections
            for result in results:
                for box in result.boxes:
                    cls = int(box.cls[0])
                    conf = float(box.conf[0])
                    class_name = self.animal_model.names[cls]
                    
                    # Get initial category
                    category = self._get_category(class_name)
                    
                    # Handle special cases
                    if category == 'big_cats':
                        bbox = box.xyxy[0].tolist()
                        detection_area = self._analyze_detection_size(bbox, frame_size)
                        
                        if detection_area > 0.01:  # Size threshold
                            class_name = self._remap_class(class_name, category)
                    
                    # Enhanced armed person detection
                    elif class_name == 'person':
                        person_box = box.xyxy[0].tolist()
                        is_armed, nearby_weapons = self._check_for_nearby_weapons(person_box, weapon_detections)
                        
                        if is_armed:
                            detections.append({
                                'class': 'armed_person',
                                'confidence': conf,
                                'box': person_box,
                                'threat_level': 'high',
                                'weapons': nearby_weapons,
                                'timestamp': time.time(),
                                'track_id': self._generate_track_id(person_box)
                            })
                            continue
                    
                    # Process other detections
                    threshold = self.target_classes.get(category, {}).get(
                        'confidence_threshold', self.animal_confidence_threshold)
                    
                    if conf > threshold:
                        threat_level = 'high' if category == 'big_cats' else \
                                     self.target_classes.get(category, {}).get('threat', 'unknown')
                        
                        detection = {
                            'class': class_name,
                            'confidence': conf,
                            'box': box.xyxy[0].tolist(),
                            'threat_level': threat_level,
                            'timestamp': time.time(),
                            'track_id': self._generate_track_id(box.xyxy[0].tolist())
                        }
                        detections.append(detection)
            
            return detections
            
        except Exception as e:
            logger.error(f"Error in object detection: {e}")
            return []

    def draw_detections(self, frame: np.ndarray, detections: List[Dict]) -> np.ndarray:
        """Draw detection boxes and labels on the frame."""
        try:
            frame_copy = frame.copy()
            
            for det in detections:
                box = det['box']
                x1, y1, x2, y2 = map(int, box)
                
                # Color scheme based on threat level
                color = {
                    'high': (0, 0, 255),      # Red (BGR)
                    'medium': (0, 165, 255),   # Orange
                    'low': (0, 255, 0),        # Green
                    'livestock': (255, 255, 0), # Cyan
                    'unknown': (128, 128, 128)  # Gray
                }[det['threat_level']]
                
                # Thicker boxes for high threats
                thickness = 3 if det['threat_level'] == 'high' else 2
                
                # Draw box
                cv2.rectangle(frame_copy, (x1, y1), (x2, y2), color, thickness)
                
                # Enhanced label for armed persons
                if det['class'] == 'armed_person':
                    weapons = det.get('weapons', [])
                    weapon_str = ', '.join(weapons) if weapons else 'weapon'
                    label = f"⚠️ ARMED PERSON with {weapon_str}"
                else:
                    conf_str = f"{det['confidence']:.2f}"
                    label = f"{det['class']} ({conf_str})"
                
                # Draw label with background
                (label_w, label_h), _ = cv2.getTextSize(
                    label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
                cv2.rectangle(
                    frame_copy,
                    (x1, y1-label_h-10),
                    (x1+label_w, y1),
                    color,
                    -1
                )
                
                # Draw label text
                cv2.putText(
                    frame_copy,
                    label,
                    (x1, y1-10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (255, 255, 255),
                    2
                )
            
            return frame_copy
            
        except Exception as e:
            logger.error(f"Error drawing detections: {e}")
            return frame

    def _check_models(self) -> bool:
        """Verify model availability."""
        if self.animal_model is None:
            logger.error("Models not properly initialized")
            return False
        return True

    def _analyze_detection_size(self, box: List[float], frame_size: Tuple[int, int]) -> float:
        """Calculate relative size of detection."""
        try:
            x1, y1, x2, y2 = box
            detection_area = (x2 - x1) * (y2 - y1)
            frame_area = frame_size[0] * frame_size[1]
            return detection_area / frame_area
        except Exception as e:
            logger.error(f"Error analyzing detection size: {e}")
            return 0.0

    def _generate_track_id(self, box: List[float]) -> str:
        """Generate a unique tracking ID based on detection position."""
        try:
            x1, y1, x2, y2 = box
            center_x = (x1 + x2) / 2
            center_y = (y1 + y2) / 2
            return f"track_{int(center_x)}_{int(center_y)}_{int(time.time())}"
        except Exception as e:
            logger.error(f"Error generating track ID: {e}")
            return f"track_error_{int(time.time())}"