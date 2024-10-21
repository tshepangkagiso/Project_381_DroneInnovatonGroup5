# Drone Control API

## Overview

This project is a **Flask-based web application** for controlling a Tello drone. It provides users with a dashboard interface to monitor the drone's status, issue control commands, and stream live video from the drone’s camera.

## Features

- **Drone Control**: Perform takeoff, landing, and movement in various directions.
- **Live Video Feed**: Stream real-time video from the drone’s camera.
- **Drone Status Monitoring**: Display vital information like battery percentage, flight time, and altitude.
- **Offline Handling**: Detects if the drone is disconnected and displays an offline status page.

## Requirements

Before running the application, ensure you have the following installed:

- **Python 3.x**
- **Flask**: Install via pip
    ```bash
    pip install Flask
    ```
- **Djitellopy**: Install via pip
    ```bash
    pip install djitellopy
    ```
- **OpenCV**: Install via pip
    ```bash
    pip install opencv-python
    ```

## Project Structure

Your project should have the following structure:

```
your_project/
├── app.py                # Main Flask app
├── drone.py              # Drone control logic
├── udpDrone.py           # UDP communication logic
├── apiTest.http          # HTTP API testing script
├── templates/
│   ├── index.html        # Dashboard template
│   └── offline.html      # Offline page template
└── static/
    └── styles.css        # Custom styles for the web interface
```

## Running the Application

1. **Start the Flask Application**:
   - Open a terminal, navigate to your project directory, and run:
     ```bash
     python app.py
     ```

2. **Access the Web Dashboard**:
   - Open your browser and navigate to:
     ```
     http://localhost:5000/
     ```
   - From the dashboard, you can monitor the drone’s status, view the live video feed, and issue control commands.

## API Endpoints

You can also interact with the drone using the following API endpoints:

- **GET** `/is_on`: Check if the drone is connected.
- **GET** `/status`: Retrieve the drone's current status (battery, height, etc.).
- **GET** `/takeoff`: Command the drone to take off.
- **GET** `/land`: Command the drone to land.
- **POST** `/move/<direction>/<int:distance>`: Move the drone in a specified direction (e.g., `/move/forward/50`).
- **GET** `/video_feed`: Stream the live video feed from the drone.

## Handling Drone Connection Issues

### Drone Initialization

- At startup, the app attempts to connect to the drone using the `drone.connect()` command.
- If the drone is not available, an exception will be raised. To prevent the app from crashing when this occurs, wrap the `drone.connect()` call in a `try-except` block.

Example:
```python
try:
    drone.connect()
except Exception as e:
    print(f"Failed to connect to the drone: {e}")
```

### Offline Handling

- Users can still access the web interface even if the drone is not connected.
- When users interact with the controls (e.g., takeoff, landing, movement) or try to fetch the drone's status, the app checks if the drone is connected.
- If the drone is offline, the user is redirected to the `/offline` page, which informs them that the drone is not available.

### Video Feed Handling

- If the drone is offline, the live video feed will not be available.
- The `/video_feed` route checks the drone’s connection and redirects to the offline page if the connection fails.

## Expected Workflow When Drone is Not Connected

1. **App Start**: 
   - The Flask server starts normally, even if the drone is not connected.
   
2. **Dashboard Access**: 
   - Users can visit the dashboard at `http://localhost:5000/` and interact with the interface.
   
3. **Drone Controls**: 
   - If the drone is offline and users try to control the drone or view the video feed, they will be redirected to the offline page.

4. **Retrying**: 
   - On the offline page, users can click the "Retry" button to attempt reconnecting to the dashboard.

## Possible Challenges and Solutions

### 1. Drone Not Connecting
- **Challenge**: The drone fails to connect at startup.
- **Solution**: Ensure the Tello drone is powered on and connected to the same Wi-Fi network as your computer. If the connection fails, check your network or restart the drone.

### 2. No Video Feed
- **Challenge**: The live video feed is not displaying on the dashboard.
- **Solution**: Ensure the drone supports video streaming, and check that the `/video_feed` route is working correctly.

### 3. API Errors
- **Challenge**: Receiving errors when interacting with the API.
- **Solution**: Verify you are using the correct HTTP method and providing valid parameters. Review any error messages returned by the API for troubleshooting.

### 4. Firewall Issues
- **Challenge**: Localhost access is blocked due to firewall settings.
- **Solution**: Check your firewall and network settings to ensure that connections to localhost and port 5000 are not being blocked.

## Conclusion

This Flask application provides a simple and effective interface for controlling and monitoring a Tello drone. By following the setup instructions and addressing potential issues, you should be able to operate the drone smoothly. If further issues arise, consult the documentation for Flask, djitellopy, or seek assistance from online communities.
