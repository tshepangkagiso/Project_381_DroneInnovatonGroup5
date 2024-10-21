#pip install Flask opencv-python numpy
#python udpDrone.py

from flask import Flask, Response, jsonify, render_template, redirect, url_for
import socket
import threading
import time
import cv2
import numpy as np

app = Flask(__name__)

# Tello drone IP and port
tello_address = ('192.168.10.1', 8889)
tello_video_address = ('0.0.0.0', 11111)

# Create UDP sockets for commands and video
command_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
command_socket.bind(('', 9000))
video_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
video_socket.bind(tello_video_address)

# Global variable to track drone availability
drone_online = False

# Function to send command and receive response
def send_command(command, retries=4):
    global drone_online
    try:
        for _ in range(retries):
            command_socket.sendto(command.encode('utf-8'), tello_address)
            response, _ = command_socket.recvfrom(1024)
            response = response.decode('utf-8')
            if response == 'ok':
                return response
        return None
    except Exception:
        drone_online = False
        return None

# Initialize drone and check if online
def initialize_drone():
    global drone_online
    response = send_command('command')
    if response == 'ok':
        send_command('streamon')  # Turn on video stream if drone is online
        drone_online = True
    else:
        drone_online = False

# Route to render the main page or redirect to offline page if the drone is unavailable
@app.route('/', methods=['GET'])
def index():
    if drone_online:
        return render_template('index.html')
    else:
        return redirect(url_for('offline'))

# Route checks if drone is on or off
@app.route('/is_on', methods=['GET'])
def is_on():
    if drone_online:
        return jsonify({"status": "Drone is ON"})
    else:
        return jsonify({"status": "Drone is OFF"})

# Route to get drone status
@app.route('/status', methods=['GET'])
def status():
    if not drone_online:
        return jsonify({"error": "Drone is offline"}), 500
    try:
        battery = send_command('battery?')
        height = send_command('height?')
        temp = send_command('temp?')
        flight_time = send_command('time?')
        wifi = send_command('wifi?')
        
        return jsonify({
            "battery": f"{battery}%",
            "height": f"{height} cm",
            "temperature": f"{temp} °C",
            "flight_time": f"{flight_time} seconds",
            "wifi_strength": wifi
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Route to command the drone to takeoff
@app.route('/takeoff', methods=['GET'])
def takeoff():
    if not drone_online:
        return jsonify({"error": "Drone is offline"}), 500
    try:
        response = send_command('takeoff')
        return jsonify({"message": f"Takeoff command sent. Response: {response}"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Route to command the drone to land
@app.route('/land', methods=['GET'])
def land():
    if not drone_online:
        return jsonify({"error": "Drone is offline"}), 500
    try:
        response = send_command('land')
        return jsonify({"message": f"Land command sent. Response: {response}"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Route to move the drone in a specified direction
@app.route('/move/<direction>/<distance>', methods=['POST'])
def move_drone(direction, distance):
    if not drone_online:
        return jsonify({"error": "Drone is offline"}), 500
    try:
        command = f"{direction} {distance}"
        response = send_command(command)
        return jsonify({"message": f"Movement command sent. Response: {response}"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Video streaming function
def receive_video_stream():
    packet_data = b''
    while drone_online:
        try:
            res_string, ip = video_socket.recvfrom(2048)
            packet_data += res_string
            if len(res_string) != 1460:  # This means we have received a complete frame
                frame = cv2.imdecode(np.frombuffer(packet_data, dtype=np.uint8), cv2.IMREAD_COLOR)
                if frame is not None:
                    ret, buffer = cv2.imencode('.jpg', frame)
                    frame = buffer.tobytes()
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
                packet_data = b''  # Reset the packet data after processing the frame
        except Exception as e:
            print(f"Error receiving video stream: {str(e)}")
            break  # Break if there's an error or if the drone is offline

# Route to get the video feed
@app.route('/video_feed', methods=['GET'])
def video_feed():
    if drone_online:
        return Response(receive_video_stream(), mimetype='multipart/x-mixed-replace; boundary=frame')
    else:
        return redirect(url_for('offline'))

# Route for the offline page
@app.route('/offline', methods=['GET'])
def offline():
    return render_template('offline.html')

# Start the server and initialize the drone
if __name__ == '__main__':
    initialize_drone()  # Check if the drone is online at the start
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)).start()

