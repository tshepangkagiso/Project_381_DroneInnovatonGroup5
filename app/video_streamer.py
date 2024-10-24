import cv2
from base64 import b64encode
import threading
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class VideoStreamer:
    def __init__(self, socketio):
        self.socketio = socketio
        self.streaming = False
        self.stream_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self.frame_size = (640, 480)  # Reduced frame size for better performance

    def get_frame(self, drone):
        """Get a frame from the drone with error handling and frame processing."""
        try:
            frame_read = drone.get_frame_read()
            if frame_read is None:
                logger.error("Frame read object is None")
                return None
                
            frame = frame_read.frame
            if frame is None:
                logger.error("Received null frame from drone")
                return None

            # Resize frame for better performance
            frame = cv2.resize(frame, self.frame_size)
            return frame
        except Exception as e:
            logger.error(f"Error getting frame: {str(e)}")
            return None

    def encode_frame(self, frame):
        """Encode frame to JPEG format with error handling and compression."""
        try:
            # Reduce quality for better performance
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 60]
            _, buffer = cv2.imencode('.jpg', frame, encode_param)
            if buffer is None:
                logger.error("Failed to encode frame")
                return None
                
            frame_data = b64encode(buffer).decode('utf-8')
            return frame_data
        except Exception as e:
            logger.error(f"Error encoding frame: {str(e)}")
            return None

    def stream_video(self, drone_manager):
        """Main video streaming loop with improved error handling and debug logging."""
        logger.info("Starting video stream thread")
        last_frame_time = time.time()
        frame_count = 0
        
        while self.is_streaming() and drone_manager.is_connected():
            try:
                current_time = time.time()
                # Limit frame rate to 20 FPS
                if current_time - last_frame_time < 0.05:
                    time.sleep(0.01)
                    continue

                frame = self.get_frame(drone_manager.get_drone())
                if frame is None:
                    logger.warning("Failed to get frame, retrying...")
                    time.sleep(0.1)
                    continue

                frame_data = self.encode_frame(frame)
                if frame_data is None:
                    logger.warning("Failed to encode frame, retrying...")
                    time.sleep(0.1)
                    continue

                self.socketio.emit('video_frame', {
                    'frame': frame_data,
                    'timestamp': time.time()
                })
                
                frame_count += 1
                if frame_count % 100 == 0:  # Log every 100 frames
                    logger.info(f"Streamed {frame_count} frames")
                    
                last_frame_time = current_time

            except Exception as e:
                logger.error(f"Error in stream_video: {str(e)}")
                time.sleep(0.1)

        logger.info("Video streaming stopped")

    def is_streaming(self) -> bool:
        """Thread-safe check of streaming status."""
        with self._lock:
            return self.streaming

    def start_streaming(self, drone_manager):
        """Start video streaming with additional checks."""
        with self._lock:
            if self.streaming:
                logger.info("Stream already active")
                return False
                
            if not drone_manager.get_drone().stream_on:
                logger.info("Ensuring drone stream is on")
                try:
                    drone_manager.get_drone().streamon()
                    time.sleep(2)  # Give time for stream to initialize
                except Exception as e:
                    logger.error(f"Failed to start drone stream: {str(e)}")
                    return False

            logger.info("Starting video stream")
            self.streaming = True
            self.stream_thread = threading.Thread(
                target=self.stream_video,
                args=(drone_manager,),
                daemon=True
            )
            self.stream_thread.start()
            return True

    def stop_streaming(self):
        """Stop video streaming with proper cleanup."""
        with self._lock:
            logger.info("Stopping video stream")
            self.streaming = False
            if self.stream_thread:
                self.stream_thread.join(timeout=2.0)
                self.stream_thread = None