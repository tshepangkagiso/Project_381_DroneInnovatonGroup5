// Initialize socket connection
const socket = io(window.location.origin);
const connectionStatus = document.getElementById('connectionStatus');
const logContainer = document.getElementById('logContainer');
const videoFeed = document.getElementById('video_feed');
const toggleVideoBtn = document.getElementById('toggleVideo');
let isVideoActive = false;

// Connection handling
socket.on('connect', () => {
    connectionStatus.textContent = 'Connected';
    connectionStatus.classList.remove('disconnected');
    addLog('Connected to drone control system');
});

socket.on('disconnect', () => {
    connectionStatus.textContent = 'Disconnected';
    connectionStatus.classList.add('disconnected');
    addLog('Disconnected from drone control system');
});

// Message handling
socket.on('message', (data) => {
    addLog(data.data);
});

// Video handling
socket.on('video_frame', (data) => {
    if (videoFeed && isVideoActive) {
        videoFeed.src = `data:image/jpeg;base64,${btoa(String.fromCharCode.apply(null, new Uint8Array(data.frame)))}`;
    }
});

// Logging function
function addLog(message) {
    const logEntry = document.createElement('div');
    logEntry.className = 'log-entry';
    logEntry.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
    logContainer.appendChild(logEntry);
    logContainer.scrollTop = logContainer.scrollHeight;

    // Keep only last 100 logs
    while (logContainer.children.length > 100) {
        logContainer.removeChild(logContainer.firstChild);
    }
}

// Video control
toggleVideoBtn.addEventListener('click', () => {
    isVideoActive = !isVideoActive;
    if (isVideoActive) {
        socket.emit('start_video');
        toggleVideoBtn.textContent = 'Stop Video';
        addLog('Starting video stream');
    } else {
        toggleVideoBtn.textContent = 'Start Video';
        videoFeed.src = '';
        addLog('Stopping video stream');
    }
});

// Drone commands
function sendCommand(command) {
    socket.emit('drone_command', { command });
    addLog(`Sending command: ${command}`);
}

function sendMoveCommand(direction, distance) {
    socket.emit('drone_command', { command: direction, distance });
    addLog(`Sending movement command: ${direction} ${distance}cm`);
}

// Status updates
async function fetchStatus() {
    try {
        const response = await fetch('/status');
        const data = await response.json();
        
        if (response.ok) {
            updateStatusDisplay(data);
            addLog('Status updated successfully');
        } else {
            throw new Error(data.error || 'Failed to fetch status');
        }
    } catch (error) {
        addLog(`Error fetching status: ${error.message}`);
    }
}

function updateStatusDisplay(data) {
    document.getElementById('battery').textContent = data.battery;
    document.getElementById('height').textContent = data.height;
    document.getElementById('temperature').textContent = data.temperature;
    document.getElementById('flight_time').textContent = data.flight_time;
    document.getElementById('is_flying').textContent = data.is_flying ? 'Flying' : 'Landed';
    document.getElementById('wifi_strength').textContent = data.wifi_strength;
}

// Initial status fetch
fetchStatus();

// Set up periodic status updates
setInterval(fetchStatus, 1000);

// Error handling for socket connection
socket.on('error', (error) => {
    addLog(`Socket error: ${error.message}`);
});

// Handle page visibility changes
document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        isVideoActive = false;
        videoFeed.src = '';
        toggleVideoBtn.textContent = 'Start Video';
    }
});

// Prevent accidental page navigation
window.addEventListener('beforeunload', (event) => {
    if (socket.connected) {
        event.preventDefault();
        event.returnValue = '';
    }
});