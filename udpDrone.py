#pip install Flask opencv-python numpy
#python udpDrone.py

from flask import Flask, Response, jsonify, render_template
import socket
import threading
import time
import cv2
import numpy as np

app = Flask(__name__)

# Tello drone IP and port
tello_address = ('192.168.10.1', 8889)
tello_video_address = ('0.0.0.0', 11111)

# Create UDP sockets
command_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
command_socket.bind(('', 9000))
video_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
video_socket.bind(tello_video_address)

# Function to send command and receive response
def send_command(command):
    try:
        command_socket.sendto(command.encode('utf-8'), tello_address)
        response, _ = command_socket.recvfrom(1024)
        return response.decode('utf-8')
    except Exception as e:
        return str(e)

# Initialize drone
send_command('command')  # Enter SDK mode
send_command('streamon')  # Turn on video stream

# Route to render the HTML page
@app.route('/', methods=['GET'])  # http://localhost:5000/
def index():
    return render_template('index.html')

# Route checks if drone is on or off
@app.route('/is_on', methods=['GET'])  # http://localhost:5000/is_on
def is_on():
    try:
        response = send_command('command')
        if response == 'ok':
            return jsonify({"status": "Drone is ON"})
        else:
            return jsonify({"status": "Drone is OFF"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Route to get drone status information
@app.route('/status', methods=['GET'])  # http://localhost:5000/status
def status():
    try:
        # Fetching drone status information
        battery = send_command('battery?')
        height = send_command('height?')
        temp = send_command('temp?')
        time = send_command('time?')
        wifi = send_command('wifi?')
        
        # Return the status information as JSON
        return jsonify({
            "battery": f"{battery}%",
            "height": f"{height} cm",
            "temperature": f"{temp} °C",
            "flight_time": f"{time} seconds",
            "wifi_strength": wifi
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Route to command the drone to takeoff
@app.route('/takeoff', methods=['GET'])  # http://localhost:5000/takeoff
def takeoff():
    try:
        response = send_command('takeoff')
        return jsonify({"message": f"Takeoff command sent. Response: {response}"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Route to command the drone to land
@app.route('/land', methods=['GET'])  # http://localhost:5000/land
def land():
    try:
        response = send_command('land')
        return jsonify({"message": f"Land command sent. Response: {response}"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Route to move the drone in a specific direction
@app.route('/move/<direction>/<int:distance>', methods=['POST'])  # http://localhost:5000/move/forward/50
def move(direction, distance):
    try:
        if direction in ['forward', 'back', 'left', 'right', 'up', 'down']:
            response = send_command(f'{direction} {distance}')
            return jsonify({"message": f"Moved {direction} by {distance} cm. Response: {response}"})
        else:
            return jsonify({"error": "Invalid direction!"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Video streaming function
def receive_video_stream():
    packet_data = b''
    while True:
        try:
            res_string, ip = video_socket.recvfrom(2048)
            packet_data += res_string
            # End of frame
            if len(res_string) != 1460:
                frame = cv2.imdecode(np.frombuffer(packet_data, dtype=np.uint8), cv2.IMREAD_COLOR)
                if frame is not None:
                    ret, buffer = cv2.imencode('.jpg', frame)
                    frame = buffer.tobytes()
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
                packet_data = b''
        except Exception as e:
            print(f"Error receiving video stream: {str(e)}")

# Route to get the video feed
@app.route('/video_feed', methods=['GET'])  # http://localhost:5000/video_feed
def video_feed():
    return Response(receive_video_stream(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

# Run the Flask server
if __name__ == '__main__':
    # Run the app in a separate thread so that the drone can operate simultaneously
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)).start()