// API Configuration
const API_CONFIG = {
    BASE_URL: 'http://localhost:5000',
    SOCKET_PATH: '',
    ENDPOINTS: {
        STATUS: '/status',
        DRONE_COMMAND: '/drone_command',
        VIDEO: '/video_feed'
    }
};

// Initialize Socket.IO connection with the Flask server
const socket = io(API_CONFIG.BASE_URL, {
    path: API_CONFIG.SOCKET_PATH,
    transports: ['websocket'],
    reconnection: true,
    reconnectionAttempts: 5,
    reconnectionDelay: 1000
});

// DOM Elements
const elements = {
    videoFeed: document.getElementById('video-feed'),
    fpsCounter: document.getElementById('fps-counter'),
    connectionStatus: document.getElementById('connection-status'),
    startStreamBtn: document.getElementById('start-stream'),
    stopStreamBtn: document.getElementById('stop-stream'),
    batteryLevel: document.getElementById('drone-battery'),
    signalStrength: document.getElementById('drone-signal'),
    droneHeight: document.getElementById('drone-height'),
    droneTemp: document.getElementById('drone-temp')
};

// State Management
let isConnected = false;
let isStreaming = false;

// Socket Event Handlers
socket.on('connect', () => {
    isConnected = true;
    updateConnectionStatus(true);
    droneLogger.addLog('Connected to drone server', 'success');
});

socket.on('disconnect', () => {
    isConnected = false;
    updateConnectionStatus(false);
    droneLogger.addLog('Disconnected from drone server', 'danger');
});

// Command Functions
async function sendDroneCommand(command) {
    if (!isConnected) {
        droneLogger.addLog('Cannot send command: Drone not connected', 'warning');
        return;
    }

    try {
        const response = await fetch(`${API_CONFIG.BASE_URL}/drone_command`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ command })
        });

        const data = await response.json();
        
        if (response.ok) {
            droneLogger.addLog(`Command executed: ${command}`, 'success');
        } else {
            throw new Error(data.error || 'Command failed');
        }
    } catch (error) {
        droneLogger.addLog(`Command error: ${error.message}`, 'danger');
        console.error('Command error:', error);
    }
}

// Video Stream Handlers
elements.startStreamBtn.addEventListener('click', startVideoStream);
elements.stopStreamBtn.addEventListener('click', stopVideoStream);

async function startVideoStream() {
    if (!isConnected) {
        droneLogger.addLog('Cannot start stream: Drone not connected', 'warning');
        return;
    }

    try {
        socket.emit('start_video');
        isStreaming = true;
        updateStreamControls(true);
        droneLogger.addLog('Video stream started', 'success');
    } catch (error) {
        droneLogger.addLog(`Stream error: ${error.message}`, 'danger');
        console.error('Stream error:', error);
    }
}

async function stopVideoStream() {
    try {
        socket.emit('stop_video');
        isStreaming = false;
        updateStreamControls(false);
        elements.videoFeed.src = '';
        droneLogger.addLog('Video stream stopped', 'info');
    } catch (error) {
        droneLogger.addLog(`Stream error: ${error.message}`, 'danger');
        console.error('Stream error:', error);
    }
}

// Video Frame Handler
socket.on('video_frame', (data) => {
    if (isStreaming && data.frame) {
        elements.videoFeed.src = `data:image/jpeg;base64,${data.frame}`;
        updateFPSCounter();
    }
});

// Status Updates
let frameCount = 0;
let lastFrameTime = Date.now();

function updateFPSCounter() {
    frameCount++;
    const now = Date.now();
    if (now - lastFrameTime >= 1000) {
        elements.fpsCounter.textContent = `${frameCount} FPS`;
        frameCount = 0;
        lastFrameTime = now;
    }
}

function updateConnectionStatus(connected) {
    elements.connectionStatus.textContent = connected ? 'Connected' : 'Disconnected';
    elements.connectionStatus.style.color = connected ? '#22c55e' : '#ef4444';
}

function updateStreamControls(streaming) {
    elements.startStreamBtn.disabled = streaming;
    elements.stopStreamBtn.disabled = !streaming;
}

// Telemetry Updates
async function updateTelemetry() {
    if (!isConnected) return;

    try {
        const response = await fetch(`${API_CONFIG.BASE_URL}/status`);
        const data = await response.json();

        if (response.ok) {
            // Update telemetry displays
            elements.batteryLevel.textContent = data.battery;
            elements.signalStrength.textContent = data.wifi_strength;
            elements.droneHeight.textContent = data.height;
            elements.droneTemp.textContent = data.temperature;

            // Log critical status changes
            checkCriticalStatus(data);
        }
    } catch (error) {
        console.error('Telemetry error:', error);
    }
}

// Critical Status Checks
function checkCriticalStatus(data) {
    if (data.battery <= 20) {
        droneLogger.addLog(`Low battery warning: ${data.battery}%`, 'warning');
    }
    if (parseInt(data.height) > 100) {
        droneLogger.addLog(`High altitude warning: ${data.height}m`, 'warning');
    }
    if (data.wifi_strength < 50) {
        droneLogger.addLog(`Weak signal warning: ${data.wifi_strength}%`, 'warning');
    }
}

// Message Handler
socket.on('message', (data) => {
    droneLogger.addLog(data.data, 'info');
});

// Error Handler
socket.on('error', (error) => {
    droneLogger.addLog(`Error: ${error.message || 'Unknown error'}`, 'danger');
    console.error('Socket error:', error);
});

// Start telemetry updates
setInterval(updateTelemetry, 1000);

// Export functions for global access
window.sendDroneCommand = sendDroneCommand;
window.startVideoStream = startVideoStream;
window.stopVideoStream = stopVideoStream;