from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import logging
import sys
import os
import asyncio
from datetime import datetime
from classes.drone_manager import DroneManager
from classes.video_streamer import VideoStreamer
from classes.object_detector import ObjectDetector
from classes.patrol_system import PatrolSystem

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# Initialize Flask
app = Flask(__name__)
app.config['SECRET_KEY'] = 'drone_secret!'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Initialize components
logger.info("Initializing system components...")
try:
    object_detector = ObjectDetector()
    video_streamer = VideoStreamer(socketio)
    drone_manager = DroneManager()
    patrol_system = PatrolSystem(drone_manager, socketio)
    
    video_streamer.set_detector(object_detector)
    drone_manager.set_video_streamer(video_streamer)
    
    logger.info("System components initialized successfully")
except Exception as e:
    logger.critical(f"Failed to initialize components: {e}")
    sys.exit(1)

# Routes
@app.route('/')
def index():
    """Render the main control interface."""
    return render_template('index.html')

@app.route('/status')
def status():
    """Get current system status."""
    if not drone_manager.is_connected:
        return jsonify({"error": "Drone not connected"}), 400

    try:
        return jsonify({
            "connected": True,
            "battery": drone_manager.battery_level,
            "streaming": video_streamer.is_streaming(),
            "patrol_status": patrol_system.status.value
        })
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        return jsonify({"error": str(e)}), 500

# Socket Events - Connection Management
@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    logger.info("Client connected")
    try:
        if not drone_manager.is_connected:
            if drone_manager.connect_drone():
                emit('message', {'data': 'Connected to drone', 'type': 'success'})
                emit('status_update', {
                    'connected': True,
                    'battery': drone_manager.battery_level
                })
            else:
                emit('message', {'data': 'Failed to connect to drone', 'type': 'error'})
        else:
            emit('message', {'data': 'Already connected', 'type': 'info'})
            emit('status_update', {
                'connected': True,
                'battery': drone_manager.battery_level
            })
    except Exception as e:
        logger.error(f"Connection error: {e}")
        emit('message', {'data': f'Connection error: {str(e)}', 'type': 'error'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection."""
    logger.info("Client disconnected")
    try:
        video_streamer.stop_streaming()
        patrol_system.stop_patrol()
    except Exception as e:
        logger.error(f"Disconnect error: {e}")

# Socket Events - Video Control
@socketio.on('start_video')
def handle_start_video():
    """Start video streaming."""
    if not drone_manager.is_connected:
        emit('message', {'data': 'Drone not connected', 'type': 'error'})
        return

    try:
        success = video_streamer.start_streaming(drone_manager.drone)
        if success:
            emit('message', {'data': 'Video streaming started', 'type': 'success'})
        else:
            emit('message', {'data': 'Failed to start video stream', 'type': 'error'})
    except Exception as e:
        logger.error(f"Error starting video: {e}")
        emit('message', {'data': f'Error starting video: {str(e)}', 'type': 'error'})

@socketio.on('stop_video')
def handle_stop_video():
    """Stop video streaming."""
    try:
        video_streamer.stop_streaming()
        emit('message', {'data': 'Video streaming stopped', 'type': 'info'})
    except Exception as e:
        logger.error(f"Error stopping video: {e}")
        emit('message', {'data': f'Error stopping video: {str(e)}', 'type': 'error'})

# Socket Events - Patrol Control
@socketio.on('set_patrol_height')
async def handle_set_height(data):
    """Set patrol height."""
    try:
        height = float(data.get('height', 10.0))
        success = patrol_system.set_height(height)
        if success:
            emit('message', {'data': f'Height set to {height}m', 'type': 'success'})
        else:
            emit('message', {'data': 'Invalid height', 'type': 'error'})
    except Exception as e:
        logger.error(f"Error setting height: {e}")
        emit('message', {'data': 'Error setting height', 'type': 'error'})

@socketio.on('set_square_size')
async def handle_set_square_size(data):
    """Set square patrol size."""
    try:
        size = float(data.get('size', 10.0))
        success = patrol_system.calculate_square_points(size)
        if success:
            emit('message', {'data': f'Square size set to {size}m', 'type': 'success'})
        else:
            emit('message', {'data': 'Invalid square size', 'type': 'error'})
    except Exception as e:
        logger.error(f"Error setting square size: {e}")
        emit('message', {'data': 'Error setting square size', 'type': 'error'})

@socketio.on('patrol_corner')
async def handle_corner_patrol(data):
    """Handle specific corner patrol request."""
    if not drone_manager.is_connected:
        emit('message', {'data': 'Drone not connected', 'type': 'error'})
        return

    try:
        corner = data.get('corner')
        corner_name = patrol_system.corners[corner]['name']
        
        emit('corner_patrol_status', {
            'status': 'started',
            'corner': corner_name
        })
        
        success = await patrol_system.patrol_specific_corner(corner)
        
        if success:
            emit('corner_patrol_status', {
                'status': 'completed',
                'corner': corner_name
            })
        else:
            emit('message', {
                'data': f'Failed to patrol {corner_name}',
                'type': 'error'
            })
    except Exception as e:
        logger.error(f"Error in corner patrol: {e}")
        emit('message', {
            'data': 'Error during corner patrol',
            'type': 'error'
        })

@socketio.on('start_square_patrol')
async def handle_start_square_patrol():
    """Start square perimeter patrol."""
    if not drone_manager.is_connected:
        emit('message', {'data': 'Drone not connected', 'type': 'error'})
        return

    try:
        success = await patrol_system.start_patrol('square')
        if success:
            emit('message', {'data': 'Square patrol started', 'type': 'success'})
        else:
            emit('message', {'data': 'Failed to start patrol', 'type': 'error'})
    except Exception as e:
        logger.error(f"Error starting patrol: {e}")
        emit('message', {'data': f'Error: {str(e)}', 'type': 'error'})

@socketio.on('start_random_patrol')
async def handle_start_random_patrol():
    """Start random point patrol."""
    if not drone_manager.is_connected:
        emit('message', {'data': 'Drone not connected', 'type': 'error'})
        return

    try:
        success = await patrol_system.start_patrol('random')
        if success:
            emit('message', {'data': 'Random patrol started', 'type': 'success'})
        else:
            emit('message', {'data': 'Failed to start patrol', 'type': 'error'})
    except Exception as e:
        logger.error(f"Error starting patrol: {e}")
        emit('message', {'data': f'Error: {str(e)}', 'type': 'error'})

@socketio.on('stop_patrol')
async def handle_stop_patrol():
    """Stop current patrol."""
    try:
        patrol_system.stop_patrol()
        emit('message', {'data': 'Patrol stopped', 'type': 'info'})
    except Exception as e:
        logger.error(f"Error stopping patrol: {e}")
        emit('message', {'data': f'Error: {str(e)}', 'type': 'error'})

# Cleanup handler
def cleanup_handler(signum, frame):
    """Handle cleanup on shutdown."""
    logger.info("Performing cleanup...")
    try:
        patrol_system.stop_patrol()
        drone_manager.cleanup()
    except Exception as e:
        logger.error(f"Cleanup error: {e}")
    finally:
        sys.exit(0)

if __name__ == '__main__':
    try:
        # Register cleanup handlers
        import signal
        signal.signal(signal.SIGINT, cleanup_handler)
        signal.signal(signal.SIGTERM, cleanup_handler)
        
        logger.info("Starting server on port 5000...")
        socketio.run(app, host='0.0.0.0', port=5000, debug=False, use_reloader=False)
    except Exception as e:
        logger.critical(f"Server startup failed: {e}")
        drone_manager.cleanup()
        sys.exit(1)