#!/usr/bin/env python3
"""
Watchdog monitor for the security camera system
Monitors the main process and sends alerts if it fails
"""

import time
import subprocess
import requests
import logging
import sys
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SecurityCameraWatchdog:
    def __init__(self, service_url="http://localhost:5000", check_interval=60):
        self.service_url = service_url
        self.check_interval = check_interval
        self.consecutive_failures = 0
        self.max_failures = 3
        self.last_notification = 0
        self.notification_interval = 600  # 10 minutes between notifications

        # Load Pushover config if available
        self.pushover_enabled = False
        try:
            from pushover_config import PUSHOVER_CONFIG
            if PUSHOVER_CONFIG["enabled"]:
                self.pushover_user_key = PUSHOVER_CONFIG["user_key"]
                self.pushover_api_token = PUSHOVER_CONFIG["api_token"]
                self.pushover_enabled = True
                logger.info("Pushover notifications enabled for watchdog")
        except ImportError:
            logger.warning("No Pushover configuration found for watchdog")

    def send_alert(self, message, title="Camera Watchdog Alert"):
        """Send alert notification"""
        if not self.pushover_enabled:
            logger.warning(f"Alert: {message}")
            return

        current_time = time.time()
        if current_time - self.last_notification < self.notification_interval:
            return

        try:
            data = {
                'token': self.pushover_api_token,
                'user': self.pushover_user_key,
                'message': message,
                'title': title,
                'priority': 2,  # High priority
                'sound': 'siren'
            }

            response = requests.post(
                "https://api.pushover.net/1/messages.json",
                data=data,
                timeout=10
            )

            if response.status_code == 200:
                self.last_notification = current_time
                logger.info("Watchdog alert sent successfully")
            else:
                logger.error(f"Failed to send watchdog alert: {response.status_code}")

        except Exception as e:
            logger.error(f"Error sending watchdog alert: {e}")

    def check_service_health(self):
        """Check if the camera service is responding"""
        try:
            response = requests.get(f"{self.service_url}/status", timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'running':
                    self.consecutive_failures = 0
                    return True
                else:
                    logger.warning("Service reports not running")
                    return False
            else:
                logger.warning(f"Service returned status code: {response.status_code}")
                return False

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to connect to camera service: {e}")
            return False

    def restart_service(self):
        """Attempt to restart the camera service"""
        try:
            logger.info("Attempting to restart security camera service...")

            # Try systemctl first
            result = subprocess.run(
                ["sudo", "systemctl", "restart", "security-camera"],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                logger.info("Service restart command completed")
                time.sleep(10)  # Wait for service to start

                # Check if restart was successful
                if self.check_service_health():
                    message = f"Security camera service automatically restarted at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    self.send_alert(message, "Service Restart")
                    return True
                else:
                    logger.error("Service restart failed - service still not responding")
                    return False
            else:
                logger.error(f"Failed to restart service: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"Error attempting service restart: {e}")
            return False

    def run(self):
        """Main watchdog loop"""
        logger.info("Security camera watchdog started")

        while True:
            try:
                if self.check_service_health():
                    logger.info("Service health check passed")
                else:
                    self.consecutive_failures += 1
                    logger.warning(f"Service health check failed ({self.consecutive_failures}/{self.max_failures})")

                    if self.consecutive_failures >= self.max_failures:
                        message = f"Security camera service failed {self.consecutive_failures} consecutive health checks. Attempting restart..."
                        self.send_alert(message, "Service Failure")

                        if self.restart_service():
                            self.consecutive_failures = 0
                        else:
                            message = f"Failed to restart security camera service after {self.consecutive_failures} failures. Manual intervention required."
                            self.send_alert(message, "Critical Failure")

                time.sleep(self.check_interval)

            except KeyboardInterrupt:
                logger.info("Watchdog stopped by user")
                break
            except Exception as e:
                logger.error(f"Unexpected error in watchdog: {e}")
                time.sleep(self.check_interval)

def main():
    """Main function"""
    if len(sys.argv) > 1:
        check_interval = int(sys.argv[1])
    else:
        check_interval = 60  # Default 1 minute

    watchdog = SecurityCameraWatchdog(check_interval=check_interval)
    watchdog.run()

if __name__ == "__main__":
    main()