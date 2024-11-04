from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import signal
import sys
import logging
import os
import random
import threading
from models.drone_manager import DroneManager
from models.patrol import PatrolPoint

'''
Key additions and features:

    Individual patrol routes (/patrol/bl, /patrol/tl, /patrol/tr)
    Random patrol with start/stop capability (/patrol/random/start, /patrol/random/stop)
    Emergency and control routes (/drone/takeoff, /drone/land, /drone/emergency)
    Enhanced status endpoint with patrol information
    Thread management for random patrol sequence
    Improved error handling and logging
    Cleanup handling for graceful shutdown

All routes return appropriate HTTP status codes and JSON responses. The random patrol feature runs in its own thread and can be started/stopped independently of other operations.
'''

# Create logs directory if it doesn't exist
if not os.path.exists('logs'):
    os.makedirs('logs')

# Configure main app logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/app.log')
    ]
)

logger = logging.getLogger(__name__)

# Initialize Flask
app = Flask(__name__)
app.config['SECRET_KEY'] = 'drone_secret!'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Initialize drone manager
drone_manager = DroneManager(socketio)

# Random patrol thread control
random_patrol_thread = None
random_patrol_stop = threading.Event()

def random_patrol_sequence():
    """Execute random patrol sequences until stopped."""
    while not random_patrol_stop.is_set():
        try:
            # Select random patrol point
            patrol_point = random.choice([PatrolPoint.BL, PatrolPoint.TL, PatrolPoint.TR])
            
            # Execute patrol
            drone_manager.drone.patrol.execute_patrol(patrol_point)
            
            # Wait for patrol to complete
            while drone_manager.drone.patrol.is_patrolling:
                if random_patrol_stop.is_set():
                    drone_manager.drone.patrol.stop_patrol()
                    return
                socketio.sleep(1)
                
            # Wait between patrols
            socketio.sleep(5)
            
        except Exception as e:
            logger.error(f"Error in random patrol sequence: {e}")
            break

# Routes
@app.route('/')
def index():
    """Render the main control interface."""
    return render_template('index.html')

@app.route('/status')
def status():
    """Get current drone and patrol status."""
    if not drone_manager.is_connected:
        return jsonify({"error": "Drone not connected"}), 400

    try:
        patrol_status = drone_manager.drone.patrol.get_patrol_status()
        return jsonify({
            "connected": True,
            "battery": drone_manager.battery_level,
            "streaming": drone_manager.video_streamer.is_streaming(),
            "patrol_status": patrol_status
        })
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        return jsonify({"error": str(e)}), 500

# Patrol Routes
@app.route('/patrol/bl', methods=['POST'])
def patrol_bl():
    """Execute Bottom Left patrol route."""
    try:
        if not drone_manager.is_connected:
            return jsonify({"error": "Drone not connected"}), 400
            
        success = drone_manager.drone.patrol.execute_patrol(PatrolPoint.BL)
        if success:
            return jsonify({"message": "Bottom Left patrol initiated"}), 200
        return jsonify({"error": "Failed to start patrol"}), 500
    except Exception as e:
        logger.error(f"Error initiating BL patrol: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/patrol/tl', methods=['POST'])
def patrol_tl():
    """Execute Top Left patrol route."""
    try:
        if not drone_manager.is_connected:
            return jsonify({"error": "Drone not connected"}), 400
            
        success = drone_manager.drone.patrol.execute_patrol(PatrolPoint.TL)
        if success:
            return jsonify({"message": "Top Left patrol initiated"}), 200
        return jsonify({"error": "Failed to start patrol"}), 500
    except Exception as e:
        logger.error(f"Error initiating TL patrol: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/patrol/tr', methods=['POST'])
def patrol_tr():
    """Execute Top Right patrol route."""
    try:
        if not drone_manager.is_connected:
            return jsonify({"error": "Drone not connected"}), 400
            
        success = drone_manager.drone.patrol.execute_patrol(PatrolPoint.TR)
        if success:
            return jsonify({"message": "Top Right patrol initiated"}), 200
        return jsonify({"error": "Failed to start patrol"}), 500
    except Exception as e:
        logger.error(f"Error initiating TR patrol: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/patrol/random/start', methods=['POST'])
def start_random_patrol():
    """Start random patrol sequence."""
    global random_patrol_thread
    try:
        if not drone_manager.is_connected:
            return jsonify({"error": "Drone not connected"}), 400
            
        if random_patrol_thread and random_patrol_thread.is_alive():
            return jsonify({"error": "Random patrol already running"}), 400
            
        random_patrol_stop.clear()
        random_patrol_thread = threading.Thread(target=random_patrol_sequence)
        random_patrol_thread.daemon = True
        random_patrol_thread.start()
        
        return jsonify({"message": "Random patrol started"}), 200
    except Exception as e:
        logger.error(f"Error starting random patrol: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/patrol/random/stop', methods=['POST'])
def stop_random_patrol():
    """Stop random patrol sequence."""
    global random_patrol_thread
    try:
        if random_patrol_thread and random_patrol_thread.is_alive():
            random_patrol_stop.set()
            random_patrol_thread.join(timeout=2.0)
            return jsonify({"message": "Random patrol stopped"}), 200
        return jsonify({"message": "No random patrol running"}), 200
    except Exception as e:
        logger.error(f"Error stopping random patrol: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/patrol/stop', methods=['POST'])
def stop_patrol():
    """Stop any current patrol."""
    try:
        if not drone_manager.is_connected:
            return jsonify({"error": "Drone not connected"}), 400
            
        drone_manager.drone.patrol.stop_patrol()
        return jsonify({"message": "Patrol stopped"}), 200
    except Exception as e:
        logger.error(f"Error stopping patrol: {e}")
        return jsonify({"error": str(e)}), 500

# Emergency and Control Routes
@app.route('/drone/takeoff', methods=['POST'])
def takeoff():
    """Execute takeoff command."""
    try:
        if not drone_manager.is_connected:
            return jsonify({"error": "Drone not connected"}), 400
            
        success = drone_manager.takeoff()
        if success:
            return jsonify({"message": "Takeoff successful"}), 200
        return jsonify({"error": "Takeoff failed"}), 500
    except Exception as e:
        logger.error(f"Error during takeoff: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/drone/land', methods=['POST'])
def land():
    """Execute landing command."""
    try:
        if not drone_manager.is_connected:
            return jsonify({"error": "Drone not connected"}), 400
            
        success = drone_manager.land()
        if success:
            return jsonify({"message": "Landing successful"}), 200
        return jsonify({"error": "Landing failed"}), 500
    except Exception as e:
        logger.error(f"Error during landing: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/drone/emergency', methods=['POST'])
def emergency():
    """Execute emergency landing."""
    try:
        if not drone_manager.is_connected:
            return jsonify({"error": "Drone not connected"}), 400
            
        drone_manager.emergency_land()
        return jsonify({"message": "Emergency landing executed"}), 200
    except Exception as e:
        logger.error(f"Error during emergency landing: {e}")
        return jsonify({"error": str(e)}), 500

# Socket events (existing events remain the same)
@socketio.on('connect')
def handle_connect():
    """Handle client connection and drone initialization."""
    logger.info("Client connected")
    try:
        if not drone_manager.is_connected:
            if drone_manager.connect_drone():
                emit('message', {
                    'data': f'Connected to drone successfully! Battery: {drone_manager.battery_level}%',
                    'type': 'success'
                })
                emit('status_update', {
                    'connected': True,
                    'battery': drone_manager.battery_level
                })
            else:
                emit('message', {
                    'data': 'Failed to connect to drone. Please check the connection.',
                    'type': 'error'
                })
        else:
            emit('message', {
                'data': 'Already connected to drone',
                'type': 'info'
            })
            emit('status_update', {
                'connected': True,
                'battery': drone_manager.battery_level
            })
    except Exception as e:
        logger.error(f"Connection error: {e}")
        emit('message', {
            'data': f'Connection error: {str(e)}',
            'type': 'error'
        })

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection."""
    logger.info("Client disconnected")
    try:
        drone_manager.video_streamer.stop_streaming()
    except Exception as e:
        logger.error(f"Disconnect error: {e}")

def cleanup_handler(signum, frame):
    """Handle cleanup on shutdown."""
    logger.info("Performing cleanup before shutdown...")
    try:
        random_patrol_stop.set()
        if random_patrol_thread:
            random_patrol_thread.join(timeout=2.0)
        drone_manager.cleanup()
    except Exception as e:
        logger.error(f"Cleanup error: {e}")
    finally:
        sys.exit(0)

if __name__ == '__main__':
    try:
        # Register cleanup handlers
        signal.signal(signal.SIGINT, cleanup_handler)
        signal.signal(signal.SIGTERM, cleanup_handler)
        
        # Start the server
        logger.info("Starting drone server on port 5000...")
        socketio.run(
            app,
            host='0.0.0.0',
            port=5000,
            debug=False,
            use_reloader=False
        )
    except Exception as e:
        logger.critical(f"Server startup failed: {e}")
        drone_manager.cleanup()
        sys.exit(1)