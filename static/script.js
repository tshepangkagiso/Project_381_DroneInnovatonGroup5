let videoPlaying = true; // To track the video state

// Fetch drone status and update the UI
function getStatus() {
    fetch('/status')
        .then(response => response.json())
        .then(data => {
            document.getElementById('battery-status').textContent = data.battery;
            document.getElementById('height-status').textContent = data.height;
            document.getElementById('flight-time-status').textContent = data.flight_time;
            document.getElementById('temperature-status').textContent = data.temperature;
            document.getElementById('wifi-status').textContent = data.wifi_strength;
        })
        .catch(() => {
            window.location.href = '/offline';
        });
}

// Toggle video play/pause
function toggleVideo() {
    const videoFeed = document.getElementById('video-feed');
    const videoControlBtn = document.getElementById('video-control');

    if (videoPlaying) {
        // Stop the video feed
        videoFeed.src = ''; // Clear the src to stop the video
        videoControlBtn.textContent = 'Play Video'; // Update button text
    } else {
        // Start the video feed
        videoFeed.src = '/video_feed'; // Set the src to resume the video
        videoControlBtn.textContent = 'Pause Video'; // Update button text
    }
    videoPlaying = !videoPlaying; // Toggle the state
}

// Send takeoff command
function takeoff() {
    fetch('/takeoff')
        .then(response => response.json())
        .then(data => alert(data.message))
        .catch(() => window.location.href = '/offline');
}

// Send land command
function land() {
    fetch('/land')
        .then(response => response.json())
        .then(data => alert(data.message))
        .catch(() => window.location.href = '/offline');
}

// Send movement command
function move(direction, distance) {
    fetch(`/move/${direction}/${distance}`, { method: 'POST' })
        .then(response => response.json())
        .then(data => alert(data.message))
        .catch(() => window.location.href = '/offline');
}