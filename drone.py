# press and wait until it flashes orange and connect to the wifi
#pip install flask opencv-python djitellopy numpy opencv-contrib-python
#python drone.py

from flask import Flask, Response, jsonify, render_template, redirect, url_for
from djitellopy import Tello
import threading
import time
import cv2  

app = Flask(__name__)
drone = Tello()
drone_connected = False 

# Attempt to connect to the drone
try:
    drone.connect()
    drone_connected = True
except Exception as e:
    print(f"Drone connection failed: {e}")

# Keep-alive function to maintain connection
def send_keep_alive():
    while True:
        if check_drone_connection():
            try:
                drone.get_battery()  # Send battery command periodically to keep the drone active
                time.sleep(2)  # Send every 10 seconds (adjust as needed)
            except Exception as e:
                print(f"Keep-alive error: {e}")
        else:
            print("Drone is not connected. Keep-alive not sent.")
            time.sleep(7)  # Wait before trying again

# Start the keep-alive thread
keep_alive_thread = threading.Thread(target=send_keep_alive, daemon=True)
keep_alive_thread.start()

# Mock GPS sensor data
def get_gps_coordinates():
    # Replace with actual GPS sensor reading logic
    return {"latitude": 37.7749, "longitude": -122.4194}

# Check if the drone is connected
def check_drone_connection():
    return drone_connected and drone.is_connected()

# Route to render the HTML page
@app.route('/', methods=['GET'])  # http://localhost:5000/
def index():
    return render_template('index.html')

# Route to check if drone is on or off
@app.route('/is_on', methods=['GET'])  # http://localhost:5000/is_on
def is_on():
    if check_drone_connection():
        return jsonify({"status": "Drone is ON"})
    else:
        return redirect(url_for('offline'))

# Route to get drone status information
@app.route('/status', methods=['GET'])  # http://localhost:5000/status
def status():
    if not check_drone_connection():
        return redirect(url_for('offline'))

    # Fetching drone status information
    try:
        battery = drone.get_battery()
        height = drone.get_height()
        is_flying = drone.is_flying
        temp = drone.get_temperature()
        flight_time = drone.get_flight_time()
        wifi_strength = drone.query_wifi_signal_noise_ratio()

        # Return the status information as JSON
        return jsonify({
            "battery": f"{battery}%",
            "height": f"{height} cm",
            "is_flying": is_flying,
            "temperature": f"{temp} °C",
            "flight_time": f"{flight_time} seconds",
            "wifi_strength": wifi_strength
        })
    except Exception:
        return redirect(url_for('offline'))

# Route to command the drone to takeoff
@app.route('/takeoff', methods=['GET'])  # http://localhost:5000/takeoff
def takeoff():
    if not check_drone_connection():
        return redirect(url_for('offline'))
    drone.takeoff()
    return jsonify({"message": "Drone took off!"})

# Route to command the drone to land
@app.route('/land', methods=['GET'])  # http://localhost:5000/land
def land():
    if not check_drone_connection():
        return redirect(url_for('offline'))
    drone.land()
    return jsonify({"message": "Drone landed!"})

# Route to move the drone in a specific direction
@app.route('/move/<direction>/<int:distance>', methods=['POST'])  # http://localhost:5000/move/forward/50
def move(direction, distance):
    if not check_drone_connection():
        return redirect(url_for('offline'))

    try:
        if direction == 'forward':
            drone.move_forward(distance)
        elif direction == 'backward':
            drone.move_back(distance)
        elif direction == 'left':
            drone.move_left(distance)
        elif direction == 'right':
            drone.move_right(distance)
        elif direction == 'up':
            drone.move_up(distance)
        elif direction == 'down':
            drone.move_down(distance)
        else:
            return jsonify({"error": "Invalid direction!"}), 400
        
        return jsonify({"message": f"Drone moved {direction} by {distance} cm!"})
    except Exception:
        return redirect(url_for('offline'))

# Video streaming endpoint method
def generate_frames():
    drone.streamon()  # Start the video stream from the drone
    while True:
        frame = drone.get_frame_read().frame  # Read the current frame from the drone
        if frame is not None:
            ret, buffer = cv2.imencode('.jpg', frame)  # Encode the frame as a JPEG image
            frame = buffer.tobytes()  # Convert the encoded image to bytes
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')  # Yield frame in MJPEG format

# Route to get the video feed
@app.route('/video_feed', methods=['GET'])  # http://localhost:5000/video_feed
def video_feed():
    if not check_drone_connection():  # Check if the drone is connected
        return redirect(url_for('offline'))  # Redirect to offline page if not connected
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

# New route for moving to GPS coordinates
@app.route('/move_to_gps', methods=['POST'])  # http://localhost:5000/move_to_gps
def move_to_gps():
    if not check_drone_connection():  # Check if the drone is connected
        return redirect(url_for('offline'))  # Redirect if not connected

    initial_coordinates = get_gps_coordinates()  # Mock initial coordinates
    target_coordinates = get_gps_coordinates()  # Mock target coordinates

    try:
        print("Moving to GPS location...")
        # Simplified movement logic for demonstration
        drone.takeoff()
        drone.move_forward(100)  # Move forward for demonstration
        time.sleep(5)  # Hover for 5 seconds
        drone.land()
        
        return jsonify({"message": "Drone has moved to GPS location."})
    except Exception:
        return redirect(url_for('offline'))  # Redirect on error

# Route to render the offline page
@app.route('/offline', methods=['GET'])  # http://localhost:5000/offline
def offline():
    return render_template('offline.html')

# Run the Flask server in a separate thread
if __name__ == '__main__':
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)).start()
