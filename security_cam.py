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
            background-color: #f0f0f0;
            text-align: center;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
            background-color: white;
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
            padding: 10px;
            background-color: #e7f3ff;
            border-radius: 5px;
            color: #333;
        }
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
        <h1>🎥 Raspberry Pi Camera Stream</h1>
        
        <div>
            <img src="{{ url_for('video_feed') }}" class="camera-stream" alt="Camera Stream">
        </div>
        
        <div class="info">
            <p><strong>Status:</strong> Camera is streaming live</p>
            <p><strong>Resolution:</strong> 640x480 (streaming at 320x240)</p>
            <p><strong>Server:</strong> Running on Raspberry Pi</p>
        </div>
        
        <div class="controls">
            <button onclick="location.reload()">🔄 Refresh Stream</button>
        </div>
        
        <script>
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

@app.route('/status')
def status():
    """API endpoint for camera status"""
    return {
        'status': 'running' if streamer.running else 'stopped',
        'camera_initialized': streamer.picam2 is not None
    }

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