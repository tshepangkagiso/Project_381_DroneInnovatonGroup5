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

async def execute_drone_command(command_func, *args, success_msg="Command executed successfully", error_msg="Command failed"):
    """Generic drone command executor with proper async handling."""
    try:
        # Create async task
        result = await command_func(*args)
        
        if result:
            print(f"{Fore.GREEN}✓ {success_msg}{Style.RESET_ALL}")
            emit('message', {'data': success_msg, 'type': 'success'})
            performance_logger.info(success_msg)
            return True
        else:
            print(f"{Fore.RED}✗ {error_msg}{Style.RESET_ALL}")
            emit('message', {'data': error_msg, 'type': 'error'})
            return False
            
    except Exception as e:
        error_detail = f"{error_msg}: {str(e)}"
        logger.error(f"{Fore.RED}{error_detail}{Style.RESET_ALL}")
        emit('message', {'data': error_detail, 'type': 'error'})
        return False

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
        img = Image.new('RGB', (width, height), color='black')
        img_io = BytesIO()
        img.save(img_io, 'JPEG', quality=70)
        img_io.seek(0)
        return send_file(img_io, mimetype='image/jpeg')
    except Exception as e:
        logger.error(f"Error generating placeholder: {e}")
        return "Error generating placeholder", 500

# Socket Events Helper
def run_async_command(command_func, *args):
    """Run async command in background thread."""
    async def async_wrapper():
        try:
            await command_func(*args)
        except Exception as e:
            logger.error(f"Async command error: {e}")
            
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(async_wrapper())
    finally:
        loop.close()

# Socket Events - Connection
@socketio.on('connect')
def handle_connect():
    """Handle client connection with enhanced error handling."""
    try:
        if not drone_manager.is_connected:
            print(f"\n{Fore.YELLOW}Starting Drone Connection Sequence...")
            if drone_manager.connect_drone():
                battery = drone_manager.battery_level
                emit('message', {
                    'data': f'Connected to drone successfully! Battery: {battery}%',
                    'type': 'success'
                })
                emit('status_update', drone_manager.get_status())
            else:
                emit('message', {
                    'data': 'Failed to connect to drone. Please check power and WiFi connection.',
                    'type': 'error'
                })
        else:
            emit('message', {
                'data': 'Already connected to drone',
                'type': 'info'
            })
            emit('status_update', drone_manager.get_status())
    except Exception as e:
        emit('message', {
            'data': f'Connection error: {str(e)}',
            'type': 'error'
        })

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection with cleanup."""
    try:
        drone_manager.video_streamer.stop_streaming()
        performance_logger.info("Video streaming stopped on disconnect")
    except Exception as e:
        logger.error(f"Disconnect error: {e}")

# Socket Events - Basic Controls
@socketio.on('takeoff')
def handle_takeoff():
    """Handle drone takeoff."""
    thread = threading.Thread(
        target=run_async_command,
        args=(drone_manager.take_off,),
        daemon=True
    )
    thread.start()

@socketio.on('land')
def handle_land():
    """Handle drone landing."""
    thread = threading.Thread(
        target=run_async_command,
        args=(drone_manager.land,),
        daemon=True
    )
    thread.start()

@socketio.on('emergency')
def handle_emergency():
    """Handle emergency stop."""
    thread = threading.Thread(
        target=run_async_command,
        args=(drone_manager.emergency_stop,),
        daemon=True
    )
    thread.start()

# Socket Events - Pattern Commands
@socketio.on('perimeter')
def handle_perimeter():
    """Handle perimeter patrol."""
    thread = threading.Thread(
        target=run_async_command,
        args=(drone_manager.perimeter,),
        daemon=True
    )
    thread.start()

@socketio.on('fly_to_topright')
def handle_fly_to_topright():
    """Handle TopRight flight."""
    thread = threading.Thread(
        target=run_async_command,
        args=(drone_manager.fly_to_TopRight,),
        daemon=True
    )
    thread.start()

@socketio.on('fly_to_topleft')
def handle_fly_to_topleft():
    """Handle TopLeft flight."""
    thread = threading.Thread(
        target=run_async_command,
        args=(drone_manager.fly_to_TopLeft,),
        daemon=True
    )
    thread.start()

@socketio.on('fly_to_bottomleft')
def handle_fly_to_bottomleft():
    """Handle BottomLeft flight."""
    thread = threading.Thread(
        target=run_async_command,
        args=(drone_manager.fly_to_BottomLeft,),
        daemon=True
    )
    thread.start()

# Socket Events - Manual Movement Commands
@socketio.on('move_forward')
def handle_move_forward():
    """Handle forward movement."""
    thread = threading.Thread(
        target=run_async_command,
        args=(drone_manager.move_forward,),
        daemon=True
    )
    thread.start()

@socketio.on('move_back')
def handle_move_back():
    """Handle backward movement."""
    thread = threading.Thread(
        target=run_async_command,
        args=(drone_manager.move_back,),
        daemon=True
    )
    thread.start()

@socketio.on('move_left')
def handle_move_left():
    """Handle left movement."""
    thread = threading.Thread(
        target=run_async_command,
        args=(drone_manager.move_left,),
        daemon=True
    )
    thread.start()

@socketio.on('move_right')
def handle_move_right():
    """Handle right movement."""
    thread = threading.Thread(
        target=run_async_command,
        args=(drone_manager.move_right,),
        daemon=True
    )
    thread.start()

@socketio.on('move_up')
def handle_move_up():
    """Handle upward movement."""
    thread = threading.Thread(
        target=run_async_command,
        args=(drone_manager.move_up,),
        daemon=True
    )
    thread.start()

@socketio.on('move_down')
def handle_move_down():
    """Handle downward movement."""
    thread = threading.Thread(
        target=run_async_command,
        args=(drone_manager.move_down,),
        daemon=True
    )
    thread.start()

@socketio.on('rotate_clockwise')
def handle_rotate_clockwise():
    """Handle clockwise rotation."""
    thread = threading.Thread(
        target=run_async_command,
        args=(drone_manager.rotate_clockwise,),
        daemon=True
    )
    thread.start()

@socketio.on('rotate_counter_clockwise')
def handle_rotate_counter_clockwise():
    """Handle counter-clockwise rotation."""
    thread = threading.Thread(
        target=run_async_command,
        args=(drone_manager.rotate_counter_clockwise,),
        daemon=True
    )
    thread.start()

@socketio.on('video_start')
def handle_video_start():
    """Handle video stream start."""
    try:
        if not drone_manager.is_connected:
            emit('message', {'data': 'Cannot start video: Drone not connected', 'type': 'error'})
            return

        if drone_manager.video_streamer.start_streaming(drone_manager.drone):
            emit('message', {'data': 'Video streaming started', 'type': 'success'})
            performance_logger.info("Video streaming started")
        else:
            emit('message', {'data': 'Failed to start video stream', 'type': 'error'})
    except Exception as e:
        logger.error(f"Video start error: {e}")
        emit('message', {'data': f'Video start error: {str(e)}', 'type': 'error'})

@socketio.on('video_stop')
def handle_video_stop():
    """Handle video stream stop."""
    try:
        drone_manager.video_streamer.stop_streaming()
        emit('message', {'data': 'Video streaming stopped', 'type': 'info'})
        performance_logger.info("Video streaming stopped")
    except Exception as e:
        logger.error(f"Video stop error: {e}")
        emit('message', {'data': f'Video stop error: {str(e)}', 'type': 'error'})

@socketio.on('check_connection')
def handle_check_connection():
    """Handle connection status check."""
    try:
        status = {
            'connected': drone_manager.is_connected,
            'battery': drone_manager.battery_level,
            'flying': drone_manager.is_flying,
            'streaming': drone_manager.video_streamer.is_streaming(),
            'timestamp': time.strftime('%H:%M:%S')
        }
        emit('connection_status', status)
    except Exception as e:
        logger.error(f"Connection check error: {e}")
        emit('connection_status', {'connected': False, 'error': str(e)})

def cleanup_handler(signum, frame):
    """Enhanced cleanup on shutdown."""
    print(f"\n{Fore.YELLOW}{'='*50}")
    print("Initiating System Shutdown...")
    print(f"{'='*50}{Style.RESET_ALL}")
    
    try:
        if drone_manager.patrol:
            drone_manager.patrol.cleanup()
            print(f"{Fore.GREEN}✓ Patrol system cleaned up{Style.RESET_ALL}")
            
        if drone_manager.is_connected:
            if drone_manager.is_flying:
                asyncio.run(drone_manager.land())
                print(f"{Fore.GREEN}✓ Emergency landing completed{Style.RESET_ALL}")
                
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
            
            # Attempt immediate drone connection
            print(f"\n{Fore.YELLOW}Starting drone connection sequence...")
            print("1. Validating WiFi connection...")
            print("2. Testing drone response...")
            print("3. Configuring settings...")
            print(f"{'='*30}{Style.RESET_ALL}")
            
            try:
                if not drone_manager._validate_wifi_connection():
                    print(f"\n{Fore.RED}{'='*50}")
                    print("WIFI CONNECTION FAILED")
                    print("Please ensure you are connected to:")
                    print("• Network name: TELLO-XXXXX")
                    print("• Drone IP is reachable (192.168.10.1)")
                    print(f"{'='*50}{Style.RESET_ALL}")
                    sys.exit(1)
                    
                print(f"{Fore.GREEN}✓ WiFi connection verified{Style.RESET_ALL}")
                
                if drone_manager.connect_drone():
                    battery = drone_manager.battery_level
                    
                    # Get additional drone info
                    try:
                        temp = drone_manager.drone.get_temperature()
                        height = drone_manager.drone.get_height()
                        sdk = drone_manager.drone.get_sdk_version()
                        
                        success_msg = f"""
{Fore.GREEN}✓ DRONE CONNECTED SUCCESSFULLY
{'='*50}
- Status: Online
- Battery: {battery}%
- Temperature: {temp}°C
- Height: {height}cm
- SDK Version: {sdk}
- Time: {time.strftime('%H:%M:%S')}
{'='*50}{Style.RESET_ALL}
"""
                    except:
                        success_msg = f"""
{Fore.GREEN}✓ DRONE CONNECTED SUCCESSFULLY
{'='*50}
- Status: Online
- Battery: {battery}%
- Time: {time.strftime('%H:%M:%S')}
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