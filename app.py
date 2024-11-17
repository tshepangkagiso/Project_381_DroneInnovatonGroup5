from flask import Flask, render_template, jsonify, send_file
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import logging
import os
import sys
import signal
import asyncio
from functools import partial
from models.drone_manager import DroneManager
import time
import colorama
from colorama import Fore, Style
import socket
import psutil
from typing import Dict
from dataclasses import dataclass
from contextlib import contextmanager
from PIL import Image
from io import BytesIO
import threading


# Initialize colorama for colored console output
colorama.init()

@dataclass
class StartupMetrics:
    initialization_time: float = 0.0
    component_times: Dict[str, float] = None
    memory_usage: float = 0.0
    cpu_usage: float = 0.0
    port_status: str = ""
    network_status: str = ""
    component_status: Dict[str, bool] = None
    
    def __post_init__(self):
        self.component_times = {}
        self.component_status = {}

class StartupMonitor:
    def __init__(self):
        self.logger = logging.getLogger('startup_monitor')
        self.metrics = StartupMetrics()
        self.start_time = time.time()
        
    def validate_component(self, component, required_attrs):
        """Validate component has required attributes without initializing."""
        missing = [attr for attr in required_attrs if not hasattr(component, attr)]
        if missing:
            self.logger.error(f"{Fore.RED}Component missing required attributes: {missing}{Style.RESET_ALL}")
            return False
        return True

    def monitor_startup(self, app, socketio, drone_manager) -> bool:
        """Monitor and validate complete startup sequence without starting services."""
        try:
            print(f"\n{Fore.CYAN}{'='*50}")
            print("Starting System Validation")
            print(f"{'='*50}{Style.RESET_ALL}\n")

            # Check system resources
            resources = self.check_system_resources()
            self.metrics.memory_usage = resources['memory_available']
            self.metrics.cpu_usage = resources['cpu_percent']
            
            # Check port availability
            if not self.check_port_availability(5000):
                self.logger.error(f"{Fore.RED}Port 5000 is not available{Style.RESET_ALL}")
                return False
            
            # Validate components exist but don't start them
            with self.measure_component('drone_manager'):
                if not self.validate_component(drone_manager, 
                    ['connect_drone', 'cleanup', 'video_streamer']):
                    return False
                
            with self.measure_component('video_streamer'):
                if not self.validate_component(drone_manager.video_streamer,
                    ['start_streaming', 'stop_streaming']):
                    return False
                
            with self.measure_component('socket_io'):
                if not self.validate_component(socketio, 
                    ['emit', 'on', 'run']):
                    return False
                
            # Calculate total initialization time
            self.metrics.initialization_time = time.time() - self.start_time
            
            # Log startup summary
            self.log_startup_summary()
            
            return all(self.metrics.component_status.values())
            
        except Exception as e:
            self.logger.error(f"{Fore.RED}Startup monitoring failed: {e}{Style.RESET_ALL}")
            return False
            
    @contextmanager
    def measure_component(self, component_name: str):
        """Measure initialization time for a component."""
        start = time.time()
        try:
            yield
            duration = time.time() - start
            self.metrics.component_times[component_name] = duration
            self.metrics.component_status[component_name] = True
            print(f"{Fore.GREEN}✓ {component_name} validated successfully{Style.RESET_ALL}")
        except Exception as e:
            self.metrics.component_status[component_name] = False
            self.logger.error(f"{Fore.RED}{component_name} initialization failed: {e}{Style.RESET_ALL}")
            raise

    def check_port_availability(self, port: int) -> bool:
        """Check if port is available."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('localhost', port))
                print(f"{Fore.GREEN}✓ Port {port} is available{Style.RESET_ALL}")
                return True
        except:
            print(f"{Fore.RED}✗ Port {port} is in use{Style.RESET_ALL}")
            return False

    def check_system_resources(self) -> Dict:
        """Check system resource availability."""
        resources = {
            'memory_available': psutil.virtual_memory().available / (1024 * 1024),  # MB
            'cpu_percent': psutil.cpu_percent(),
            'disk_space': psutil.disk_usage('/').free / (1024 * 1024 * 1024)  # GB
        }
        
        print(f"{Fore.CYAN}System Resources:{Style.RESET_ALL}")
        print(f"Memory Available: {resources['memory_available']:.1f}MB")
        print(f"CPU Usage: {resources['cpu_percent']:.1f}%")
        print(f"Free Disk Space: {resources['disk_space']:.1f}GB\n")
        
        return resources
        
    def log_startup_summary(self) -> None:
        """Log detailed startup metrics."""
        summary = f"""
{Fore.CYAN}{'='*50}
Startup Summary
{'='*50}{Style.RESET_ALL}
Total initialization time: {self.metrics.initialization_time:.2f}s

Component Status:"""
        
        print(summary)
        for component, duration in self.metrics.component_times.items():
            status = f"{Fore.GREEN}✓{Style.RESET_ALL}" if self.metrics.component_status[component] else f"{Fore.RED}✗{Style.RESET_ALL}"
            print(f"{component}: {duration:.2f}s [{status}]")
        
        print(f"\n{Fore.CYAN}System Resources:{Style.RESET_ALL}")
        print(f"Memory Available: {self.metrics.memory_usage:.1f}MB")
        print(f"CPU Usage: {self.metrics.cpu_usage:.1f}%")
        print(f"{'='*50}\n")

# Configure logging with performance monitoring
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('drone.log')
    ]
)

# Separate loggers
keepalive_logger = logging.getLogger('keepalive')
keepalive_logger.setLevel(logging.INFO)

performance_logger = logging.getLogger('performance')
performance_logger.setLevel(logging.INFO)

# Main logger
logger = logging.getLogger(__name__)

# Initialize Flask with optimized settings
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'drone_secret!')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max-size
CORS(app)

# Initialize SocketIO with optimized settings
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode='threading',
    ping_timeout=10,
    ping_interval=5,
    max_http_buffer_size=16 * 1024 * 1024
)

# Initialize drone manager
drone_manager = DroneManager(socketio)

# Enhanced error handling
class DroneServerError(Exception):
    pass

# Routes
@app.route('/')
def index():
    """Render the main control interface."""
    return render_template('index.html')

@app.route('/status')
def get_status():
    """Get comprehensive drone status."""
    try:
        status = drone_manager.get_status()
        performance_logger.info(f"Status request successful: {status}")
        return jsonify(status)
    except Exception as e:
        logger.error(f"{Fore.RED}Error getting status: {e}{Style.RESET_ALL}")
        return jsonify({"error": str(e)}), 500

@app.route('/metrics')
def get_metrics():
    """Get performance metrics."""
    try:
        metrics = {
            'drone': drone_manager.get_status()['metrics'],
            'video': drone_manager.video_streamer.get_status()
        }
        return jsonify(metrics)
    except Exception as e:
        logger.error(f"{Fore.RED}Error getting metrics: {e}{Style.RESET_ALL}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/placeholder/<int:width>/<int:height>')
def placeholder(width: int, height: int):
    """Generate placeholder image for video feeds."""
    try:
        # Create a black image with text
        img = Image.new('RGB', (width, height), color='black')
        
        # Save to bytes
        img_io = BytesIO()
        img.save(img_io, 'JPEG', quality=70)
        img_io.seek(0)
        
        return send_file(img_io, mimetype='image/jpeg')
    except Exception as e:
        logger.error(f"Error generating placeholder: {e}")
        return "Error generating placeholder", 500

# Socket events
@socketio.on('connect')
def handle_connect():
    """Handle client connection with enhanced error handling and connection verification."""
    print(f"\n{Fore.CYAN}{'='*50}")
    print("NEW CLIENT CONNECTION")
    print(f"Time: {time.strftime('%H:%M:%S')}")
    print(f"{'='*50}{Style.RESET_ALL}")
    
    try:
        if not drone_manager.is_connected:
            print(f"\n{Fore.YELLOW}Starting Drone Connection Sequence...")
            print(f"{'='*30}")
            print("1. Checking WiFi connection...")
            print("2. Attempting drone connection...")
            print(f"{'='*30}{Style.RESET_ALL}")
            
            if drone_manager.connect_drone():
                battery = drone_manager.battery_level
                
                success_msg = f"""
{Fore.GREEN}✓ DRONE CONNECTED SUCCESSFULLY
{'='*30}
• Status: Online
• Battery: {battery}%
• Time: {time.strftime('%H:%M:%S')}
{'='*30}{Style.RESET_ALL}
"""
                print(success_msg)
                
                emit('message', {
                    'data': f'Connected to drone successfully! Battery: {battery}%',
                    'type': 'success'
                })
                emit('status_update', drone_manager.get_status())
            else:
                error_msg = f"""
{Fore.RED}✗ DRONE CONNECTION FAILED
{'='*30}
• Please check:
  1. Drone is powered on
  2. Connected to drone's WiFi
  3. Correct IP (192.168.10.1)
{'='*30}{Style.RESET_ALL}
"""
                print(error_msg)
                emit('message', {
                    'data': 'Failed to connect to drone. Please check power and WiFi connection.',
                    'type': 'error'
                })
        else:
            print(f"\n{Fore.YELLOW}Notice: Drone already connected{Style.RESET_ALL}")
            emit('message', {
                'data': 'Already connected to drone',
                'type': 'info'
            })
            emit('status_update', drone_manager.get_status())
    except Exception as e:
        error_msg = f"""
{Fore.RED}✗ CONNECTION ERROR
{'='*30}
Error: {str(e)}
Please check drone status and try again
{'='*30}{Style.RESET_ALL}
"""
        print(error_msg)
        emit('message', {
            'data': f'Connection error: {str(e)}',
            'type': 'error'
        })

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection with cleanup."""
    print(f"\n{Fore.YELLOW}{'='*50}")
    print("CLIENT DISCONNECTED")
    print(f"Time: {time.strftime('%H:%M:%S')}")
    print(f"{'='*50}{Style.RESET_ALL}")
    
    try:
        drone_manager.video_streamer.stop_streaming()
        print(f"{Fore.GREEN}✓ Video stream stopped successfully{Style.RESET_ALL}")
        performance_logger.info("Video streaming stopped on disconnect")
    except Exception as e:
        print(f"{Fore.RED}✗ Error during disconnect cleanup: {e}{Style.RESET_ALL}")
        logger.error(f"Disconnect error: {e}")

# Add this new monitoring event
@socketio.on('check_connection')
def handle_check_connection():
    """Monitor connection status."""
    try:
        if drone_manager.is_connected:
            status = {
                'connected': True,
                'battery': drone_manager.battery_level,
                'time': time.strftime('%H:%M:%S')
            }
            emit('connection_status', status)
        else:
            emit('connection_status', {'connected': False})
    except Exception as e:
        logger.error(f"Connection check error: {e}")
        emit('connection_status', {
            'connected': False,
            'error': str(e)
        })

@socketio.on('start_video')
def handle_start_video():
    """Start video streaming with performance monitoring."""
    if not drone_manager.is_connected:
        print(f"{Fore.RED}✗ Cannot start stream: Drone not connected{Style.RESET_ALL}")
        emit('message', {
            'data': 'Cannot start stream: Drone not connected',
            'type': 'error'
        })
        return

    try:
        success = drone_manager.video_streamer.start_streaming(drone_manager.drone)
        if success:
            print(f"{Fore.GREEN}✓ Video streaming started{Style.RESET_ALL}")
            emit('message', {
                'data': 'Video streaming started',
                'type': 'success'
            })
            performance_logger.info("Video streaming started successfully")
        else:
            print(f"{Fore.RED}✗ Failed to start video stream{Style.RESET_ALL}")
            emit('message', {
                'data': 'Failed to start video stream',
                'type': 'error'
            })
    except Exception as e:
        logger.error(f"{Fore.RED}Error starting video: {e}{Style.RESET_ALL}")
        emit('message', {
            'data': f'Error starting video: {str(e)}',
            'type': 'error'
        })

@socketio.on('stop_video')
def handle_stop_video():
    """Stop video streaming with cleanup."""
    try:
        drone_manager.video_streamer.stop_streaming()
        print(f"{Fore.GREEN}✓ Video streaming stopped{Style.RESET_ALL}")
        emit('message', {
            'data': 'Video streaming stopped',
            'type': 'info'
        })
        performance_logger.info("Video streaming stopped")
    except Exception as e:
        logger.error(f"{Fore.RED}Error stopping video: {e}{Style.RESET_ALL}")
        emit('message', {
            'data': f'Error stopping video: {str(e)}',
            'type': 'error'
        })

@socketio.on('threat_detected')
def handle_threat(data):
    """Handle threat detection events."""
    try:
        print(f"\n{Fore.RED}! THREAT DETECTED: {data}{Style.RESET_ALL}")
        socketio.emit('threat_alert', {
            'threat_data': data,
            'timestamp': time.time()
        })
    except Exception as e:
        logger.error(f"{Fore.RED}Error handling threat: {e}{Style.RESET_ALL}")

@socketio.on('takeoff')
def handle_takeoff():
    """Handle drone takeoff with safety checks."""
    try:
        if drone_manager.take_off():
            print(f"{Fore.GREEN}✓ Takeoff successful{Style.RESET_ALL}")
            emit('message', {
                'data': 'Takeoff successful',
                'type': 'success'
            })
            performance_logger.info("Takeoff successful")
        else:
            print(f"{Fore.RED}✗ Takeoff failed - Check battery and connection{Style.RESET_ALL}")
            emit('message', {
                'data': 'Takeoff failed - Check battery and connection',
                'type': 'error'
            })
    except Exception as e:
        logger.error(f"{Fore.RED}Takeoff error: {e}{Style.RESET_ALL}")
        emit('message', {
            'data': f'Takeoff error: {str(e)}',
            'type': 'error'
        })

@socketio.on('land')
def handle_land():
    """Handle drone landing with safety measures."""
    try:
        if drone_manager.land():
            print(f"{Fore.GREEN}✓ Landing successful{Style.RESET_ALL}")
            emit('message', {
                'data': 'Landing successful',
                'type': 'success'
            })
            performance_logger.info("Landing successful")
        else:
            print(f"{Fore.RED}! Landing failed - Initiating emergency procedures{Style.RESET_ALL}")
            emit('message', {
                'data': 'Landing failed - Initiating emergency procedures',
                'type': 'error'
            })
            drone_manager.emergency_stop()
    except Exception as e:
        logger.error(f"{Fore.RED}Landing error: {e}{Style.RESET_ALL}")
        emit('message', {
            'data': f'Landing error: {str(e)}',
            'type': 'error'
        })
        drone_manager.emergency_stop()

@socketio.on('emergency')
def handle_emergency():
    """Handle emergency stop command."""
    try:
        print(f"\n{Fore.RED}{'!'*50}")
        print("EMERGENCY STOP INITIATED")
        print(f"{'!'*50}{Style.RESET_ALL}")
        
        drone_manager.emergency_stop()
        emit('message', {
            'data': 'Emergency stop executed',
            'type': 'warning'
        })
        performance_logger.warning("Emergency stop triggered")
        print(f"{Fore.GREEN}✓ Emergency stop completed{Style.RESET_ALL}")
    except Exception as e:
        logger.error(f"{Fore.RED}Emergency stop error: {e}{Style.RESET_ALL}")
        emit('message', {
            'data': f'Emergency stop error: {str(e)}',
            'type': 'error'
        })

@socketio.on('command')
def handle_command(data):
    """Handle generic drone commands with rate limiting."""
    try:
        command = data.get('command')
        args = data.get('args', [])
        
        if not command:
            print(f"{Fore.RED}✗ Invalid command format{Style.RESET_ALL}")
            emit('message', {
                'data': 'Invalid command format',
                'type': 'error'
            })
            return
            
        result = drone_manager.send_command(command, *args)
        if result:
            print(f"{Fore.GREEN}✓ Command {command} executed successfully{Style.RESET_ALL}")
            emit('message', {
                'data': f'Command {command} executed successfully',
                'type': 'success'
            })
            performance_logger.info(f"Command executed: {command}")
        else:
            print(f"{Fore.RED}✗ Command {command} failed{Style.RESET_ALL}")
            emit('message', {
                'data': f'Command {command} failed',
                'type': 'error'
            })
    except Exception as e:
        logger.error(f"{Fore.RED}Command error: {e}{Style.RESET_ALL}")
        emit('message', {
            'data': f'Command error: {str(e)}',
            'type': 'error'
        })

@socketio.on('init_patrol')
def handle_init_patrol():
    """Initialize patrol capability."""
    try:
        drone_manager.init_patrol()
        print(f"{Fore.GREEN}✓ Patrol system initialized{Style.RESET_ALL}")
        emit('message', {
            'data': 'Patrol system initialized',
            'type': 'success'
        })
    except Exception as e:
        logger.error(f"{Fore.RED}Patrol initialization error: {e}{Style.RESET_ALL}")
        emit('message', {
            'data': f'Failed to initialize patrol: {str(e)}',
            'type': 'error'
        })


def background_task(app, coroutine):
    """Run coroutine in background with app context."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    with app.app_context():
        loop.run_until_complete(coroutine)
    loop.close()

@socketio.on('start_patrol')
def handle_start_patrol(data):
    """Handle patrol start with proper async execution."""
    try:
        patrol_type = data.get('type', 'clockwise')
        print(f"\n{Fore.CYAN}Starting {patrol_type} patrol...{Style.RESET_ALL}")
        
        if not drone_manager.patrol:
            # Initialize patrol synchronously first
            drone_manager.init_patrol()
        
        # Validate patrol conditions synchronously
        valid, message = drone_manager.patrol.validate_patrol_conditions()
        if not valid:
            print(f"{Fore.RED}✗ Cannot start patrol: {message}{Style.RESET_ALL}")
            emit('message', {
                'data': f'Cannot start patrol: {message}',
                'type': 'error'
            })
            return

        # Create the patrol coroutine based on type
        if patrol_type == 'clockwise':
            patrol_coro = drone_manager.patrol.clockwise_patrol()
        else:
            patrol_coro = drone_manager.patrol.counterclockwise_patrol()

        # Start patrol in background thread
        thread = threading.Thread(
            target=background_task,
            args=(app, patrol_coro),
            daemon=True
        )
        thread.start()

        emit('message', {
            'data': f'Starting {patrol_type} patrol',
            'type': 'success'
        })

    except Exception as e:
        logger.error(f"{Fore.RED}Patrol start error: {e}{Style.RESET_ALL}")
        emit('message', {
            'data': f'Patrol error: {str(e)}',
            'type': 'error'
        })

@socketio.on('stop_patrol')
def handle_stop_patrol():
    """Stop current patrol."""
    try:
        if drone_manager.patrol:
            if drone_manager.patrol.stop_patrol():
                print(f"{Fore.YELLOW}! Patrol stop requested{Style.RESET_ALL}")
                emit('message', {
                    'data': 'Patrol stop requested',
                    'type': 'info'
                })
            else:
                print(f"{Fore.RED}✗ Failed to stop patrol{Style.RESET_ALL}")
                emit('message', {
                    'data': 'Failed to stop patrol',
                    'type': 'error'
                })
    except Exception as e:
        logger.error(f"{Fore.RED}Patrol stop error: {e}{Style.RESET_ALL}")
        emit('message', {
            'data': f'Error stopping patrol: {str(e)}',
            'type': 'error'
        })

@socketio.on('get_patrol_status')
def handle_get_patrol_status():
    """Get current patrol status."""
    try:
        if drone_manager.patrol:
            status = drone_manager.patrol.get_status()
            emit('patrol_status', status)
        else:
            emit('patrol_status', {
                'status': 'not_initialized',
                'is_patrolling': False
            })
    except Exception as e:
        logger.error(f"{Fore.RED}Get patrol status error: {e}{Style.RESET_ALL}")
        emit('message', {
            'data': f'Error getting patrol status: {str(e)}',
            'type': 'error'
        })

@socketio.on('get_patrol_history')
def handle_get_patrol_history():
    """Get patrol history."""
    try:
        if drone_manager.patrol:
            history = drone_manager.patrol.get_patrol_history()
            emit('patrol_history', {'history': history})
        else:
            emit('patrol_history', {'history': []})
    except Exception as e:
        logger.error(f"{Fore.RED}Get patrol history error: {e}{Style.RESET_ALL}")
        emit('message', {
            'data': f'Error getting patrol history: {str(e)}',
            'type': 'error'
        })

def cleanup_handler(signum, frame):
    """Enhanced cleanup on shutdown."""
    print(f"\n{Fore.YELLOW}{'='*50}")
    print("Initiating System Shutdown...")
    print(f"{'='*50}{Style.RESET_ALL}")
    
    try:
        if drone_manager.patrol:
            drone_manager.patrol.cleanup()
            print(f"{Fore.GREEN}✓ Patrol system cleaned up{Style.RESET_ALL}")
            
        drone_manager.cleanup()
        print(f"{Fore.GREEN}✓ Drone manager cleaned up{Style.RESET_ALL}")
        performance_logger.info("Cleanup completed")
        
        print(f"\n{Fore.GREEN}System shutdown completed successfully{Style.RESET_ALL}")
    except Exception as e:
        logger.error(f"{Fore.RED}Cleanup error: {e}{Style.RESET_ALL}")
    finally:
        sys.exit(0)

if __name__ == '__main__':
    try:
        print(f"\n{Fore.CYAN}{'='*50}")
        print("DRONE CONTROL SYSTEM")
        print(f"{'='*50}{Style.RESET_ALL}")
        
        # Initialize startup monitor
        startup_monitor = StartupMonitor()
        
        # Register cleanup handlers
        signal.signal(signal.SIGINT, cleanup_handler)
        signal.signal(signal.SIGTERM, cleanup_handler)
        
        print(f"\n{Fore.CYAN}Starting system initialization...{Style.RESET_ALL}")
        
        # Monitor complete startup sequence
        if startup_monitor.monitor_startup(app, socketio, drone_manager):
            print(f"\n{Fore.GREEN}System initialization successful!")
            
            # Attempt immediate drone connection since WiFi is already connected
            print(f"\n{Fore.YELLOW}Detecting drone connection...{Style.RESET_ALL}")
            try:
                if drone_manager.connect_drone():
                    battery = drone_manager.battery_level
                    
                    # Get additional drone info
                    try:
                        temp = drone_manager.drone.get_temperature()
                        height = drone_manager.get_height()
                        sdk = drone_manager.drone.get_sdk_version()
                        
                        success_msg = f"""
{Fore.GREEN}✓ DRONE CONNECTED SUCCESSFULLY
{'='*50}
• Status: Online
• Battery: {battery}%
• Temperature: {temp}°C
• Height: {height}cm
• SDK Version: {sdk}
• Time: {time.strftime('%H:%M:%S')}
{'='*50}{Style.RESET_ALL}
"""
                    except:
                        success_msg = f"""
{Fore.GREEN}✓ DRONE CONNECTED SUCCESSFULLY
{'='*50}
• Status: Online
• Battery: {battery}%
• Time: {time.strftime('%H:%M:%S')}
{'='*50}{Style.RESET_ALL}
"""
                    print(success_msg)
                    
                    print(f"\n{Fore.CYAN}Starting server on port 5000...")
                    print(f"{'='*50}")
                    print(f"Available at:")
                    print(f"• Local: http://127.0.0.1:5000")
                    print(f"• Network: http://192.168.10.2:5000")
                    print(f"{'='*50}{Style.RESET_ALL}")
                    
                    # Start server with optimized settings
                    socketio.run(
                        app,
                        host='0.0.0.0',
                        port=5000,
                        debug=False,
                        use_reloader=False,
                        allow_unsafe_werkzeug=True
                    )
                else:
                    print(f"\n{Fore.RED}{'='*50}")
                    print("CONNECTION FAILED")
                    print("Please check:")
                    print("1. Drone is powered on")
                    print("2. Connected to drone's WiFi (TELLO-XXXXX)")
                    print("3. No other devices are connected")
                    print(f"{'='*50}{Style.RESET_ALL}")
                    sys.exit(1)
                    
            except Exception as e:
                print(f"\n{Fore.RED}{'='*50}")
                print(f"CONNECTION ERROR: {str(e)}")
                print("Please verify drone status and try again")
                print(f"{'='*50}{Style.RESET_ALL}")
                sys.exit(1)
                
        else:
            error_msg = "Failed to start server - component initialization failed"
            print(f"\n{Fore.RED}{'!'*50}")
            print(f"STARTUP ERROR: {error_msg}")
            print(f"{'!'*50}{Style.RESET_ALL}")
            logger.critical(error_msg)
            raise RuntimeError(error_msg)
            
    except Exception as e:
        print(f"\n{Fore.RED}{'!'*50}")
        print(f"FATAL ERROR: {str(e)}")
        print(f"{'!'*50}{Style.RESET_ALL}")
        logger.critical(f"Server startup failed: {e}")
        
        if drone_manager.patrol:
            drone_manager.patrol.cleanup()
        drone_manager.cleanup()
        sys.exit(1)