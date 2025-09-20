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
        
    def initialize_camera(self):
        """Initialize the camera with optimal settings for streaming"""
        try:
            self.picam2 = Picamera2()
            
            # Simplified configuration - just main stream for streaming
            config = self.picam2.create_video_configuration(
                main={"size": (320, 240)}  # Single stream, small size for web streaming
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
    
    def capture_frames(self):
        """Continuously capture frames from camera"""
        self.running = True
        
        while self.running:
            try:
                # Capture directly to JPEG bytes using main stream
                buffer = io.BytesIO()
                self.picam2.capture_file(buffer, format='jpeg')
                
                # Update shared frame data
                with self.condition:
                    self.frame = buffer.getvalue()
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
            margin: 0;
            padding: 20px;
            background-color: #000000;
            text-align: center;
        }
        .wifi-indicator {
            position: absolute;
            top: 10px;
            right: 10px;
            background: rgba(0, 0, 0, 0.9);
            padding: 8px 12px;
            border-radius: 20px;
            font-size: 14px;
            font-weight: bold;
            box-shadow: 0 2px 8px rgba(0,0,0,0.2);
            border: 2px solid #ddd;
            z-index: 100;
        }
        .container {
            position: relative;
            max-width: 800px;
            margin: 0 auto;
            background-color: black;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: #333;
            margin-bottom: 20px;
        }
        .camera-stream {
            border: 2px solid #ddd;
            border-radius: 5px;
            max-width: 100%;
            height: auto;
        }
        .info {
            margin-top: 20px;
            padding: 15px;
            background-color: #e7f3ff;
            border-radius: 5px;
            color: #333;
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
            color: black;
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
        <!-- WiFi Signal Indicator -->
        <div class="wifi-indicator" id="wifi-indicator">
            <span id="wifi-display">Loading...</span>
        </div>
        
        
        <div>
            <img src="{{ url_for('video_feed') }}" class="camera-stream" alt="Camera Stream">
        </div>
        
        <div class="controls">
            <button onclick="location.reload()">Refresh Stream</button>
        </div>
        
        <script>
            // Function to update system status
            function updateStatus() {
                console.log('Updating status...');
                fetch('/status')
                    .then(response => {
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
                        }console.log('Status response received:', response.status);
                        if (!response.ok) {
                            throw new Error(`HTTP error! status: ${response.status}`);
                        }
                        return response.json();
                    })
                    .then(data => {
                        console.log('Status data received:', data);
                        
                        // Update camera status with styling
                        const cameraStatusEl = document.getElementById('camera-status');
                        if (cameraStatusEl) {
                            if (data.status === 'running') {
                                cameraStatusEl.textContent = 'Camera is streaming live';
                                cameraStatusEl.className = 'status-running';
                            } else {
                                cameraStatusEl.textContent = 'Camera stopped';
                                cameraStatusEl.className = 'status-stopped';
                            }
                        }
                        
                        // Update WiFi indicator at the top
                        const wifiDisplayEl = document.getElementById('wifi-display');
                        const wifiIndicatorEl = document.getElementById('wifi-indicator');
                        
                        if (wifiDisplayEl && wifiIndicatorEl) {
                            if (data.wifi_signal_dbm !== null) {
                                wifiDisplayEl.textContent = `${data.wifi_signal_quality} ${data.wifi_signal_percent}%`;
                                
                                // Update indicator border color based on signal quality
                                const quality = data.wifi_signal_quality.toLowerCase();
                                if (quality === 'excellent') {
                                    wifiIndicatorEl.style.borderColor = '#28a745';
                                    wifiIndicatorEl.style.color = '#28a745';
                                } else if (quality === 'good') {
                                    wifiIndicatorEl.style.borderColor = '#17a2b8';
                                    wifiIndicatorEl.style.color = '#17a2b8';
                                } else if (quality === 'fair') {
                                    wifiIndicatorEl.style.borderColor = '#ffc107';
                                    wifiIndicatorEl.style.color = '#e67e00';
                                } else if (quality === 'weak') {
                                    wifiIndicatorEl.style.borderColor = '#fd7e14';
                                    wifiIndicatorEl.style.color = '#fd7e14';
                                } else if (quality === 'poor') {
                                    wifiIndicatorEl.style.borderColor = '#dc3545';
                                    wifiIndicatorEl.style.color = '#dc3545';
                                } else {
                                    wifiIndicatorEl.style.borderColor = '#6c757d';
                                    wifiIndicatorEl.style.color = '#6c757d';
                                }
                            } else {
                                wifiDisplayEl.textContent = 'No WiFi';
                                wifiIndicatorEl.style.borderColor = '#6c757d';
                                wifiIndicatorEl.style.color = '#6c757d';
                            }
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
    return {
        'status': 'running' if streamer.running else 'stopped',
        'camera_initialized': streamer.picam2 is not None,
        'wifi_signal_dbm': system_info['wifi_signal_dbm'],
        'wifi_signal_percent': system_info['wifi_signal_percent'],
        'wifi_signal_quality': system_info['wifi_signal_quality'],
        'wifi_ssid': system_info['wifi_ssid'],
        'ip_address': system_info['ip_address'],
        'cpu_temp': system_info['cpu_temp'],
        'uptime': system_info['uptime']
    }
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

def main():
    """Main function to start the camera server"""
    print("🎥 Starting Raspberry Pi Camera Web Server...")
    
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