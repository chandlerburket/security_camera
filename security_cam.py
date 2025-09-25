#!/usr/bin/env python3
"""
Raspberry Pi Camera Web Server using picamera2
Streams live camera footage to a web interface
"""

import io
import time
import threading
import sys
import logging
import subprocess
import socket
import re

# Try importing required packages and provide helpful error messages
try:
    from flask import Flask, render_template_string, Response
except ImportError:
    print("❌ Flask not found. Install with: sudo apt install python3-flask")
    sys.exit(1)

try:
    from picamera2 import Picamera2
except ImportError:
    print("❌ picamera2 not found. Install with: sudo apt install python3-picamera2")
    sys.exit(1)

try:
    from PIL import Image
except ImportError:
    print("❌ PIL not found. Install with: sudo apt install python3-pil")
    sys.exit(1)

try:
    import cv2
    import numpy as np
except ImportError:
    print("❌ OpenCV not found. Install with: sudo apt install python3-opencv-python")
    sys.exit(1)

try:
    import requests
    from requests.auth import HTTPBasicAuth
except ImportError:
    print("❌ requests not found. Install with: pip install requests")
    sys.exit(1)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CameraStreamer:
    def __init__(self):
        self.picam2 = None
        self.output_buffer = io.BytesIO()
        self.condition = threading.Condition()
        self.frame = None
        self.running = False

        # Motion detection variables
        self.motion_detected = False
        self.background_subtractor = None
        self.previous_frame = None
        self.motion_threshold = 5000  # Minimum area for motion detection
        self.last_motion_time = 0
        self.last_save_time = 0  # Track when last image was saved

        # OwnCloud configuration - update these with your server details
        self.owncloud_enabled = False  # Set to True to enable uploads
        self.owncloud_url = "http://192.168.1.100"  # Your OwnCloud server IP
        self.owncloud_username = "camera_user"  # Your OwnCloud username
        self.owncloud_password = "your_password"  # Your OwnCloud password
        self.owncloud_folder = "/motion_captures"  # Folder to save images
        self.save_interval = 5  # Minimum seconds between saves

        # Pushover configuration - update these with your Pushover credentials
        self.pushover_enabled = False  # Set to True to enable notifications
        self.pushover_user_key = "your_pushover_user_key"  # Your Pushover user key
        self.pushover_api_token = "your_pushover_api_token"  # Your Pushover application token
        self.pushover_notify_interval = 60  # Minimum seconds between notifications
        self.last_pushover_time = 0  # Track when last notification was sent

    def configure_owncloud(self, url, username, password, folder="/motion_captures", enabled=True):
        """Configure OwnCloud settings for image uploads"""
        self.owncloud_url = url.rstrip('/')  # Remove trailing slash
        self.owncloud_username = username
        self.owncloud_password = password
        self.owncloud_folder = folder if folder.startswith('/') else f'/{folder}'
        self.owncloud_enabled = enabled

        logger.info(f"🔧 OwnCloud configured: {url}{folder} (enabled: {enabled})")

    def configure_pushover(self, user_key, api_token, enabled=True, notify_interval=60):
        """Configure Pushover settings for motion notifications"""
        self.pushover_user_key = user_key
        self.pushover_api_token = api_token
        self.pushover_enabled = enabled
        self.pushover_notify_interval = notify_interval

        logger.info(f"🔔 Pushover configured (enabled: {enabled}, interval: {notify_interval}s)")

    def initialize_camera(self):
        """Initialize the camera with optimal settings for streaming"""
        try:
            self.picam2 = Picamera2()
            
            # Simplified configuration with higher resolution for larger display
            config = self.picam2.create_video_configuration(
                main={"size": (640, 480)}  # Increased resolution for larger display
            )
            
            self.picam2.configure(config)
            self.picam2.start()
            
            # Allow camera to warm up
            time.sleep(2)
            
            logger.info("Camera initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize camera: {e}")
            return False

    def detect_motion(self, frame_bytes):
        """Detect motion in the current frame using OpenCV"""
        try:
            # Convert JPEG bytes to OpenCV image
            nparr = np.frombuffer(frame_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            # Convert to grayscale for motion detection
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (21, 21), 0)

            # Initialize background frame if this is the first frame
            if self.previous_frame is None:
                self.previous_frame = gray
                return False

            # Compute the absolute difference between current and previous frame
            frame_delta = cv2.absdiff(self.previous_frame, gray)

            # Apply threshold to get binary image
            thresh = cv2.threshold(frame_delta, 25, 255, cv2.THRESH_BINARY)[1]

            # Dilate the thresholded image to fill in holes
            thresh = cv2.dilate(thresh, None, iterations=2)

            # Find contours
            contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            # Check if any contour is large enough to be considered motion
            motion_detected = False
            for contour in contours:
                if cv2.contourArea(contour) > self.motion_threshold:
                    motion_detected = True
                    self.last_motion_time = time.time()
                    break

            # Update previous frame
            self.previous_frame = gray

            # Update motion status
            self.motion_detected = motion_detected or (time.time() - self.last_motion_time < 3.0)

            return self.motion_detected

        except Exception as e:
            logger.error(f"Error in motion detection: {e}")
            return False

    def capture_frames(self):
        """Continuously capture frames from camera"""
        self.running = True
        
        while self.running:
            try:
                # Capture directly to JPEG bytes using main stream
                buffer = io.BytesIO()
                self.picam2.capture_file(buffer, format='jpeg')
                frame_bytes = buffer.getvalue()

                # Perform motion detection on the frame
                motion_detected = self.detect_motion(frame_bytes)

                # Save image if motion is detected
                if motion_detected:
                    self.save_motion_image(frame_bytes)

                # Update shared frame data
                with self.condition:
                    self.frame = frame_bytes
                    self.condition.notify_all()
                    
                # Small delay to prevent overwhelming the system
                time.sleep(0.033)  # ~30 FPS
                
            except Exception as e:
                logger.error(f"Error capturing frame: {e}")
                time.sleep(1)
    
    def get_frame(self):
        """Get the latest frame for streaming"""
        with self.condition:
            self.condition.wait()
            return self.frame

    def get_motion_status(self):
        """Get current motion detection status"""
        return {
            'motion_detected': self.motion_detected,
            'last_motion_time': self.last_motion_time
        }

    def upload_to_owncloud(self, image_data, filename):
        """Upload image data to OwnCloud server via WebDAV"""
        if not self.owncloud_enabled:
            return False

        try:
            # Construct the full WebDAV URL
            webdav_url = f"{self.owncloud_url}/remote.php/webdav{self.owncloud_folder}/{filename}"

            # Prepare authentication
            auth = HTTPBasicAuth(self.owncloud_username, self.owncloud_password)

            # Set headers for WebDAV upload
            headers = {
                'Content-Type': 'image/jpeg',
            }

            # Upload the file using PUT method
            response = requests.put(
                webdav_url,
                data=image_data,
                auth=auth,
                headers=headers,
                timeout=10
            )

            if response.status_code in [200, 201, 204]:
                logger.info(f"✅ Successfully uploaded {filename} to OwnCloud")
                return True
            else:
                logger.error(f"❌ Failed to upload {filename}. Status: {response.status_code}, Response: {response.text}")
                return False

        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Network error uploading to OwnCloud: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Unexpected error uploading to OwnCloud: {e}")
            return False

    def send_pushover_notification(self, message, title="Motion Detected"):
        """Send a notification via Pushover API"""
        if not self.pushover_enabled:
            return False

        current_time = time.time()

        # Check if enough time has passed since last notification
        if current_time - self.last_pushover_time < self.pushover_notify_interval:
            return False

        try:
            # Pushover API endpoint
            pushover_url = "https://api.pushover.net/1/messages.json"

            # Prepare the notification data
            data = {
                'token': self.pushover_api_token,
                'user': self.pushover_user_key,
                'message': message,
                'title': title,
                'priority': 0,  # Normal priority
                'sound': 'pushover'  # Default sound
            }

            # Send the notification
            response = requests.post(
                pushover_url,
                data=data,
                timeout=10
            )

            if response.status_code == 200:
                response_json = response.json()
                if response_json.get('status') == 1:
                    self.last_pushover_time = current_time
                    logger.info(f"🔔 Pushover notification sent successfully")
                    return True
                else:
                    logger.error(f"❌ Pushover API error: {response_json.get('errors', 'Unknown error')}")
                    return False
            else:
                logger.error(f"❌ Failed to send Pushover notification. Status: {response.status_code}")
                return False

        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Network error sending Pushover notification: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Unexpected error sending Pushover notification: {e}")
            return False

    def save_motion_image(self, frame_bytes):
        """Save image when motion is detected"""
        current_time = time.time()

        # Check if enough time has passed since last save
        if current_time - self.last_save_time < self.save_interval:
            return False

        try:
            # Generate filename with timestamp
            timestamp = time.strftime("%Y%m%d_%H%M%S", time.localtime(current_time))
            filename = f"motion_{timestamp}.jpg"

            # Send Pushover notification
            notification_message = f"Motion detected at {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(current_time))}"
            self.send_pushover_notification(notification_message)

            # Upload to OwnCloud if enabled
            if self.owncloud_enabled:
                success = self.upload_to_owncloud(frame_bytes, filename)
                if success:
                    self.last_save_time = current_time
                    logger.info(f"📸 Motion detected - image saved: {filename}")
                    return True
                else:
                    logger.error(f"❌ Failed to save motion image: {filename}")
                    return False
            else:
                logger.info("📸 Motion detected but OwnCloud upload is disabled")
                self.last_save_time = current_time  # Still update save time for notification throttling
                return True

        except Exception as e:
            logger.error(f"❌ Error saving motion image: {e}")
            return False

    def stop(self):
        """Stop the camera and cleanup resources"""
        self.running = False
        if self.picam2:
            self.picam2.stop()
            self.picam2.close()
        logger.info("Camera stopped")

# Initialize Flask app and camera streamer
app = Flask(__name__)
streamer = CameraStreamer()

# HTML template for the web interface
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Raspberry Pi Camera Stream</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {
            font-family: Arial, sans-serif;
            color: slategray; 
            margin: 0;
            background-color: #000000;
            text-align: center;
        }
        .wifi-bars {
            display: inline-flex;
            align-items: flex-end;
            margin-right: 8px;
            height: 16px;
        }
        .wifi-bar {
            width: 3px;
            margin-right: 2px;
            background-color: #ddd;
            border-radius: 1px;
            transition: background-color 0.3s ease;
        }
        .wifi-bar:nth-child(1) { height: 4px; }
        .wifi-bar:nth-child(2) { height: 8px; }
        .wifi-bar:nth-child(3) { height: 12px; }
        .wifi-bar:nth-child(4) { height: 16px; }
        .wifi-excellent { 
            border-color: #28a745; 
            color: #28a745;
            background: rgba(40, 167, 69, 0.1);
        }
        .wifi-good { 
            border-color: #17a2b8; 
            color: #17a2b8;
            background: rgba(23, 162, 184, 0.1);
        }
        .wifi-fair { 
            border-color: #ffc107; 
            color: #e67e00;
            background: rgba(255, 193, 7, 0.1);
        }
        .wifi-weak { 
            border-color: #fd7e14; 
            color: #fd7e14;
            background: rgba(253, 126, 20, 0.1);
        }
        .wifi-poor { 
            border-color: #dc3545; 
            color: #dc3545;
            background: rgba(220, 53, 69, 0.1);
        }
        .wifi-unknown { 
            border-color: #6c757d; 
            color: #6c757d;
            background: rgba(108, 117, 125, 0.1);
        }
        .container {
            position: relative;
            max-width: 1200px;
            margin: 0 auto;
            background-color: black;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: #ffffff;
            margin-bottom: 20px;
        }
        .camera-stream {
            border: 2px solid #ddd;
            border-radius: 5px;
            width: 100%;
            max-width: 1000px;
            height: auto;
            display: block;
            margin: 0 auto;
        }
        .video-container {
            position: relative;
            margin: 20px 0;
            text-align: center;
        }
        .video-section {
            margin-bottom: 20px;
        }
        .info {
            margin-top: 20px;
            padding: 15px;
            background-color: #000000;
            border-radius: 5px;
            color: #slategray;
            text-align: left;
        }
        .info p {
            margin: 8px 0;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .signal-excellent { color: #28a745; font-weight: bold; }
        .signal-good { color: #17a2b8; font-weight: bold; }
        .signal-fair { color: #ffc107; font-weight: bold; }
        .signal-weak { color: #fd7e14; font-weight: bold; }
        .signal-poor { color: #dc3545; font-weight: bold; }
        .status-running { color: #28a745; font-weight: bold; }
        .status-stopped { color: #dc3545; font-weight: bold; }
        .controls {
            margin-top: 15px;
        }
        button {
            padding: 10px 20px;
            margin: 5px;
            background-color: #007bff;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
        }
        button:hover {
            background-color: #0056b3;
        }
    </style>
</head>
<body>
    <div class="container">
        
        
        <div class="video-section">
            <div class="video-container" style="position: relative;">
                <img src="{{ url_for('video_feed') }}" class="camera-stream" alt="Camera Stream">
                <div id="datetime-overlay" style="position: absolute; bottom: 10px; right: 10px; background: rgba(0, 0, 0, 0.7); color: white; padding: 4px 8px; border-radius: 4px; font-size: 12px; font-family: monospace;"></div>
            </div>
        </div>

        <div class="info">
            <p style="display: flex; justify-content: space-between; align-items: center;"><strong>Camera Status:</strong> <span id="camera-status" style="width: 12px; height: 12px; border-radius: 50%; background-color: #4CAF50; display: inline-block;"></span></p>
            <p style="display: flex; justify-content: space-between; align-items: center;"><strong>WiFi Signal:</strong> <span style="display: flex; align-items: center; gap: 8px;"><span class="wifi-bars" id="wifi-bars" style="display: inline-flex; align-items: baseline;"><span class="wifi-bar"></span><span class="wifi-bar"></span><span class="wifi-bar"></span><span class="wifi-bar"></span></span><span id="wifi-signal">Loading...</span></span></p>
            <p><strong>CPU Temperature:</strong> <span id="cpu-temp">Loading...</span></p>
            <p><strong>Uptime:</strong> <span id="uptime">Loading...</span></p>
        </div>
        
        <script>
            // Function to update system status
            function updateStatus() {
                console.log('Updating status...');
                fetch('/status')
                    .then(response => {
                        console.log('Status response received:', response.status);
                        if (!response.ok) {
                            throw new Error(`HTTP error! status: ${response.status}`);
                        }
                        return response.json();
                    })
                    .then(data => {
                        console.log('Status data received:', data);
                        
                        // Update camera status indicator
                        const cameraStatusEl = document.getElementById('camera-status');
                        if (cameraStatusEl) {
                            if (data.status === 'running') {
                                cameraStatusEl.style.backgroundColor = '#4CAF50'; // Green for running
                            } else {
                                cameraStatusEl.style.backgroundColor = '#f44336'; // Red for stopped
                            }
                        }

                        
                        // Update WiFi bars in info section
                        const wifiBars = document.querySelectorAll('#wifi-bars .wifi-bar');
                        const wifiBarsContainer = document.getElementById('wifi-bars');
                        
                        let barsToFill = 0;
                        let qualityClass = 'wifi-unknown';
                        
                        if (data.wifi_signal_dbm !== null) {
                            const quality = data.wifi_signal_quality.toLowerCase();
                            
                            // Determine number of bars to fill
                            switch(quality) {
                                case 'excellent':
                                    qualityClass = 'wifi-excellent';
                                    barsToFill = 4;
                                    break;
                                case 'good':
                                    qualityClass = 'wifi-good';
                                    barsToFill = 3;
                                    break;
                                case 'fair':
                                    qualityClass = 'wifi-fair';
                                    barsToFill = 2;
                                    break;
                                case 'weak':
                                    qualityClass = 'wifi-weak';
                                    barsToFill = 1;
                                    break;
                                case 'poor':
                                    qualityClass = 'wifi-poor';
                                    barsToFill = 1;
                                    break;
                                default:
                                    qualityClass = 'wifi-unknown';
                                    barsToFill = 0;
                            }
                        }
                        
                        // Apply quality class to bars container
                        wifiBarsContainer.className = `wifi-bars ${qualityClass}`;
                        
                        // Update signal bars
                        wifiBars.forEach((bar, index) => {
                            if (index < barsToFill) {
                                // Get color from the container's computed style
                                const containerStyle = getComputedStyle(wifiBarsContainer);
                                const color = containerStyle.color;
                                bar.style.backgroundColor = color;
                            } else {
                                // Leave unfilled bars gray
                                bar.style.backgroundColor = '#ddd';
                            }
                        });
                        
                        // Update WiFi info in details section
                        const wifiSsidEl = document.getElementById('wifi-ssid');
                        if (wifiSsidEl) {
                            wifiSsidEl.textContent = data.wifi_ssid || 'Unknown';
                        }
                        
                        const signalEl = document.getElementById('wifi-signal');
                        if (signalEl) {
                            let signalText = 'Unknown';
                            let signalClass = '';
                            
                            if (data.wifi_signal_dbm !== null) {
                                signalText = `${data.wifi_signal_quality} (${data.wifi_signal_dbm} dBm, ${data.wifi_signal_percent}%)`;
                                signalClass = `signal-${data.wifi_signal_quality.toLowerCase()}`;
                            }
                            
                            signalEl.textContent = signalText;
                            signalEl.className = signalClass;
                        }
                        
                        // Update system info
                        const ipEl = document.getElementById('ip-address');
                        if (ipEl) {
                            ipEl.textContent = data.ip_address || 'Unknown';
                        }
                        
                        const tempEl = document.getElementById('cpu-temp');
                        if (tempEl) {
                            tempEl.textContent = data.cpu_temp || 'Unknown';
                        }
                        
                        const uptimeEl = document.getElementById('uptime');
                        if (uptimeEl) {
                            uptimeEl.textContent = data.uptime || 'Unknown';
                        }
                        
                        console.log('Status updated successfully');
                    })
                    .catch(error => {
                        console.error('Error fetching status:', error);
                        // Show error in the status elements
                        const elements = ['camera-status', 'wifi-ssid', 'wifi-signal', 'ip-address', 'cpu-temp', 'uptime'];
                        elements.forEach(id => {
                            const el = document.getElementById(id);
                            if (el && el.textContent === 'Loading...') {
                                el.textContent = 'Error loading';
                            }
                        });
                    });
            }
            
            // Wait for page to load before updating status
            document.addEventListener('DOMContentLoaded', function() {
                console.log('Page loaded, starting status updates');
                // Update status immediately and then every 10 seconds
                updateStatus();
                setInterval(updateStatus, 10000);
            });
            
            // Function to update date and time overlay
            function updateDateTime() {
                const now = new Date();
                const year = now.getFullYear();
                const month = String(now.getMonth() + 1).padStart(2, '0');
                const day = String(now.getDate()).padStart(2, '0');

                // Convert to 12-hour format
                let hours = now.getHours();
                const ampm = hours >= 12 ? 'PM' : 'AM';
                hours = hours % 12;
                hours = hours ? hours : 12; // the hour '0' should be '12'
                const hoursFormatted = String(hours).padStart(2, '0');

                const minutes = String(now.getMinutes()).padStart(2, '0');
                const seconds = String(now.getSeconds()).padStart(2, '0');

                const dateTimeString = `${year}-${month}-${day} ${hoursFormatted}:${minutes}:${seconds} ${ampm}`;
                const overlay = document.getElementById('datetime-overlay');
                if (overlay) {
                    overlay.textContent = dateTimeString;
                }
            }

            // Update datetime immediately and then every second
            updateDateTime();
            setInterval(updateDateTime, 1000);

            // Auto-refresh the page every 5 minutes to prevent connection issues
            setTimeout(function() {
                location.reload();
            }, 300000);
        </script>
    </div>
</body>
</html>
"""

def generate_frames():
    """Generator function for video streaming"""
    while True:
        try:
            frame = streamer.get_frame()
            if frame:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        except Exception as e:
            logger.error(f"Error generating frame: {e}")
            break

@app.route('/')
def index():
    """Main page with camera stream"""
    return render_template_string(HTML_TEMPLATE)

@app.route('/video_feed')
def video_feed():
    """Video streaming route"""
    return Response(
        generate_frames(),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )

def get_system_info():
    """Get system information including WiFi signal strength"""
    info = {}
    
    try:
        # Get WiFi signal strength
        result = subprocess.run(['iwconfig'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            # Parse iwconfig output for signal strength
            lines = result.stdout
            signal_match = re.search(r'Signal level=(-?\d+) dBm', lines)
            if signal_match:
                signal_dbm = int(signal_match.group(1))
                info['wifi_signal_dbm'] = signal_dbm
                
                # Convert dBm to percentage (rough approximation)
                if signal_dbm >= -30:
                    info['wifi_signal_percent'] = 100
                elif signal_dbm >= -67:
                    info['wifi_signal_percent'] = 70
                elif signal_dbm >= -70:
                    info['wifi_signal_percent'] = 50
                elif signal_dbm >= -80:
                    info['wifi_signal_percent'] = 30
                else:
                    info['wifi_signal_percent'] = 10
                    
                info['wifi_signal_quality'] = 'Excellent' if signal_dbm >= -30 else \
                                            'Good' if signal_dbm >= -67 else \
                                            'Fair' if signal_dbm >= -70 else \
                                            'Weak' if signal_dbm >= -80 else 'Poor'
            else:
                info['wifi_signal_dbm'] = None
                info['wifi_signal_percent'] = None
                info['wifi_signal_quality'] = 'Unknown'
                
            # Get WiFi network name (SSID)
            ssid_match = re.search(r'ESSID:"([^"]*)"', lines)
            if ssid_match:
                info['wifi_ssid'] = ssid_match.group(1)
            else:
                info['wifi_ssid'] = 'Not connected'
        else:
            info['wifi_signal_dbm'] = None
            info['wifi_signal_percent'] = None
            info['wifi_signal_quality'] = 'No WiFi'
            info['wifi_ssid'] = 'No WiFi'
    except Exception as e:
        logger.warning(f"Could not get WiFi info: {e}")
        info['wifi_signal_dbm'] = None
        info['wifi_signal_percent'] = None
        info['wifi_signal_quality'] = 'Error'
        info['wifi_ssid'] = 'Error'
    
    try:
        # Get IP address
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        info['ip_address'] = s.getsockname()[0]
        s.close()
    except Exception:
        info['ip_address'] = 'Unknown'
    
    try:
        # Get CPU temperature
        with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
            temp = int(f.read().strip()) / 1000.0
            info['cpu_temp'] = f"{temp:.1f}°C"
    except Exception:
        info['cpu_temp'] = 'Unknown'
    
    try:
        # Get uptime
        with open('/proc/uptime', 'r') as f:
            uptime_seconds = float(f.read().split()[0])
            hours = int(uptime_seconds // 3600)
            minutes = int((uptime_seconds % 3600) // 60)
            info['uptime'] = f"{hours}h {minutes}m"
    except Exception:
        info['uptime'] = 'Unknown'
    
    return info

@app.route('/test-status')
def test_status():
    """Test endpoint to debug status information"""
    try:
        system_info = get_system_info()
        return f"""
        <h2>Status Debug Information</h2>
        <pre>
System Info: {system_info}

Camera Status: {'running' if streamer.running else 'stopped'}
Camera Initialized: {streamer.picam2 is not None}
        </pre>
        <a href="/">Back to main page</a>
        """
    except Exception as e:
        return f"Error getting status: {str(e)}"

@app.route('/status')
def status():
    """API endpoint for camera and system status"""
    system_info = get_system_info()
    motion_status = streamer.get_motion_status()
    return {
        'status': 'running' if streamer.running else 'stopped',
        'camera_initialized': streamer.picam2 is not None,
        'motion_detected': motion_status['motion_detected'],
        'last_motion_time': motion_status['last_motion_time'],
        'owncloud_enabled': streamer.owncloud_enabled,
        'pushover_enabled': streamer.pushover_enabled,
        'wifi_signal_dbm': system_info['wifi_signal_dbm'],
        'wifi_signal_percent': system_info['wifi_signal_percent'],
        'wifi_signal_quality': system_info['wifi_signal_quality'],
        'wifi_ssid': system_info['wifi_ssid'],
        'ip_address': system_info['ip_address'],
        'cpu_temp': system_info['cpu_temp'],
        'uptime': system_info['uptime']
    }

@app.route('/test-owncloud')
def test_owncloud():
    """Test OwnCloud connection"""
    if not streamer.owncloud_enabled:
        return {"status": "error", "message": "OwnCloud is not enabled"}

    try:
        # Test connection by trying to create a test file
        test_filename = f"test_connection_{int(time.time())}.txt"
        test_data = b"OwnCloud connection test from security camera"

        webdav_url = f"{streamer.owncloud_url}/remote.php/webdav{streamer.owncloud_folder}/{test_filename}"
        auth = HTTPBasicAuth(streamer.owncloud_username, streamer.owncloud_password)

        response = requests.put(
            webdav_url,
            data=test_data,
            auth=auth,
            headers={'Content-Type': 'text/plain'},
            timeout=10
        )

        if response.status_code in [200, 201, 204]:
            # Delete the test file
            requests.delete(webdav_url, auth=auth, timeout=5)
            return {"status": "success", "message": "OwnCloud connection successful"}
        else:
            return {
                "status": "error",
                "message": f"Connection failed. Status: {response.status_code}",
                "details": response.text
            }

    except Exception as e:
        return {"status": "error", "message": f"Connection error: {str(e)}"}

@app.route('/test-pushover')
def test_pushover():
    """Test Pushover notification"""
    if not streamer.pushover_enabled:
        return {"status": "error", "message": "Pushover is not enabled"}

    try:
        # Send a test notification
        test_message = f"Test notification from security camera at {time.strftime('%Y-%m-%d %H:%M:%S')}"
        success = streamer.send_pushover_notification(test_message, "Test Notification")

        if success:
            return {"status": "success", "message": "Pushover test notification sent successfully"}
        else:
            return {"status": "error", "message": "Failed to send test notification"}

    except Exception as e:
        return {"status": "error", "message": f"Test error: {str(e)}"}

def main():
    """Main function to start the camera server"""
    print("🎥 Starting Raspberry Pi Camera Web Server...")

    # Try to load OwnCloud configuration
    try:
        from owncloud_config import OWNCLOUD_CONFIG
        streamer.configure_owncloud(
            url=OWNCLOUD_CONFIG["url"],
            username=OWNCLOUD_CONFIG["username"],
            password=OWNCLOUD_CONFIG["password"],
            folder=OWNCLOUD_CONFIG["folder"],
            enabled=OWNCLOUD_CONFIG["enabled"]
        )
        streamer.save_interval = OWNCLOUD_CONFIG.get("save_interval", 5)
        print("✅ OwnCloud configuration loaded")
    except ImportError:
        print("⚠️  No OwnCloud configuration found. Copy owncloud_config_example.py to owncloud_config.py and configure it.")
        print("   Motion detection will work, but images won't be saved to OwnCloud.")
    except Exception as e:
        print(f"⚠️  Error loading OwnCloud configuration: {e}")

    # Try to load Pushover configuration
    try:
        from pushover_config import PUSHOVER_CONFIG
        streamer.configure_pushover(
            user_key=PUSHOVER_CONFIG["user_key"],
            api_token=PUSHOVER_CONFIG["api_token"],
            enabled=PUSHOVER_CONFIG["enabled"],
            notify_interval=PUSHOVER_CONFIG.get("notify_interval", 60)
        )
        print("✅ Pushover configuration loaded")
    except ImportError:
        print("⚠️  No Pushover configuration found. Create pushover_config.py to enable notifications.")
        print("   Motion detection will work, but no notifications will be sent.")
    except Exception as e:
        print(f"⚠️  Error loading Pushover configuration: {e}")

    # Initialize camera
    if not streamer.initialize_camera():
        print("❌ Failed to initialize camera. Please check your camera connection.")
        return
    
    # Start camera capture thread
    capture_thread = threading.Thread(target=streamer.capture_frames, daemon=True)
    capture_thread.start()
    
    print("✅ Camera initialized successfully!")
    print("🌐 Starting web server...")
    print("📱 Access your camera stream at:")
    print("   - Local: http://localhost:5000")
    print("   - Network: http://[your-pi-ip]:5000")
    print("\n💡 Tip: Find your Pi's IP with: hostname -I")
    print("🛑 Press Ctrl+C to stop the server\n")
    
    try:
        # Start Flask server
        app.run(
            host='0.0.0.0',  # Allow access from any device on network
            port=5000,
            debug=False,     # Disable debug mode for better performance
            threaded=True    # Enable threading for multiple connections
        )
    except KeyboardInterrupt:
        print("\n🛑 Shutting down server...")
    finally:
        streamer.stop()
        print("✅ Camera server stopped successfully!")

if __name__ == '__main__':
    main()