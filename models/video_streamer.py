import cv2
import threading
import time
import logging
import os
import numpy as np
from base64 import b64encode
from typing import Optional, Dict
from .object_detector import ObjectDetector

'''
This VideoStreamer class handles:

    Real-time video streaming from the drone
    Frame processing and object detection integration
    Performance monitoring (FPS, processing times)
    Frame buffering for smooth streaming
    Object tracking and movement detection
    Real-time alerts for high-threat detections
    WebSocket communication for streaming and alerts

Key features include:

    Adaptive frame rate control
    Performance monitoring and metrics
    Object tracking history
    Movement detection for tracked objects
    Buffer management for smooth streaming
    Real-time threat alerts
'''

# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if not os.path.exists('logs'):
    os.makedirs('logs')
handler = logging.FileHandler('logs/video_streamer.log')
handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

class VideoStreamer:
    def __init__(self, socketio):
        """Initialize video streamer with SocketIO for real-time streaming."""
        self.socketio = socketio
        self.streaming = False
        self.frame_size = (640, 480)
        self._lock = threading.Lock()
        self.stream_thread = None
        self.detector = ObjectDetector()
        
        # Performance monitoring
        self.frame_counter = 0
        self.last_fps_time = time.time()
        self.fps = 0
        self.processing_times = []
        
        # Frame buffer for smooth streaming
        self.frame_buffer_size = 5
        self.frame_buffer = []
        
        # Detection history for tracking
        self.detection_history = {}
        self.history_max_age = 5.0  # seconds
        
        logger.info("VideoStreamer initialized")

    def get_frame(self, drone) -> Optional[np.ndarray]:
        """Get a frame from the drone's video feed."""
        try:
            frame_read = drone.get_frame_read()
            if frame_read and frame_read.frame is not None:
                frame = frame_read.frame
                return cv2.resize(frame, self.frame_size)
            return None
        except Exception as e:
            logger.error(f"Error getting frame: {e}")
            return None

    def encode_frame(self, frame: np.ndarray) -> Optional[str]:
        """Encode frame to JPEG format for streaming."""
        try:
            # Apply quality reduction for better streaming performance
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 60]
            _, buffer = cv2.imencode('.jpg', frame, encode_param)
            return b64encode(buffer).decode('utf-8')
        except Exception as e:
            logger.error(f"Error encoding frame: {e}")
            return None

    def calculate_fps(self) -> float:
        """Calculate current FPS."""
        self.frame_counter += 1
        current_time = time.time()
        time_diff = current_time - self.last_fps_time
        
        if time_diff >= 1.0:
            self.fps = self.frame_counter / time_diff
            self.frame_counter = 0
            self.last_fps_time = current_time
            
        return self.fps

    def update_detection_history(self, detections: list):
        """Update detection history for object tracking."""
        current_time = time.time()
        
        # Update current detections
        for detection in detections:
            track_id = detection.get('track_id')
            if track_id:
                self.detection_history[track_id] = {
                    'last_seen': current_time,
                    'detection': detection
                }
        
        # Remove old detections
        self.detection_history = {
            k: v for k, v in self.detection_history.items()
            if current_time - v['last_seen'] < self.history_max_age
        }

    def calculate_movement(self, detection: Dict) -> Optional[Dict]:
        """Calculate object movement based on detection history."""
        try:
            track_id = detection.get('track_id')
            if not track_id or track_id not in self.detection_history:
                return None
            
            current_box = detection['box']
            previous_detection = self.detection_history[track_id]['detection']
            previous_box = previous_detection['box']
            
            # Calculate center points
            current_center = [(current_box[0] + current_box[2]) / 2,
                            (current_box[1] + current_box[3]) / 2]
            previous_center = [(previous_box[0] + previous_box[2]) / 2,
                             (previous_box[1] + previous_box[3]) / 2]
            
            # Calculate movement vector
            movement = {
                'dx': current_center[0] - previous_center[0],
                'dy': current_center[1] - previous_center[1],
                'time_delta': time.time() - self.detection_history[track_id]['last_seen']
            }
            
            return movement
            
        except Exception as e:
            logger.error(f"Error calculating movement: {e}")
            return None

    def process_frame(self, frame: np.ndarray):
        """Process frame with object detection and streaming."""
        try:
            start_time = time.time()
            
            # Process original frame first
            frame_data = self.encode_frame(frame)
            if frame_data:
                self.socketio.emit('video_frame', {
                    'frame': frame_data,
                    'timestamp': time.time(),
                    'fps': round(self.calculate_fps(), 1)
                })

            # Object detection
            detections = self.detector.detect_objects(frame)
            
            if detections:
                # Update tracking history
                self.update_detection_history(detections)
                
                # Calculate movements for tracked objects
                for detection in detections:
                    movement = self.calculate_movement(detection)
                    if movement:
                        detection['movement'] = movement
                
                # Draw detections on frame
                detection_frame = self.detector.draw_detections(frame.copy(), detections)
                detection_data = self.encode_frame(detection_frame)
                
                if detection_data:
                    self.socketio.emit('detection_frame', {
                        'frame': detection_data,
                        'detections': detections,
                        'timestamp': time.time()
                    })

                    # Check for and emit high-threat alerts
                    high_threats = [d for d in detections if d['threat_level'] == 'high']
                    if high_threats:
                        self.socketio.emit('threat_alert', {
                            'threats': high_threats,
                            'timestamp': time.time()
                        })

            # Calculate and store processing time
            processing_time = time.time() - start_time
            self.processing_times.append(processing_time)
            
            # Keep only recent processing times
            if len(self.processing_times) > 100:
                self.processing_times.pop(0)
            
            # Emit performance metrics periodically
            if len(self.processing_times) % 30 == 0:
                avg_processing_time = sum(self.processing_times) / len(self.processing_times)
                self.socketio.emit('performance_metrics', {
                    'avg_processing_time': avg_processing_time,
                    'fps': self.fps,
                    'timestamp': time.time()
                })

        except Exception as e:
            logger.error(f"Error processing frame: {e}")

    def stream_video(self, drone):
        """Main video streaming loop."""
        logger.info("Starting video stream")
        last_frame_time = time.time()
        frame_interval = 1.0 / 20.0  # Target 20 FPS
        
        while self.is_streaming():
            try:
                current_time = time.time()
                if current_time - last_frame_time < frame_interval:
                    time.sleep(0.001)  # Short sleep to prevent CPU overuse
                    continue

                frame = self.get_frame(drone)
                if frame is not None:
                    # Add to frame buffer
                    self.frame_buffer.append(frame)
                    if len(self.frame_buffer) > self.frame_buffer_size:
                        self.frame_buffer.pop(0)
                    
                    # Process latest frame
                    self.process_frame(frame)
                    last_frame_time = current_time
                else:
                    time.sleep(0.1)

            except Exception as e:
                logger.error(f"Streaming error: {e}")
                time.sleep(0.1)

        logger.info("Video streaming stopped")

    def is_streaming(self) -> bool:
        """Check if streaming is active."""
        with self._lock:
            return self.streaming

    def start_streaming(self, drone) -> bool:
        """Start video streaming thread."""
        with self._lock:
            if self.streaming:
                logger.warning("Streaming already active")
                return False
            
            self.streaming = True
            self.stream_thread = threading.Thread(
                target=self.stream_video,
                args=(drone,),
                daemon=True
            )
            self.stream_thread.start()
            logger.info("Streaming thread started")
            return True

    def stop_streaming(self):
        """Stop video streaming."""
        with self._lock:
            self.streaming = False
            if self.stream_thread:
                self.stream_thread.join(timeout=2.0)
                self.stream_thread = None
            # Clear buffers
            self.frame_buffer.clear()
            self.detection_history.clear()
            logger.info("Streaming stopped and buffers cleared")

    def get_performance_metrics(self) -> Dict:
        """Get current performance metrics."""
        try:
            return {
                'fps': round(self.fps, 1),
                'avg_processing_time': sum(self.processing_times) / len(self.processing_times) if self.processing_times else 0,
                'buffer_size': len(self.frame_buffer),
                'tracked_objects': len(self.detection_history)
            }
        except Exception as e:
            logger.error(f"Error getting performance metrics: {e}")
            return {}