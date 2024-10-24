#pip install Flask Flask-SocketIO eventlet djitellopy opencv-python opencv-contrib-python numpy typing logging
#python droneio3.py
#esp 32 for parameter thing

from flask import Flask, render_template, jsonify, Response
from flask_socketio import SocketIO, emit
from djitellopy import Tello
import threading
import time
import cv2
from base64 import b64encode
from typing import Optional
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app and Flask-SocketIO
app = Flask(__name__)
app.config['SECRET_KEY'] = 'drone_secret!'  # Change this to a secure secret key
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='threading')

# Global variables
drone = None
drone_connected = False

class VideoStreamer:
    def __init__(self, socketio: SocketIO):
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

    def stream_video(self, drone):
        """Main video streaming loop with improved error handling and debug logging."""
        logger.info("Starting video stream thread")
        last_frame_time = time.time()
        frame_count = 0
        
        while self.is_streaming() and drone_connected:
            try:
                current_time = time.time()
                # Limit frame rate to 20 FPS
                if current_time - last_frame_time < 0.05:
                    time.sleep(0.01)
                    continue

                frame = self.get_frame(drone)
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

    def start_streaming(self, drone):
        """Start video streaming with additional checks."""
        with self._lock:
            if self.streaming:
                logger.info("Stream already active")
                return False
                
            if not drone.stream_on:
                logger.info("Ensuring drone stream is on")
                try:
                    drone.streamon()
                    time.sleep(2)  # Give time for stream to initialize
                except Exception as e:
                    logger.error(f"Failed to start drone stream: {str(e)}")
                    return False

            logger.info("Starting video stream")
            self.streaming = True
            self.stream_thread = threading.Thread(
                target=self.stream_video,
                args=(drone,),
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

# Initialize VideoStreamer
video_streamer = VideoStreamer(socketio)

def connect_drone():
    """Connect to the drone with error handling."""
    global drone, drone_connected
    try:
        logger.info("Attempting to connect to drone...")
        drone = Tello()
        drone.connect()
        if drone.get_battery() > 0:  # Basic connection test
            drone.streamon()
            drone_connected = True
            logger.info("Successfully connected to drone")
            return True
        else:
            logger.error("Failed to verify drone connection")
            return False
    except Exception as e:
        logger.error(f"Drone connection failed: {str(e)}")
        drone_connected = False
        return False

def send_keep_alive():
    """Keep-alive function to maintain drone connection."""
    while True:
        if drone_connected:
            try:
                drone.get_battery()  # Send a keep-alive command
                time.sleep(5)  # Sleep for 5 seconds
            except Exception as e:
                logger.error(f"Keep-alive error: {str(e)}")
                video_streamer.stop_streaming()
        else:
            time.sleep(5)  # Wait before retry if disconnected

@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    logger.info("Client connected")
    if not drone_connected:
        if connect_drone():
            emit('message', {'data': 'Connected to drone successfully!'})
        else:
            emit('message', {'data': 'Failed to connect to drone'})
    else:
        emit('message', {'data': 'Already connected to drone'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection."""
    logger.info("Client disconnected")
    video_streamer.stop_streaming()

@socketio.on('drone_command')
def handle_drone_command(data):
    """Handle drone control commands."""
    if not drone_connected:
        emit('message', {'data': 'Drone is not connected'})
        return
    
    command = data.get('command')
    distance = data.get('distance', 30)  # Default distance of 30cm
    
    try:
        if command == 'takeoff':
            drone.takeoff()
            emit('message', {'data': 'Drone took off!'})
        elif command == 'land':
            drone.land()
            emit('message', {'data': 'Drone landed!'})
        elif command == 'move_forward':
            drone.move_forward(distance)
            emit('message', {'data': f'Drone moved forward {distance}cm'})
        elif command == 'move_back':
            drone.move_back(distance)
            emit('message', {'data': f'Drone moved back {distance}cm'})
        elif command == 'move_left':
            drone.move_left(distance)
            emit('message', {'data': f'Drone moved left {distance}cm'})
        elif command == 'move_right':
            drone.move_right(distance)
            emit('message', {'data': f'Drone moved right {distance}cm'})
        elif command == 'move_up':
            drone.move_up(distance)
            emit('message', {'data': f'Drone moved up {distance}cm'})
        elif command == 'move_down':
            drone.move_down(distance)
            emit('message', {'data': f'Drone moved down {distance}cm'})
        elif command == 'rotate_clockwise':
            drone.rotate_clockwise(90)
            emit('message', {'data': 'Drone rotated clockwise'})
        elif command == 'rotate_counter_clockwise':
            drone.rotate_counter_clockwise(90)
            emit('message', {'data': 'Drone rotated counter-clockwise'})
        else:
            emit('message', {'data': f'Invalid command: {command}'})
    except Exception as e:
        logger.error(f"Error executing command {command}: {str(e)}")
        emit('message', {'data': f'Error: {str(e)}'})

@socketio.on('start_video')
def handle_start_video():
    """Handle video stream start request."""
    if not drone_connected:
        emit('message', {'data': 'Drone not connected'})
        return
        
    logger.info("Received start_video request")
    try:
        success = video_streamer.start_streaming(drone)
        emit('message', {
            'data': 'Video streaming started' if success else 'Video streaming failed to start'
        })
    except Exception as e:
        logger.error(f"Error starting video: {str(e)}")
        emit('message', {'data': f'Error starting video: {str(e)}'})

@socketio.on('stop_video')
def handle_stop_video():
    """Handle video stream stop request."""
    logger.info("Received stop_video request")
    video_streamer.stop_streaming()
    emit('message', {'data': 'Video streaming stopped'})

@app.route('/')
def index():
    """Render the main control interface."""
    return render_template('websocket.html')

@app.route('/status')
def status():
    """Get current drone status."""
    if not drone_connected:
        return jsonify({"error": "Drone not connected"}), 400

    try:
        battery = drone.get_battery()
        height = drone.get_height()
        temperature = drone.get_temperature()
        flight_time = drone.get_flight_time()
        wifi_strength = drone.query_wifi_signal_noise_ratio()

        return jsonify({
            "battery": f"{battery}%",
            "height": f"{height}cm",
            "temperature": f"{temperature}°C",
            "flight_time": f"{flight_time}s",
            "wifi_strength": f"{wifi_strength}",
            "is_flying": drone.is_flying
        })
    except Exception as e:
        logger.error(f"Error getting drone status: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Start keep-alive thread
    keep_alive_thread = threading.Thread(target=send_keep_alive, daemon=True)
    keep_alive_thread.start()
    
    try:
        logger.info("Starting server on port 5000...")
        socketio.run(app, host='0.0.0.0', port=5000, debug=True, use_reloader=False)
    except Exception as e:
        logger.error(f"Server error: {str(e)}")