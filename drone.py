# press and wait until it flashes orange and connect to the wifi
#pip install flask opencv-python djitellopy

from flask import Flask, Response, jsonify, render_template  
from djitellopy import Tello
import threading
import cv2

app = Flask(__name__) 
drone = Tello()  
drone.connect()  

# Route to render the HTML page
@app.route('/', methods=['GET'])  # http://localhost:5000/
def index():
    return render_template('index.html')  

# Route checks if drone is on or off
@app.route('/is_on', methods=['GET'])  # http://localhost:5000/is_on
def is_on():
    try:
        if drone.is_connected:
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
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Route to command the drone to takeoff
@app.route('/takeoff', methods=['GET'])  # http://localhost:5000/takeoff
def takeoff():
    try:
        drone.takeoff()
        return jsonify({"message": "Drone took off!"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Route to command the drone to land
@app.route('/land', methods=['GET'])  # http://localhost:5000/land
def land():
    try:
        drone.land()
        return jsonify({"message": "Drone landed!"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Route to move the drone in a specific direction
@app.route('/move/<direction>/<int:distance>', methods=['POST'])  # http://localhost:5000/move/forward/50
def move(direction, distance):
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
    except Exception as e:
        return jsonify({"error": str(e)}), 500

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
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

# Run the Flask server
if __name__ == '__main__':
    # Run the app in a separate thread so that the drone can operate simultaneously
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)).start()
