from djitellopy import Tello
import threading
import time
import logging
from flask import jsonify

logger = logging.getLogger(__name__)

class DroneManager:
    def __init__(self):
        self.drone = None
        self.drone_connected = False
        self.keep_alive_thread = None

    def connect_drone(self):
        """Connect to the drone with improved initialization."""
        try:
            logger.info("Attempting to connect to drone...")
            self.drone = Tello()
            self.drone.connect()
            
            if self.drone.get_battery() > 0:
                # Initialize drone settings
                self.drone.streamon()
                self.drone.set_speed(50)  # Set default speed to 50%
                
                # Set initial RC values to zero
                self.drone.send_rc_control(0, 0, 0, 0)
                time.sleep(0.5)  # Give time for commands to register
                
                self.drone_connected = True
                logger.info(f"Successfully connected to drone. Battery: {self.drone.get_battery()}%")
                return True
            else:
                logger.error("Failed to verify drone connection")
                return False
        except Exception as e:
            logger.error(f"Drone connection failed: {str(e)}")
            self.drone_connected = False
            return False

    def send_keep_alive(self):
        """Keep-alive function to maintain drone connection."""
        while True:
            if self.drone_connected and self.drone:
                try:
                    battery = self.drone.get_battery()
                    logger.debug(f"Keep-alive battery check: {battery}%")
                    time.sleep(5)  # Check every 5 seconds
                except Exception as e:
                    logger.error(f"Keep-alive error: {str(e)}")
                    self.drone_connected = False
                    # Attempt to reconnect
                    self.connect_drone()
            else:
                time.sleep(5)  # Wait before retry if disconnected

    def start_keep_alive(self):
        """Start the keep-alive thread."""
        self.keep_alive_thread = threading.Thread(
            target=self.send_keep_alive,
            daemon=True
        )
        self.keep_alive_thread.start()

    def get_status(self):
        """Get current drone status."""
        if not self.drone_connected:
            return jsonify({"error": "Drone not connected"}), 400

        try:
            battery = self.drone.get_battery()
            height = self.drone.get_height()
            temperature = self.drone.get_temperature()
            flight_time = self.drone.get_flight_time()
            wifi_strength = self.drone.query_wifi_signal_noise_ratio()

            return jsonify({
                "battery": f"{battery}%",
                "height": f"{height}cm",
                "temperature": f"{temperature}°C",
                "flight_time": f"{flight_time}s",
                "wifi_strength": f"{wifi_strength}",
                "is_flying": self.drone.is_flying
            })
        except Exception as e:
            logger.error(f"Error getting drone status: {str(e)}")
            return jsonify({"error": str(e)}), 500

    def get_drone(self):
        """Get the drone instance."""
        return self.drone

    def is_connected(self):
        """Check if drone is connected."""
        return self.drone_connected