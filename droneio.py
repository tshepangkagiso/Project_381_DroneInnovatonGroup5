#pip install flask opencv-python djitellopy numpy opencv-contrib-python flask-socketio eventlet
#python droneio.py

from flask import Flask, render_template, jsonify, redirect, url_for, Response
from flask_socketio import SocketIO, emit
from djitellopy import Tello
import threading
import time
import cv2

# Initialize Flask app and Flask-SocketIO
app = Flask(__name__)
socketio = SocketIO(app)
drone = None
drone_connected = False

# Drone connection function
def connect_drone():
    global drone, drone_connected
    try:
        drone = Tello()
        drone.connect()
        drone.streamon()  # Start video stream
        drone_connected = True
    except Exception as e:
        print(f"Drone connection failed: {e}")
        drone_connected = False

# Keep-alive function to maintain connection
def send_keep_alive():
    while True:
        if drone_connected:
            try:
                drone.get_battery()  # Send a keep-alive command
                time.sleep(5)  # Sleep for a few seconds
            except Exception as e:
                print(f"Keep-alive error: {e}")
        else:
            time.sleep(5)  # Wait and retry if disconnected

# WebSocket route to handle connection events
@socketio.on('connect')
def handle_connect():
    emit('message', {'data': 'Connected to WebSocket!'})
    if not drone_connected:
        connect_drone()

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

# Handle drone control commands from WebSocket
@socketio.on('drone_command')
def handle_drone_command(data):
    if not drone_connected:
        emit('message', {'data': 'Drone is not connected'})
        return
    
    command = data['command']
    try:
        if command == 'takeoff':
            drone.takeoff()
            emit('message', {'data': 'Drone took off!'})
        elif command == 'land':
            drone.land()
            emit('message', {'data': 'Drone landed!'})
        elif command == 'move_forward':
            drone.move_forward(data['distance'])
            emit('message', {'data': f'Drone moved forward {data["distance"]} cm!'})
        elif command == 'move_back':
            drone.move_back(data['distance'])
            emit('message', {'data': f'Drone moved back {data["distance"]} cm!'})
        elif command == 'move_left':
            drone.move_left(data['distance'])
            emit('message', {'data': f'Drone moved left {data["distance"]} cm!'})
        elif command == 'move_right':
            drone.move_right(data['distance'])
            emit('message', {'data': f'Drone moved right {data["distance"]} cm!'})
        elif command == 'move_up':
            drone.move_up(data['distance'])
            emit('message', {'data': f'Drone moved up {data["distance"]} cm!'})
        elif command == 'move_down':
            drone.move_down(data['distance'])
            emit('message', {'data': f'Drone moved down {data["distance"]} cm!'})
        else:
            emit('message', {'data': 'Invalid command!'})
    except Exception as e:
        emit('message', {'data': f'Error: {str(e)}'})

# Video streaming via WebSocket
def stream_video():
    while True:
        if not drone_connected:
            break
        frame = drone.get_frame_read().frame
        if frame is not None:
            _, buffer = cv2.imencode('.jpg', frame)
            frame_data = buffer.tobytes()
            socketio.emit('video_frame', {'frame': frame_data}, broadcast=True)
            time.sleep(0.03)  # Control frame rate to around 30 FPS

@socketio.on('start_video')
def handle_start_video():
    threading.Thread(target=stream_video).start()

# Route to render the HTML page
@app.route('/', methods=['GET'])  # http://localhost:5000/
def index():
    return render_template('websocket.html')

# Route to get drone status
@app.route('/status', methods=['GET'])  # http://localhost:5000/status
def status():
    if not drone_connected:
        return jsonify({"error": "Drone not connected"}), 400

    # Fetching drone status information
    try:
        battery = drone.get_battery()
        height = drone.get_height()
        is_flying = drone.is_flying
        temp = drone.get_temperature()
        flight_time = drone.get_flight_time()
        wifi_strength = drone.query_wifi_signal_noise_ratio()

        return jsonify({
            "battery": f"{battery}%",
            "height": f"{height} cm",
            "is_flying": is_flying,
            "temperature": f"{temp} °C",
            "flight_time": f"{flight_time} seconds",
            "wifi_strength": wifi_strength
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Start the Flask-SocketIO server
if __name__ == '__main__':
    # Ensure no reloader to avoid multiple instances
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, use_reloader=False)
