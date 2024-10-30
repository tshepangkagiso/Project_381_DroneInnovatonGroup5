import cv2
import threading
import time
from base64 import b64encode
import logging
import numpy as np

logger = logging.getLogger(__name__)

class VideoStreamer:
    def __init__(self, socketio):
        self.socketio = socketio
        self.streaming = False
        self.frame_size = (640, 480)
        self._lock = threading.Lock()
        self.stream_thread = None
        self.detector = None  # Will be set after initialization
        self.frame_counter = 0
        self.last_fps_time = time.time()
        self.fps = 0
        
    def set_detector(self, detector):
        """Set the object detector component."""
        self.detector = detector

    def get_frame(self, drone):
        """Get a frame from the drone camera."""
        try:
            frame_read = drone.get_frame_read()
            if frame_read and frame_read.frame is not None:
                frame = frame_read.frame
                return cv2.resize(frame, self.frame_size)
            return None
        except Exception as e:
            logger.error(f"Error getting frame: {e}")
            return None

    def encode_frame(self, frame):
        """Encode frame to JPEG format for streaming."""
        try:
            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
            return b64encode(buffer).decode('utf-8')
        except Exception as e:
            logger.error(f"Error encoding frame: {e}")
            return None

    def calculate_fps(self):
        """Calculate current FPS."""
        self.frame_counter += 1
        current_time = time.time()
        time_diff = current_time - self.last_fps_time
        
        if time_diff >= 1.0:
            self.fps = self.frame_counter / time_diff
            self.frame_counter = 0
            self.last_fps_time = current_time
            
        return self.fps

    def process_frame(self, frame):
        """Process frame for both raw streaming and object detection."""
        try:
            # Process original frame first
            frame_data = self.encode_frame(frame)
            if frame_data:
                self.socketio.emit('video_frame', {
                    'frame': frame_data,
                    'timestamp': time.time(),
                    'fps': round(self.calculate_fps(), 1)
                })

            # Object detection
            if self.detector:
                detections = self.detector.detect_objects(frame)
                
                if detections:
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
                    self.process_frame(frame)
                    last_frame_time = current_time
                else:
                    time.sleep(0.1)

            except Exception as e:
                logger.error(f"Streaming error: {e}")
                time.sleep(0.1)

        logger.info("Video streaming stopped")

    def is_streaming(self):
        """Check if streaming is active."""
        with self._lock:
            return self.streaming

    def start_streaming(self, drone):
        """Start video streaming thread."""
        with self._lock:
            if self.streaming:
                return False
            
            self.streaming = True
            self.stream_thread = threading.Thread(
                target=self.stream_video,
                args=(drone,),
                daemon=True
            )
            self.stream_thread.start()
            return True

    def stop_streaming(self):
        """Stop video streaming thread."""
        with self._lock:
            self.streaming = False
            if self.stream_thread:
                self.stream_thread.join(timeout=2.0)
                self.stream_thread = None