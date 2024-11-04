# Drone Surveillance System Technical Documentation

## Table of Contents
1. [Class Documentation](#1-class-documentation)
2. [Routes & API Documentation](#2-routes--api-documentation)
3. [WebSocket Interface](#3-websocket-interface)
4. [Frontend Integration](#4-frontend-integration)

# 1. Class Documentation

## DroneManager Class
**Location**: `models/drone_manager.py`

**Purpose**: Central controller for drone operations, handling connection, movement, and state management.

**Dependencies**:
- djitellopy==2.5.0
- threading
- time
- logging
- VideoStreamer (local class)
- typing

**Class Integration**:
- Used by `app.py` as primary drone controller
- Interfaces with `VideoStreamer` for video feed
- Utilized by `Patrol` class for movement execution

### Methods Breakdown:

#### `__init__(self, socketio)`
**Input**: 
- socketio: SocketIO instance

**Process**:
1. Initializes drone attributes
2. Sets up video streamer
3. Configures safety parameters
4. Initializes threading locks

**Output**: None

#### `connect_drone(self) -> bool`
**Input**: None

**Process**:
1. Attempts drone connection
2. Initializes video stream
3. Gets initial battery level
4. Starts keep-alive thread

**Output**:
- True: Connection successful
- False: Connection failed

```python
# Example Response
{
    "success": true,
    "battery_level": 85,
    "connection_status": "connected"
}
```

[Detailed breakdown of all DroneManager methods...]

## Patrol Class
**Location**: `models/patrol.py`

**Purpose**: Manages automated patrol routes and movement sequences.

**Dependencies**:
- logging
- os
- time
- threading
- typing
- enum
- queue
- DroneManager (local class)

**Class Integration**:
- Called by `app.py` for patrol routes
- Uses `DroneManager` for movement execution
- Interfaces with socket system for status updates

### Methods Breakdown:

[Detailed breakdown of all Patrol methods...]

## ObjectDetector Class
**Location**: `models/object_detector.py`

**Purpose**: Handles real-time object detection and threat assessment.

**Dependencies**:
- ultralytics
- opencv-python
- numpy
- logging
- typing
- time

**Class Integration**:
- Used by `VideoStreamer` for frame analysis
- Provides detection data for WebSocket events
- Interfaces with threat assessment system

### Methods Breakdown:

[Detailed breakdown of all ObjectDetector methods...]

## VideoStreamer Class
**Location**: `models/video_streamer.py`

**Purpose**: Manages video streaming and frame processing.

**Dependencies**:
- cv2
- threading
- time
- logging
- numpy
- base64
- ObjectDetector (local class)

**Class Integration**:
- Used by `DroneManager` for video feed
- Interfaces with `ObjectDetector` for frame analysis
- Provides data for WebSocket video events

### Methods Breakdown:

[Detailed breakdown of all VideoStreamer methods...]

# 2. Routes & API Documentation

## Patrol Routes

### POST /patrol/bl
**Purpose**: Initiates Bottom Left patrol sequence

**Process**:
1. Validates drone connection
2. Creates patrol thread
3. Executes movement sequence
4. Monitors completion

**Request**: None

**Response Success**:
```json
{
    "message": "Bottom Left patrol initiated",
    "status": 200
}
```

**Response Error**:
```json
{
    "error": "Drone not connected",
    "status": 400
}
```

[Detailed breakdown of all routes...]

# 3. WebSocket Interface

## Connection Events

### Event: 'connect'
**Purpose**: Establishes WebSocket connection and initializes drone

**Process**:
1. Client connects
2. Server attempts drone connection
3. Returns connection status
4. Begins status updates

**Client Code**:
```javascript
socket.on('connect', () => {
    console.log('Connected to server');
});
```

**Server Response**:
```json
{
    "data": "Connected to drone successfully!",
    "battery": 85,
    "type": "success"
}
```

[Detailed breakdown of all WebSocket events...]

# 4. Frontend Integration

## Essential JavaScript Setup

### Socket Connection
```javascript
const socket = io('http://localhost:5000', {
    transports: ['websocket'],
    reconnection: true,
    reconnectionAttempts: 5
});
```

### Video Stream Handler
```javascript
socket.on('video_frame', function(data) {
    const img = document.getElementById('drone-feed');
    img.src = `data:image/jpeg;base64,${data.frame}`;
    updateMetrics(data.fps);
});
```

[Complete JavaScript integration guide...]

# Application Integration (app.py)

## Initialization Flow
1. Flask and SocketIO setup
```python
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")
```

2. Component initialization
```python
drone_manager = DroneManager(socketio)
```

3. Route registration
```python
@app.route('/patrol/bl', methods=['POST'])
def patrol_bl():
    # Implementation
```

4. WebSocket event handlers
```python
@socketio.on('connect')
def handle_connect():
    # Implementation
```

[Complete application integration breakdown...]

# Complete Method Documentation

## DroneManager Class Methods

### move(self, direction: str, distance: int) -> bool
**Input**:
- direction: str (forward/back/left/right/up/down)
- distance: int (centimeters)

**Process**:
1. Validates connection
2. Checks battery level
3. Verifies safety parameters
4. Executes movement
5. Monitors completion

**Output**:
- True: Movement successful
- False: Movement failed

**Example Usage**:
```python
drone_manager.move("forward", 100)
```

[Detailed documentation of every method in each class...]

# Route Documentation

## Emergency Routes

### POST /drone/emergency
**Purpose**: Emergency landing procedure

**Implementation Location**: app.py

**Process Flow**:
1. Receives emergency request
2. Calls drone_manager.emergency_land()
3. Broadcasts status via WebSocket
4. Returns confirmation

**Response Success**:
```json
{
    "message": "Emergency landing executed",
    "status": 200
}
```

[Detailed documentation of every route...]

# WebSocket Event Documentation

## Status Events

### battery_update
**Purpose**: Real-time battery level updates

**Data Format**:
```json
{
    "battery": 85,
    "timestamp": 1645567890.123,
    "low_battery": false
}
```

**Client Implementation**:
```javascript
socket.on('battery_update', function(data) {
    updateBatteryIndicator(data.battery);
    checkLowBatteryWarning(data.low_battery);
});
```

[Detailed documentation of every WebSocket event...]

# Frontend Implementation Guide

## Essential Components

### Video Feed Setup
```html
<div id="video-container">
    <img id="drone-feed" alt="Drone Feed" />
    <div id="overlay">
        <span id="battery-indicator"></span>
        <span id="connection-status"></span>
    </div>
</div>
```

```javascript
// Video feed initialization
function initializeVideoFeed() {
    const feed = document.getElementById('drone-feed');
    socket.on('video_frame', (data) => {
        feed.src = `data:image/jpeg;base64,${data.frame}`;
    });
}
```

# Drone System Technical Documentation - Continued

## DroneManager Methods (Continued)

### start_keep_alive(self)
**Purpose**: Maintains drone connection and monitors vital stats

**Input**: None

**Process**:
1. Creates monitoring thread
2. Checks battery level every 30 seconds
3. Monitors connection status
4. Broadcasts updates via WebSocket

**Output**: None

**WebSocket Events Emitted**:
```json
{
    "battery_update": {
        "battery": 85,
        "timestamp": 1645567890.123,
        "low_battery": false
    }
}
```

### cleanup(self)
**Purpose**: Safely terminates drone operations

**Input**: None

**Process**:
1. Stops video streaming
2. Lands drone if flying
3. Terminates connection
4. Closes all threads
5. Cleans up resources

**Output**: None

### takeoff(self) -> bool
**Input**: None

**Process**:
1. Validates connection status
2. Checks battery level
3. Executes takeoff command
4. Monitors success

**Output**:
- True: Takeoff successful
- False: Takeoff failed

**Error Cases**:
```json
{
    "error": "Insufficient battery",
    "battery_level": 15,
    "min_required": 20
}
```

## VideoStreamer Methods

### start_streaming(self, drone) -> bool
**Purpose**: Initiates video stream processing

**Input**: 
- drone: Tello drone instance

**Process**:
1. Initializes streaming flags
2. Creates processing thread
3. Begins frame capture
4. Starts object detection
5. Broadcasts frames via WebSocket

**Output**:
- True: Stream started
- False: Stream failed

**WebSocket Events**:
```javascript
socket.on('video_frame', (data) => {
    {
        frame: "base64_encoded_image",
        timestamp: 1645567890.123,
        fps: 25.5,
        resolution: {
            width: 640,
            height: 480
        }
    }
});
```

### process_frame(self, frame: np.ndarray)
**Purpose**: Processes video frames for streaming and detection

**Input**:
- frame: numpy array of image data

**Process**:
1. Encodes original frame
2. Performs object detection
3. Updates tracking history
4. Calculates performance metrics
5. Emits various WebSocket events

**Output**: None

**WebSocket Events Emitted**:
```json
{
    "detection_frame": {
        "frame": "base64_encoded_image",
        "detections": [
            {
                "class": "person",
                "confidence": 0.92,
                "box": [100, 200, 150, 300],
                "threat_level": "low",
                "track_id": "track_123_456_789"
            }
        ],
        "timestamp": 1645567890.123
    },
    "performance_metrics": {
        "fps": 25.5,
        "processing_time": 0.04,
        "detection_count": 3
    }
}
```

## ObjectDetector Methods

### detect_objects(self, frame: np.ndarray) -> List[Dict]
**Purpose**: Performs object detection on video frames

**Input**:
- frame: numpy array of image data

**Process**:
1. Runs YOLO detection
2. Processes detection results
3. Classifies threats
4. Calculates confidence scores
5. Generates tracking IDs

**Output**:
```python
[
    {
        "class": "person",
        "confidence": 0.92,
        "box": [x1, y1, x2, y2],
        "threat_level": "low",
        "track_id": "track_123_456_789",
        "movement": {
            "dx": 10,
            "dy": 5,
            "speed": 3.2
        }
    }
]
```

### _check_for_nearby_weapons(self, person_box: List[float], weapon_boxes: List[Dict]) -> Tuple[bool, List[str]]
**Purpose**: Analyzes weapon proximity to detected persons

**Input**:
- person_box: [x1, y1, x2, y2] coordinates
- weapon_boxes: List of detected weapon coordinates

**Process**:
1. Calculates person center point
2. Measures distances to weapons
3. Evaluates threat levels
4. Determines proximity alerts

**Output**:
```python
(
    True,  # Weapon nearby
    ["knife", "gun"]  # List of detected weapons
)
```

## Patrol Methods

### execute_patrol(self, patrol_point: PatrolPoint) -> bool
**Purpose**: Executes specified patrol sequence

**Input**:
- patrol_point: PatrolPoint enum (BL, TL, TR)

**Process**:
1. Validates drone status
2. Initializes patrol sequence
3. Executes movement pattern
4. Performs area scan
5. Returns to origin

**Output**:
- True: Patrol successfully initiated
- False: Patrol failed to start

**WebSocket Events Emitted**:
```json
{
    "patrol_status": {
        "status": "active",
        "current_point": "BL",
        "progress": 45,
        "timestamp": 1645567890.123
    }
}
```

## Additional Route Documentation

### GET /status
**Purpose**: Retrieves comprehensive system status

**Process**:
1. Collects drone status
2. Gathers patrol information
3. Checks video stream
4. Compiles system metrics

**Response**:
```json
{
    "drone": {
        "connected": true,
        "battery": 85,
        "flying": true,
        "height": 1.2
    },
    "patrol": {
        "active": false,
        "last_completed": "2024-02-23T15:30:00Z",
        "current_route": null
    },
    "video": {
        "streaming": true,
        "fps": 25.5,
        "resolution": "640x480"
    },
    "system": {
        "cpu_usage": 45,
        "memory_usage": 312,
        "uptime": 3600
    }
}
```

### POST /patrol/random/start
**Purpose**: Initiates random patrol sequence

**Process**:
1. Validates drone status
2. Creates patrol thread
3. Randomly selects points
4. Executes sequences

**Request**: None

**Response Success**:
```json
{
    "message": "Random patrol initiated",
    "status": 200,
    "patrol_id": "patrol_789",
    "initial_point": "TL"
}
```

**Response Error**:
```json
{
    "error": "Cannot start patrol",
    "reason": "Drone not connected",
    "status": 400
}
```

## WebSocket Event Details

### threat_alert
**Purpose**: Real-time threat detection notifications

**Trigger**: High-threat object detected

**Data Format**:
```json
{
    "threat_alert": {
        "level": "high",
        "type": "armed_person",
        "location": {
            "x": 320,
            "y": 240
        },
        "confidence": 0.95,
        "weapons_detected": ["gun"],
        "timestamp": 1645567890.123
    }
}
```

**Client Handler**:
```javascript
socket.on('threat_alert', (data) => {
    showAlert({
        type: data.threat_alert.level,
        message: `${data.threat_alert.type} detected`,
        location: data.threat_alert.location
    });
    
    highlightThreat(data.threat_alert.location);
    activateEmergencyProtocol(data.threat_alert.level);
});
```

## Frontend Implementation Details

### Patrol Control Interface
```javascript
class PatrolController {
    constructor(socket) {
        this.socket = socket;
        this.active = false;
        this.currentRoute = null;
    }

    startPatrol(route) {
        fetch(`/patrol/${route}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        })
        .then(response => response.json())
        .then(data => {
            this.active = true;
            this.currentRoute = route;
            this.updateInterface();
        })
        .catch(error => this.handleError(error));
    }

    updateInterface() {
        const statusElement = document.getElementById('patrol-status');
        statusElement.innerHTML = `
            <div class="status-indicator ${this.active ? 'active' : 'inactive'}">
                <span>Patrol Status: ${this.active ? 'Active' : 'Inactive'}</span>
                <span>Current Route: ${this.currentRoute || 'None'}</span>
            </div>
        `;
    }

    handleError(error) {
        console.error('Patrol error:', error);
        showNotification({
            type: 'error',
            message: 'Failed to start patrol'
        });
    }
}
```

### Video Stream Handler
```javascript
class VideoStreamHandler {
    constructor(socket) {
        this.socket = socket;
        this.canvas = document.getElementById('detection-canvas');
        this.ctx = this.canvas.getContext('2d');
        this.initializeEventListeners();
    }

    initializeEventListeners() {
        this.socket.on('video_frame', this.handleFrame.bind(this));
        this.socket.on('detection_frame', this.handleDetection.bind(this));
    }

    handleFrame(data) {
        const img = new Image();
        img.onload = () => {
            this.ctx.drawImage(img, 0, 0);
            this.updateMetrics(data);
        };
        img.src = `data:image/jpeg;base64,${data.frame}`;
    }

    handleDetection(data) {
        this.drawDetectionBoxes(data.detections);
        this.updateThreatDisplay(data.detections);
    }

    drawDetectionBoxes(detections) {
        detections.forEach(detection => {
            const [x, y, w, h] = detection.box;
            this.ctx.strokeStyle = this.getThreatColor(detection.threat_level);
            this.ctx.strokeRect(x, y, w, h);
            this.ctx.fillText(
                `${detection.class} (${detection.confidence.toFixed(2)})`,
                x, y - 5
            );
        });
    }

    getThreatColor(level) {
        const colors = {
            low: '#00ff00',
            medium: '#ffff00',
            high: '#ff0000'
        };
        return colors[level] || '#ffffff';
    }
}
```

# Drone System Technical Documentation - Part 3

## Complete Integration Guide

### 1. System Initialization Flow

```python
# app.py initialization sequence
def initialize_system():
    try:
        # Initialize core components
        drone_manager = DroneManager(socketio)
        
        # Setup error handlers
        setup_error_handlers(app)
        
        # Initialize patrol system
        patrol_system = drone_manager.drone.patrol
        
        # Start monitoring services
        start_monitoring_services()
        
        return True
    except Exception as e:
        logger.critical(f"System initialization failed: {e}")
        return False

def start_monitoring_services():
    # Battery monitoring
    @monitor.periodic_task(30)  # Every 30 seconds
    def check_battery():
        level = drone_manager.battery_level
        socketio.emit('battery_update', {
            'level': level,
            'timestamp': time.time()
        })
```

### 2. Complete Error Handling System

```python
# Error handling for all routes
def setup_error_handlers(app):
    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({
            'error': 'Bad Request',
            'message': str(e),
            'status': 400
        }), 400

    @app.errorhandler(500)
    def server_error(e):
        return jsonify({
            'error': 'Internal Server Error',
            'message': str(e),
            'status': 500
        }), 500

# Custom error responses
class DroneError:
    CONNECTION_FAILED = {
        'error': 'Connection Failed',
        'code': 'DRONE_001',
        'status': 500
    }
    
    LOW_BATTERY = {
        'error': 'Low Battery',
        'code': 'DRONE_002',
        'status': 400
    }
```

### 3. Complete WebSocket Event System

```python
# WebSocket event handlers
@socketio.on('connect')
def handle_connect():
    """
    Purpose: Handles new client connections
    Process: 
    1. Validates client
    2. Initializes connection
    3. Sends initial state
    """
    try:
        # Initialize connection
        session_id = request.sid
        
        # Get initial state
        initial_state = {
            'drone_status': drone_manager.get_status(),
            'video_status': drone_manager.video_streamer.is_streaming(),
            'patrol_status': drone_manager.drone.patrol.get_patrol_status()
        }
        
        # Emit initial state
        emit('initialization', initial_state)
        
    except Exception as e:
        emit('error', {
            'type': 'connection_error',
            'message': str(e)
        })

@socketio.on('disconnect')
def handle_disconnect():
    """
    Purpose: Handles client disconnection
    Process:
    1. Cleans up resources
    2. Updates tracking
    3. Logs event
    """
    try:
        session_id = request.sid
        cleanup_client_resources(session_id)
    except Exception as e:
        logger.error(f"Disconnect error: {e}")

@socketio.on('command')
def handle_command(data):
    """
    Purpose: Processes drone commands
    Input:
    {
        "command": "move",
        "parameters": {
            "direction": "forward",
            "distance": 100
        }
    }
    """
    try:
        command = data.get('command')
        params = data.get('parameters', {})
        
        result = execute_command(command, params)
        
        emit('command_result', {
            'status': 'success',
            'command': command,
            'result': result
        })
    except Exception as e:
        emit('command_result', {
            'status': 'error',
            'command': command,
            'error': str(e)
        })
```

### 4. Complete Frontend Integration Code

```javascript
// main.js - Complete frontend implementation

class DroneController {
    constructor() {
        this.socket = io('http://localhost:5000', {
            transports: ['websocket'],
            reconnection: true
        });
        
        this.videoHandler = new VideoStreamHandler(this.socket);
        this.patrolHandler = new PatrolHandler(this.socket);
        this.statusHandler = new StatusHandler(this.socket);
        
        this.initializeEventListeners();
    }
    
    initializeEventListeners() {
        // Socket connection events
        this.socket.on('connect', () => this.handleConnect());
        this.socket.on('disconnect', () => this.handleDisconnect());
        
        // Drone status events
        this.socket.on('status_update', (data) => this.handleStatusUpdate(data));
        this.socket.on('battery_update', (data) => this.handleBatteryUpdate(data));
        this.socket.on('error', (data) => this.handleError(data));
        
        // UI event listeners
        document.getElementById('takeoff-btn').addEventListener('click', () => this.takeoff());
        document.getElementById('land-btn').addEventListener('click', () => this.land());
        document.getElementById('emergency-btn').addEventListener('click', () => this.emergency());
    }
    
    handleConnect() {
        console.log('Connected to drone server');
        this.updateConnectionStatus(true);
    }
    
    handleDisconnect() {
        console.log('Disconnected from drone server');
        this.updateConnectionStatus(false);
    }
    
    handleStatusUpdate(data) {
        this.updateDroneStatus(data);
        this.updateUIElements(data);
    }
    
    handleBatteryUpdate(data) {
        const batteryIndicator = document.getElementById('battery-indicator');
        batteryIndicator.textContent = `Battery: ${data.level}%`;
        
        if (data.level < 20) {
            this.showLowBatteryWarning();
        }
    }
    
    handleError(data) {
        console.error('Drone error:', data);
        this.showErrorNotification(data);
    }
    
    // Drone control methods
    async takeoff() {
        try {
            const response = await fetch('/drone/takeoff', {
                method: 'POST'
            });
            const data = await response.json();
            
            if (data.status === 200) {
                this.showSuccessNotification('Takeoff successful');
            } else {
                this.showErrorNotification(data.error);
            }
        } catch (error) {
            this.handleError(error);
        }
    }
    
    // UI update methods
    updateConnectionStatus(connected) {
        const statusElement = document.getElementById('connection-status');
        statusElement.className = connected ? 'connected' : 'disconnected';
        statusElement.textContent = connected ? 'Connected' : 'Disconnected';
    }
    
    updateDroneStatus(data) {
        const statusElement = document.getElementById('drone-status');
        statusElement.innerHTML = `
            <div class="status-container">
                <div class="status-item">
                    <span class="label">Status:</span>
                    <span class="value">${data.status}</span>
                </div>
                <div class="status-item">
                    <span class="label">Battery:</span>
                    <span class="value">${data.battery}%</span>
                </div>
                <div class="status-item">
                    <span class="label">Height:</span>
                    <span class="value">${data.height}m</span>
                </div>
            </div>
        `;
    }
    
    showNotification(type, message) {
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.textContent = message;
        
        document.body.appendChild(notification);
        setTimeout(() => notification.remove(), 3000);
    }
}

class VideoStreamHandler {
    constructor(socket) {
        this.socket = socket;
        this.canvas = document.getElementById('video-canvas');
        this.ctx = this.canvas.getContext('2d');
        this.detectionOverlay = document.getElementById('detection-overlay');
        
        this.initializeVideoStream();
    }
    
    initializeVideoStream() {
        this.socket.on('video_frame', (data) => this.handleVideoFrame(data));
        this.socket.on('detection_frame', (data) => this.handleDetectionFrame(data));
    }
    
    handleVideoFrame(data) {
        const img = new Image();
        img.onload = () => {
            this.ctx.drawImage(img, 0, 0);
            this.updateStreamMetrics(data);
        };
        img.src = `data:image/jpeg;base64,${data.frame}`;
    }
    
    handleDetectionFrame(data) {
        this.drawDetections(data.detections);
        this.updateThreatIndicators(data.detections);
    }
}

class PatrolHandler {
    constructor(socket) {
        this.socket = socket;
        this.currentPatrol = null;
        this.initializePatrolControls();
    }
    
    initializePatrolControls() {
        document.getElementById('patrol-bl').addEventListener('click', () => this.startPatrol('bl'));
        document.getElementById('patrol-tl').addEventListener('click', () => this.startPatrol('tl'));
        document.getElementById('patrol-tr').addEventListener('click', () => this.startPatrol('tr'));
        document.getElementById('patrol-stop').addEventListener('click', () => this.stopPatrol());
    }
    
    async startPatrol(route) {
        try {
            const response = await fetch(`/patrol/${route}`, {
                method: 'POST'
            });
            const data = await response.json();
            
            if (data.status === 200) {
                this.currentPatrol = route;
                this.updatePatrolStatus('active', route);
            } else {
                this.handlePatrolError(data.error);
            }
        } catch (error) {
            this.handlePatrolError(error);
        }
    }
}

// Initialize the application
document.addEventListener('DOMContentLoaded', () => {
    const droneController = new DroneController();
});
```

### 5. Complete API Route Documentation

#### Status Routes

##### GET /status/battery
**Purpose**: Get current battery status

**Process**:
1. Queries drone manager
2. Checks battery threshold
3. Returns status data

**Response**:
```json
{
    "battery_level": 85,
    "low_battery": false,
    "estimated_time_remaining": 900,
    "charging": false
}
```

##### GET /status/system
**Purpose**: Get complete system status

**Process**:
1. Collects all subsystem statuses
2. Aggregates performance metrics
3. Returns comprehensive status

**Response**:
```json
{
    "drone": {
        "connected": true,
        "battery": 85,
        "flight_time": 300,
        "height": 1.2,
        "temperature": 25
    },
    "video": {
        "streaming": true,
        "fps": 25,
        "resolution": "640x480",
        "bandwidth_usage": 1500
    },
    "patrol": {
        "active": true,
        "current_route": "BL",
        "completion": 45,
        "next_waypoint": "TL"
    },
    "detections": {
        "total_objects": 3,
        "threats": 0,
        "processing_time": 0.05
    }
}
```

#### Control Routes

##### POST /control/move
**Purpose**: Execute precise movement

**Request**:
```json
{
    "direction": "forward",
    "distance": 100,
    "speed": 50
}
```

**Process**:
1. Validates parameters
2. Checks safety conditions
3. Executes movement
4. Monitors completion

**Response Success**:
```json
{
    "status": "success",
    "movement": {
        "completed": true,
        "actual_distance": 98,
        "time_taken": 2.3
    }
}
```

**Response Error**:
```json
{
    "status": "error",
    "error": "Movement blocked",
    "details": {
        "reason": "Obstacle detected",
        "position": [120, 45]
    }
}
```

### 6. WebSocket Event Reference

#### Video Events

##### video_frame
```javascript
socket.on('video_frame', (data) => {
    {
        frame: "base64_encoded_image",
        timestamp: 1645567890.123,
        metrics: {
            fps: 25.5,
            bitrate: 1500,
            resolution: {
                width: 640,
                height: 480
            }
        }
    }
});
```

##### detection_frame
```javascript
socket.on('detection_frame', (data) => {
    {
        frame: "base64_encoded_image",
        detections: [
            {
                type: "person",
                confidence: 0.95,
                box: [x1, y1, x2, y2],
                threat_level: "low",
                track_id: "track_123",
                metadata: {
                    size: "medium",
                    movement: {
                        direction: "north",
                        speed: 1.2
                    }
                }
            }
        ],
        processing: {
            time: 0.05,
            device: "GPU"
        }
    }
});
```

