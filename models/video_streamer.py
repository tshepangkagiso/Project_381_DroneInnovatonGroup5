import cv2
import threading
import time
import logging
from base64 import b64encode
import numpy as np
from typing import Optional, Dict, List, Tuple, Deque
from collections import deque
from .object_detector import ObjectDetector

# Configure logging
logger = logging.getLogger(__name__)

class FrameBuffer:
    """Efficient frame buffer with automatic overflow protection."""
    def __init__(self, maxlen: int = 5):
        self.frames: Deque = deque(maxlen=maxlen)
        self.lock = threading.Lock()

    def add_frame(self, frame: np.ndarray) -> None:
        """Add frame to buffer with thread safety."""
        with self.lock:
            self.frames.append(frame)

    def get_latest_frame(self) -> Optional[np.ndarray]:
        """Get most recent frame from buffer."""
        with self.lock:
            return self.frames[-1].copy() if self.frames else None

    def clear(self) -> None:
        """Clear buffer."""
        with self.lock:
            self.frames.clear()

class StreamMetrics:
    """Performance metrics tracker."""
    def __init__(self):
        self.fps = 0.0
        self.frame_times: List[float] = []
        self.processing_times: List[float] = []
        self.detection_times: List[float] = []
        self.max_history = 100
        self.lock = threading.Lock()
        self.start_time = time.time()
        self.frame_count = 0
        self.error_count = 0

    def update_fps(self) -> None:
        """Update FPS calculation."""
        with self.lock:
            current_time = time.time()
            self.frame_count += 1
            if self.frame_times:
                time_diff = current_time - self.frame_times[-1]
                if time_diff > 0:
                    self.fps = 1 / time_diff

            self.frame_times.append(current_time)
            if len(self.frame_times) > self.max_history:
                self.frame_times.pop(0)

    def add_processing_time(self, duration: float) -> None:
        """Add frame processing time."""
        with self.lock:
            self.processing_times.append(duration)
            if len(self.processing_times) > self.max_history:
                self.processing_times.pop(0)

    def add_detection_time(self, duration: float) -> None:
        """Add object detection time."""
        with self.lock:
            self.detection_times.append(duration)
            if len(self.detection_times) > self.max_history:
                self.detection_times.pop(0)

    def get_stats(self) -> Dict:
        """Get current performance statistics."""
        with self.lock:
            return {
                'fps': self.fps,
                'avg_processing_time': np.mean(self.processing_times) if self.processing_times else 0,
                'avg_detection_time': np.mean(self.detection_times) if self.detection_times else 0,
                'total_frames': self.frame_count,
                'error_count': self.error_count,
                'uptime': time.time() - self.start_time
            }

class VideoStreamer:
    def __init__(self, socketio):
        """Initialize optimized video streamer."""
        try:
            # Core components
            self.socketio = socketio
            self.frame_buffer = FrameBuffer(maxlen=5)
            self.metrics = StreamMetrics()
            self.detector = ObjectDetector()
            
            # Threading control
            self.streaming = False
            self.processing = False
            self.stream_thread = None
            self.process_thread = None
            self.emit_thread = None
            self._lock = threading.Lock()
            
            # Performance settings
            self.frame_size = (640, 480)  # Increased for better visibility
            self.display_size = (960, 720)  # Larger display size
            self.process_every_n_frames = 3
            self.frame_counter = 0
            self.jpeg_quality = 80  # Increased quality
            self.max_fps = 30
            
            # Frame synchronization
            self.last_processed_frame = None
            self.last_detections = []
            self.detection_event = threading.Event()
            
            # UDP settings
            self.udp_retry_count = 0
            self.max_udp_retries = 3
            self.udp_retry_delay = 0.5
            
            logger.info("Optimized VideoStreamer initialized successfully")
            
        except Exception as e:
            logger.error(f"VideoStreamer initialization failed: {e}")
            raise

    def start_streaming(self, drone) -> bool:
        """Start optimized video streaming."""
        try:
            with self._lock:
                if self.streaming:
                    return False
                
                if not drone:
                    raise ValueError("Invalid drone object")
                
                # Reset state
                self.streaming = True
                self.processing = True
                self.frame_buffer.clear()
                self.metrics = StreamMetrics()
                
                # Initialize UDP video stream
                try:
                    drone.streamon()
                    time.sleep(2)  # Wait for stream initialization
                except Exception as e:
                    logger.error(f"Failed to initialize video stream: {e}")
                    return False
                
                # Start threads
                self.stream_thread = threading.Thread(
                    target=self._stream_loop,
                    args=(drone,),
                    daemon=True
                )
                self.process_thread = threading.Thread(
                    target=self._process_loop,
                    daemon=True
                )
                self.emit_thread = threading.Thread(
                    target=self._emit_loop,
                    daemon=True
                )
                
                self.stream_thread.start()
                self.process_thread.start()
                self.emit_thread.start()
                
                logger.info("Streaming started with optimized pipeline")
                return True
                
        except Exception as e:
            logger.error(f"Failed to start streaming: {e}")
            self.stop_streaming()
            return False

    def _stream_loop(self, drone) -> None:
        """Main video capture loop with UDP stability improvements."""
        try:
            frame_time = 1.0 / self.max_fps
            last_frame_time = 0
            retry_count = 0
            
            while self.streaming:
                current_time = time.time()
                if current_time - last_frame_time < frame_time:
                    time.sleep(0.001)
                    continue
                    
                try:
                    frame = self._get_frame_with_timeout(drone)
                    
                    if frame is not None:
                        retry_count = 0
                        frame = cv2.resize(frame, self.frame_size)
                        self.frame_buffer.add_frame(frame)
                        self.metrics.update_fps()
                        last_frame_time = current_time
                    else:
                        retry_count += 1
                        if retry_count >= self.max_udp_retries:
                            self._restart_video_stream(drone)
                            retry_count = 0
                        time.sleep(self.udp_retry_delay)
                        
                except Exception as e:
                    logger.error(f"Frame capture error: {e}")
                    retry_count += 1
                    if retry_count >= self.max_udp_retries:
                        self._restart_video_stream(drone)
                        retry_count = 0
                    time.sleep(self.udp_retry_delay)
                    
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            self.stop_streaming()

    def _get_frame_with_timeout(self, drone, timeout: float = 0.5) -> Optional[np.ndarray]:
        """Get frame with timeout to handle UDP delays."""
        try:
            start_time = time.time()
            while time.time() - start_time < timeout:
                frame_read = drone.get_frame_read()
                if frame_read and frame_read.frame is not None:
                    frame = frame_read.frame
                    if frame.size > 0:
                        return frame
                time.sleep(0.01)
            return None
        except Exception as e:
            logger.error(f"Frame acquisition error: {e}")
            return None

    def _restart_video_stream(self, drone) -> None:
        """Restart video stream after failure."""
        try:
            logger.info("Restarting video stream...")
            
            # Stop current stream
            try:
                drone.streamoff()
                time.sleep(1)
            except Exception as e:
                logger.error(f"Error stopping stream: {e}")
            
            # Clear buffer
            self.frame_buffer.clear()
            
            # Restart stream
            try:
                drone.streamon()
                time.sleep(2)
                logger.info("Video stream restarted")
            except Exception as e:
                logger.error(f"Error restarting stream: {e}")
                self.stop_streaming()
                
        except Exception as e:
            logger.error(f"Stream restart error: {e}")
            self.stop_streaming()

    def _process_loop(self) -> None:
        """Object detection processing loop."""
        try:
            while self.processing:
                frame = self.frame_buffer.get_latest_frame()
                if frame is None:
                    time.sleep(0.01)
                    continue
                
                self.frame_counter += 1
                if self.frame_counter % self.process_every_n_frames == 0:
                    start_time = time.time()
                    
                    detections = self.detector.detect_objects(frame)
                    
                    self.last_processed_frame = frame
                    self.last_detections = detections
                    self.detection_event.set()
                    
                    self.metrics.add_detection_time(time.time() - start_time)
                
        except Exception as e:
            logger.error(f"Processing error: {e}")
            self.stop_streaming()

    def _emit_loop(self) -> None:
        """Frame emission loop with enhanced error handling."""
        try:
            while self.streaming:
                if not self.detection_event.wait(timeout=0.1):
                    continue
                
                self.detection_event.clear()
                if self.last_processed_frame is None:
                    continue
                
                start_time = time.time()
                
                display_frame = cv2.resize(self.last_processed_frame, self.display_size)
                
                if self.last_detections:
                    detection_frame = self.detector.draw_detections(
                        display_frame.copy(), 
                        self.last_detections
                    )
                else:
                    detection_frame = display_frame.copy()
                
                self._emit_frames(display_frame, detection_frame)
                
                self.metrics.add_processing_time(time.time() - start_time)
                
        except Exception as e:
            logger.error(f"Emission error: {e}")
            self.stop_streaming()

    def _emit_frames(self, raw_frame: np.ndarray, detection_frame: np.ndarray) -> None:
        """Emit processed frames with enhanced error handling."""
        try:
            if raw_frame is None or detection_frame is None:
                return
                
            # Encode frames with higher quality
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality]
            
            # Encode raw frame
            try:
                _, raw_buffer = cv2.imencode('.jpg', raw_frame, encode_param)
                raw_data = b64encode(raw_buffer).decode('utf-8')
                
                self.socketio.emit('video_frame', {
                    'frame': raw_data,
                    'timestamp': time.time(),
                    'fps': self.metrics.fps
                })
            except Exception as e:
                logger.error(f"Raw frame emission error: {e}")
            
            # Encode detection frame
            try:
                _, detection_buffer = cv2.imencode('.jpg', detection_frame, encode_param)
                detection_data = b64encode(detection_buffer).decode('utf-8')
                
                self.socketio.emit('detection_frame', {
                    'frame': detection_data,
                    'detections': self.last_detections,
                    'timestamp': time.time()
                })
            except Exception as e:
                logger.error(f"Detection frame emission error: {e}")
                
        except Exception as e:
            logger.error(f"Frame emission error: {e}")

    def stop_streaming(self) -> None:
        """Stop streaming and cleanup resources."""
        try:
            logger.info("Stopping video stream...")
            
            with self._lock:
                self.streaming = False
                self.processing = False
                
                # Stop threads
                for thread in [self.stream_thread, self.process_thread, self.emit_thread]:
                    if thread and thread.is_alive():
                        thread.join(timeout=2.0)
                
                # Clear resources
                self.frame_buffer.clear()
                self.last_processed_frame = None
                self.last_detections = []
                
                # Log final stats
                stats = self.metrics.get_stats()
                logger.info(
                    f"Stream stopped - Processed {stats['total_frames']} frames "
                    f"at {stats['fps']:.1f} FPS"
                )
                
        except Exception as e:
            logger.error(f"Error stopping stream: {e}")
        finally:
            self.streaming = False
            self.processing = False

    def is_streaming(self) -> bool:
        """Thread-safe streaming status check."""
        with self._lock:
            return self.streaming

    def get_settings(self) -> Dict:
        """Get current settings."""
        return {
            'frame_size': self.frame_size,
            'display_size': self.display_size,
            'process_every_n_frames': self.process_every_n_frames,
            'jpeg_quality': self.jpeg_quality,
            'max_fps': self.max_fps
        }

    def update_settings(self, settings: Dict) -> bool:
        """Update streamer settings."""
        try:
            with self._lock:
                if 'frame_size' in settings:
                    self.frame_size = settings['frame_size']
                if 'display_size' in settings:
                    self.display_size = settings['display_size']
                if 'process_every_n_frames' in settings:
                    self.process_every_n_frames = settings['process_every_n_frames']
                if 'jpeg_quality' in settings:
                    self.jpeg_quality = settings['jpeg_quality']
                if 'max_fps' in settings:
                    self.max_fps = settings['max_fps']
                return True
        except Exception as e:
            logger.error(f"Error updating settings: {e}")
            return False

    def get_status(self) -> Dict:
        """Get current status and metrics."""
        return {
            'streaming': self.streaming,
            'metrics': self.metrics.get_stats(),
            'settings': self.get_settings()
        }