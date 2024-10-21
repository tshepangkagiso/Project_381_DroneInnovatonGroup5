# Tello Drone Flask API

## Overview

This repository contains a Flask API for controlling a Tello drone. The API allows users to take off, land, check status, 
move in various directions, and stream video from the drone.

## Requirements

Before you begin, ensure you have the following installed on your system:

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

Ensure your project has the following structure:

```
your_project/
├── drone.py
└── templates/
    └── index.html
```

### HTML File

Create an `index.html` file in the `templates` folder with the following content:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Drone Video Feed</title>
    <style>
        body {
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
            background-color: #f0f0f0;
        }
        img {
            width: 640px; /* Set the desired width */
            height: auto; /* Maintain aspect ratio */
            border: 2px solid #333;
        }
        h1 {
            margin-bottom: 20px;
        }
    </style>
</head>
<body>
    <h1>Live Video Feed from Tello Drone</h1>
    <img src="{{ url_for('video_feed') }}" alt="Drone Video Feed">
</body>
</html>
```

## Running the Application

1. **Start the Flask Application**:
   Open your terminal, navigate to your project directory, and run:
   ```bash
   python drone.py
   ```

2. **Access the API**:
   Open a web browser and go to:
   ```
   http://localhost:5000/
   ```

3. **Testing API Endpoints**:
   Use the provided `.rest` file to test various API endpoints, or you can use a tool like Postman or curl to make HTTP requests to your endpoints.

### API Endpoints

- **GET** `/is_on`: Check if the drone is connected.
- **GET** `/status`: Get the drone's battery, height, flying status, etc.
- **GET** `/takeoff`: Command the drone to take off.
- **GET** `/land`: Command the drone to land.
- **POST** `/move/<direction>/<int:distance>`: Move the drone in a specified direction (e.g., forward, backward).
- **GET** `/video_feed`: Stream the video feed from the drone.

## Possible Challenges and Solutions

### 1. Drone Not Connecting
- **Challenge**: The drone fails to connect.
- **Solution**: Ensure that the Tello drone is powered on and connected to the same Wi-Fi network as your computer. You may also need to reset the drone or your Wi-Fi connection.

### 2. No Video Feed
- **Challenge**: The video feed does not display.
- **Solution**: Ensure that the drone is properly streaming video. Check the `generate_frames` function for any errors and ensure your drone supports video streaming. Additionally, verify that your browser can access the video stream at `http://localhost:5000/video_feed`.

### 3. API Response Errors
- **Challenge**: Receiving error messages from the API.
- **Solution**: Review the error message returned in the JSON response for more information. Ensure that you are using the correct HTTP method (GET or POST) and that you have provided valid parameters (like distance).

### 4. Environment Issues
- **Challenge**: Python or package version compatibility issues.
- **Solution**: Ensure you are using compatible versions of Python and packages. Consider using a virtual environment to isolate your dependencies:
  ```bash
  python -m venv venv
  source venv/bin/activate  # On Windows use `venv\Scripts\activate`
  pip install Flask djitellopy opencv-python
  ```

### 5. Firewall Issues
- **Challenge**: Localhost connection issues due to firewall restrictions.
- **Solution**: Check your firewall settings to ensure they are not blocking the Flask application. You may need to allow Python or the specific port (5000) through your firewall.

## Conclusion

This Flask API provides a simple way to control and monitor a Tello drone. By following the setup instructions and addressing potential challenges, you should be able to operate the drone smoothly. If you encounter any issues not covered in this documentation, consider checking the documentation for Flask, djitellopy, or seeking help from community forums.