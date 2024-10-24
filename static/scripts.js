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
    // Reset video state on disconnect
    isVideoActive = false;
    if (videoFeed) videoFeed.src = '';
    toggleVideoBtn.textContent = 'Start Video';
});

// Message handling
socket.on('message', (data) => {
    addLog(data.data);
});

// Video handling
socket.on('video_frame', (data) => {
    if (videoFeed && isVideoActive) {
        // Use the base64 encoded frame directly
        videoFeed.src = `data:image/jpeg;base64,${data.frame}`;
    }
});

// Logging function with timestamp
function addLog(message) {
    const logEntry = document.createElement('div');
    logEntry.className = 'log-entry';
    logEntry.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
    logContainer.appendChild(logEntry);
    logContainer.scrollTop = logContainer.scrollHeight;

    // Keep only last 100 logs for performance
    while (logContainer.children.length > 100) {
        logContainer.removeChild(logContainer.firstChild);
    }
}

// Video control with improved error handling
toggleVideoBtn.addEventListener('click', () => {
    isVideoActive = !isVideoActive;
    if (isVideoActive) {
        socket.emit('start_video');
        toggleVideoBtn.textContent = 'Stop Video';
        addLog('Starting video stream');
    } else {
        socket.emit('stop_video');  // Added explicit stop command
        toggleVideoBtn.textContent = 'Start Video';
        if (videoFeed) videoFeed.src = '';
        addLog('Stopping video stream');
    }
});

// Drone commands with improved feedback
function sendCommand(command) {
    if (!socket.connected) {
        addLog('Error: Not connected to drone');
        return;
    }
    socket.emit('drone_command', { command });
    addLog(`Sending command: ${command}`);
}

function sendMoveCommand(direction, distance) {
    if (!socket.connected) {
        addLog('Error: Not connected to drone');
        return;
    }
    socket.emit('drone_command', { command: direction, distance });
    addLog(`Sending movement command: ${direction} ${distance}cm`);
}

// Status updates with error handling and retry
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
        connectionStatus.textContent = 'Error';
        connectionStatus.classList.add('disconnected');
    }
}

// Update status display with formatting
function updateStatusDisplay(data) {
    const elements = {
        'battery': data.battery,
        'height': data.height,
        'temperature': data.temperature,
        'flight_time': data.flight_time,
        'is_flying': data.is_flying ? 'Flying' : 'Landed',
        'wifi_strength': data.wifi_strength
    };

    for (const [id, value] of Object.entries(elements)) {
        const element = document.getElementById(id);
        if (element) {
            element.textContent = value;
            // Add visual indicator for battery level
            if (id === 'battery') {
                const batteryLevel = parseInt(value);
                element.style.color = batteryLevel <= 20 ? '#dc2626' : 
                                    batteryLevel <= 50 ? '#f59e0b' : '#16a34a';
            }
        }
    }
}

// Initial status fetch
fetchStatus();

// Set up periodic status updates with error handling
const statusInterval = 1000; // 1 second
let statusTimer = setInterval(fetchStatus, statusInterval);

// Error handling for socket connection
socket.on('error', (error) => {
    addLog(`Socket error: ${error.message}`);
    connectionStatus.textContent = 'Error';
    connectionStatus.classList.add('disconnected');
});

// Handle page visibility changes to conserve resources
document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        // Stop video when page is not visible
        if (isVideoActive) {
            isVideoActive = false;
            socket.emit('stop_video');
            if (videoFeed) videoFeed.src = '';
            toggleVideoBtn.textContent = 'Start Video';
        }
        // Pause status updates
        clearInterval(statusTimer);
    } else {
        // Resume status updates when page becomes visible
        fetchStatus();
        statusTimer = setInterval(fetchStatus, statusInterval);
    }
});

// Prevent accidental page navigation while connected
window.addEventListener('beforeunload', (event) => {
    if (socket.connected) {
        event.preventDefault();
        event.returnValue = '';
    }
});

// Cleanup function for page unload
window.addEventListener('unload', () => {
    // Stop video stream
    if (isVideoActive) {
        socket.emit('stop_video');
    }
    // Clear intervals
    clearInterval(statusTimer);
    // Disconnect socket
    socket.disconnect();
});

// Handle window resize for video feed optimization
let resizeTimeout;
window.addEventListener('resize', () => {
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(() => {
        if (isVideoActive) {
            // Briefly pause and resume video to adjust to new size
            videoFeed.src = '';
            setTimeout(() => {
                if (isVideoActive) {
                    socket.emit('start_video');
                }
            }, 100);
        }
    }, 250);
});