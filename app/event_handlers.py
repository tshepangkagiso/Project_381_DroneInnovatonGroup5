import logging

logger = logging.getLogger(__name__)

def register_socket_events(socketio, drone_manager, video_streamer, control_thread):
    @socketio.on('connect')
    def handle_connect():
        """Handle client connection."""
        logger.info("Client connected")
        if not drone_manager.is_connected():
            if drone_manager.connect_drone():
                socketio.emit('message', {'data': 'Connected to drone successfully!'})
            else:
                socketio.emit('message', {'data': 'Failed to connect to drone'})
        else:
            socketio.emit('message', {'data': 'Already connected to drone'})

    @socketio.on('disconnect')
    def handle_disconnect():
        """Handle client disconnection."""
        logger.info("Client disconnected")
        video_streamer.stop_streaming()

    @socketio.on('drone_command')
    def handle_drone_command(data):
        """Handle drone control commands."""
        if not drone_manager.is_connected():
            socketio.emit('message', {'data': 'Drone is not connected'})
            return
        
        command = data.get('command')
        distance = data.get('distance', 30)  # Default distance of 30cm
        
        try:
            control_thread.start(drone_manager, command, distance)
            socketio.emit('message', {'data': f"Executing {command} command"})
        except Exception as e:
            logger.error(f"Error executing command {command}: {str(e)}")
            socketio.emit('message', {'data': f'Error: {str(e)}'})

    @socketio.on('start_video')
    def handle_start_video():
        """Handle video stream start request."""
        if not drone_manager.is_connected():
            socketio.emit('message', {'data': 'Drone not connected'})
            return
            
        logger.info("Received start_video request")
        try:
            success = video_streamer.start_streaming(drone_manager)
            socketio.emit('message', {
                'data': 'Video streaming started' if success else 'Video streaming failed to start'
            })
        except Exception as e:
            logger.error(f"Error starting video: {str(e)}")
            socketio.emit('message', {'data': f'Error starting video: {str(e)}'})

    @socketio.on('stop_video')
    def handle_stop_video():
        """Handle video stream stop request."""
        logger.info("Received stop_video request")
        video_streamer.stop_streaming()
        socketio.emit('message', {'data': 'Video streaming stopped'})