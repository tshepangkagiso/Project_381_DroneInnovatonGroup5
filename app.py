# python app.py

from flask import Flask, render_template
from flask_socketio import SocketIO
from flask_cors import CORS
import logging
from app.drone_manager import DroneManager
from app.video_streamer import VideoStreamer
from app.control_thread import ControlThread
from app.event_handlers import register_socket_events

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app and CORS
app = Flask(__name__)
app.config['SECRET_KEY'] = 'drone_secret!'

# CORS Configuration
allowed_origins = ["http://localhost:3000", "http://localhost:5000"]
CORS(app, resources={
    r"/*": {
        "origins": allowed_origins,
        "allow_credentials": True,
        "methods": ["GET", "POST", "OPTIONS"],
        "expose_headers": ["Content-Range", "X-Content-Range"]
    }
})

# Initialize Socket.IO with CORS settings
socketio = SocketIO(
    app,
    cors_allowed_origins=allowed_origins,
    async_mode='threading'
)

# Initialize components
drone_manager = DroneManager()
video_streamer = VideoStreamer(socketio)
control_thread = ControlThread()

# Register socket events
register_socket_events(socketio, drone_manager, video_streamer, control_thread)

@app.route('/')
def index():
    """Render the main control interface."""
    return render_template('dashboard.html')

@app.route('/status')
def status():
    """Get current drone status."""
    return drone_manager.get_status()

if __name__ == '__main__':
    # Start keep-alive thread
    drone_manager.start_keep_alive()
    
    try:
        logger.info("Starting server on port 5000...")
        socketio.run(app, host='0.0.0.0', port=5000, debug=True, use_reloader=False)
    except Exception as e:
        logger.error(f"Server error: {str(e)}")