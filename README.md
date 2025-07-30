# Security Drone Monitoring System

A full-stack surveillance system integrating DJI Tello drones with real-time video streaming, object detection (YOLO), and automated patrol routines. Designed for intelligent, autonomous monitoring with live feedback and threat alerts.

## Features

- **Drone Control & Automation**  
  Control DJI Tello drones with pre-defined patrol routes (square & random).

- **Real-Time Video Streaming**  
  Live video feed using OpenCV, with processed frames served to the frontend.

- **Object Detection**  
  YOLO-based threat detection and classification in real-time.

- **Secure Web Interface**  
  Node.js + Express frontend with JWT authentication and protected routes.

- **Socket.IO Integration**  
  Real-time communication for video feed, status updates, and threat alerts.

- **Modular Architecture**  
  Python backend for drone logic; JavaScript frontend for dashboard and control.

---

## Tech Stack

- **Backend**: Python, OpenCV, djitellopy, YOLO, asyncio, Socket.IO  
- **Frontend**: Node.js, Express.js, EJS, MongoDB, JWT  
- **Drone**: DJI Tello  
- **Other Tools**: Docker (optional), MongoDB Compass, REST & WebSocket APIs

---

## Installation

### Prerequisites
- Python 3.8+
- Node.js 14+
- MongoDB
- DJI Tello Drone
- Wi-Fi connection


<img width="943" height="508" alt="Image" src="https://github.com/user-attachments/assets/428e5880-3bef-45c7-95ab-c2390ebaf358" />
