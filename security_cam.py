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

# PIL removed - not needed for basic camera streaming on Pi Zero W

try:
    import cv2
    import numpy as np
except ImportError:
    print("❌ OpenCV not found. Install with: sudo apt install python3-opencv python3-numpy")
    print("For Pi Zero W, use system packages for better performance")
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
        self.motion_threshold = 2000  # Reduced threshold for lower resolution on Pi Zero W
        self.last_motion_time = 0
        self.last_save_time = 0  # Track when last image was saved

        # OwnCloud configuration - update these with your server details
        self.owncloud_enabled = False  # Set to True to enable uploads
        self.owncloud_url = "http://192.168.1.100"  # Your OwnCloud server IP
        self.owncloud_username = "camera_user"  # Your OwnCloud username
        self.owncloud_password = "your_password"  # Your OwnCloud password
        self.owncloud_folder = "/motion_captures"  # Folder to save images
        self.owncloud_video_folder = "/recordings"  # Folder to save videos
        self.save_interval = 10  # Increased interval for Pi Zero W to reduce I/O load

        # Pushover configuration - update these with your Pushover credentials
        self.pushover_enabled = False  # Set to True to enable notifications
        self.pushover_user_key = "your_pushover_user_key"  # Your Pushover user key
        self.pushover_api_token = "your_pushover_api_token"  # Your Pushover application token
        self.pushover_notify_interval = 120  # Increased interval for Pi Zero W
        self.last_pushover_time = 0  # Track when last notification was sent

        # Video recording variables (optimized for Pi Zero W)
        self.recording = False
        self.recording_start_time = None
        self.recording_thread = None
        self.recording_temp_dir = None
        self.max_recording_duration = 120  # 2 minutes max for Pi Zero W
        self.recording_frame_interval = 2.0  # Capture every 2 seconds for ultra-light recording

        # System monitoring variables
        self.system_monitor_enabled = True
        self.last_health_check = 0
        self.health_check_interval = 300  # Check system health every 5 minutes
        self.error_count = 0
        self.max_errors_before_notification = 3
        self.last_error_notification = 0
        self.system_start_time = time.time()
        self.startup_notification_sent = False

    def configure_owncloud(self, url, username, password, folder="/motion_captures", video_folder="/recordings", enabled=True):
        """Configure OwnCloud settings for image and video uploads"""
        self.owncloud_url = url.rstrip('/')  # Remove trailing slash
        self.owncloud_username = username
        self.owncloud_password = password
        self.owncloud_folder = folder if folder.startswith('/') else f'/{folder}'
        self.owncloud_video_folder = video_folder if video_folder.startswith('/') else f'/{video_folder}'
        self.owncloud_enabled = enabled

        logger.info(f"🔧 OwnCloud configured: {url} - Images: {folder}, Videos: {video_folder} (enabled: {enabled})")

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
            
            # Optimized configuration for Pi Zero W - lower resolution and frame rate
            config = self.picam2.create_video_configuration(
                main={"size": (320, 240)},  # Reduced resolution for Pi Zero W
                controls={"FrameRate": 15}  # Lower frame rate to reduce CPU load
            )
            
            self.picam2.configure(config)
            self.picam2.start()
            
            # Shorter warm-up time for Pi Zero W
            time.sleep(1)
            
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
            # Smaller blur kernel for Pi Zero W to reduce processing
            gray = cv2.GaussianBlur(gray, (11, 11), 0)

            # Initialize background frame if this is the first frame
            if self.previous_frame is None:
                self.previous_frame = gray
                return False

            # Compute the absolute difference between current and previous frame
            frame_delta = cv2.absdiff(self.previous_frame, gray)

            # Apply threshold to get binary image
            thresh = cv2.threshold(frame_delta, 30, 255, cv2.THRESH_BINARY)[1]

            # Reduce dilation iterations for Pi Zero W
            thresh = cv2.dilate(thresh, None, iterations=1)

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

            # Update motion status - shorter detection window for Pi Zero W
            self.motion_detected = motion_detected or (time.time() - self.last_motion_time < 2.0)

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

                # Recording is handled separately to avoid blocking main capture loop

                # Update shared frame data
                with self.condition:
                    self.frame = frame_bytes
                    self.condition.notify_all()
                    
                # Longer delay optimized for Pi Zero W
                time.sleep(0.067)  # ~15 FPS - reduces CPU load on Pi Zero W
                
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

    def upload_to_owncloud(self, data, filename, folder_type='image'):
        """Upload data to OwnCloud server via WebDAV"""
        if not self.owncloud_enabled:
            return False

        try:
            # Choose folder based on type
            if folder_type == 'video':
                folder = self.owncloud_video_folder
                content_type = 'video/mp4'
            else:
                folder = self.owncloud_folder
                content_type = 'image/jpeg'

            # Construct the full WebDAV URL
            webdav_url = f"{self.owncloud_url}/remote.php/webdav{folder}/{filename}"

            # Prepare authentication
            auth = HTTPBasicAuth(self.owncloud_username, self.owncloud_password)

            # Set headers for WebDAV upload
            headers = {
                'Content-Type': content_type,
            }

            # Upload the file using PUT method
            response = requests.put(
                webdav_url,
                data=data,
                auth=auth,
                headers=headers,
                timeout=30  # Longer timeout for videos
            )

            if response.status_code in [200, 201, 204]:
                logger.info(f"✅ Successfully uploaded {filename} to OwnCloud ({folder_type})")
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

    def send_pushover_notification(self, message, title="Motion Detected", image_bytes=None):
        """Send a notification via Pushover API with optional image attachment"""
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

            # Prepare files for image attachment if provided
            files = None
            if image_bytes:
                files = {
                    'attachment': ('motion_capture.jpg', image_bytes, 'image/jpeg')
                }

            # Send the notification
            response = requests.post(
                pushover_url,
                data=data,
                files=files,
                timeout=10
            )

            if response.status_code == 200:
                response_json = response.json()
                if response_json.get('status') == 1:
                    self.last_pushover_time = current_time
                    image_status = " with image" if image_bytes else ""
                    logger.info(f"🔔 Pushover notification sent successfully{image_status}")
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

            # Send Pushover notification with image
            notification_message = f"Motion detected at {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(current_time))}"
            self.send_pushover_notification(notification_message, image_bytes=frame_bytes)

            # Upload to OwnCloud if enabled
            if self.owncloud_enabled:
                success = self.upload_to_owncloud(frame_bytes, filename, 'image')
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

    def start_recording(self):
        """Start video recording (optimized for Pi Zero W)"""
        if self.recording:
            return {"status": "error", "message": "Recording already in progress"}

        try:
            import tempfile
            import threading

            # Create temporary directory for recording
            self.recording_temp_dir = tempfile.mkdtemp(prefix="camera_rec_")
            self.recording = True
            self.recording_start_time = time.time()

            # Start recording in separate thread to avoid blocking
            self.recording_thread = threading.Thread(target=self._record_frames, daemon=True)
            self.recording_thread.start()

            logger.info("🎥 Started lightweight video recording")
            return {"status": "success", "message": "Recording started"}

        except Exception as e:
            self.recording = False
            if self.recording_temp_dir:
                import shutil
                shutil.rmtree(self.recording_temp_dir, ignore_errors=True)
            error_msg = f"Failed to start recording: {e}"
            logger.error(error_msg)
            return {"status": "error", "message": error_msg}

    def stop_recording(self):
        """Stop video recording and save to file (optimized for Pi Zero W)"""
        if not self.recording:
            return {"status": "error", "message": "No recording in progress"}

        try:
            # Signal recording to stop
            self.recording = False
            recording_duration = time.time() - self.recording_start_time

            # Wait for recording thread to finish (with timeout)
            if self.recording_thread and self.recording_thread.is_alive():
                self.recording_thread.join(timeout=5)

            # Generate filename with timestamp
            timestamp = time.strftime("%Y%m%d_%H%M%S", time.localtime(self.recording_start_time))
            filename = f"recording_{timestamp}.mp4"

            # Create video from saved frames
            video_data = self.create_video_from_temp_files()

            if video_data:
                # Upload to OwnCloud if enabled
                if self.owncloud_enabled:
                    success = self.upload_to_owncloud(video_data, filename, 'video')
                    if success:
                        logger.info(f"🎥 Recording saved: {filename} (duration: {recording_duration:.1f}s)")
                        return {
                            "status": "success",
                            "message": f"Recording saved: {filename}",
                            "duration": recording_duration
                        }
                    else:
                        return {"status": "error", "message": "Failed to upload recording"}
                else:
                    logger.info(f"🎥 Recording completed but OwnCloud upload disabled (duration: {recording_duration:.1f}s)")
                    return {
                        "status": "success",
                        "message": "Recording completed (upload disabled)",
                        "duration": recording_duration
                    }
            else:
                return {"status": "error", "message": "Failed to create video file"}

        except Exception as e:
            self.recording = False
            error_msg = f"Failed to stop recording: {e}"
            logger.error(error_msg)
            return {"status": "error", "message": error_msg}
        finally:
            # Clean up temporary directory
            if self.recording_temp_dir:
                import shutil
                shutil.rmtree(self.recording_temp_dir, ignore_errors=True)
                self.recording_temp_dir = None

    def _record_frames(self):
        """Background thread to capture frames for recording (ultra-lightweight)"""
        import os
        frame_count = 0
        last_capture_time = 0

        logger.info("Recording thread started")

        while self.recording:
            try:
                current_time = time.time()

                # Check if we've exceeded max duration
                if current_time - self.recording_start_time > self.max_recording_duration:
                    logger.info(f"Auto-stopping recording after {self.max_recording_duration} seconds")
                    self.recording = False
                    break

                # Only capture frames at specified interval
                if current_time - last_capture_time >= self.recording_frame_interval:
                    try:
                        # Capture frame directly to file (no memory storage)
                        frame_path = os.path.join(self.recording_temp_dir, f"frame_{frame_count:04d}.jpg")
                        self.picam2.capture_file(frame_path)
                        frame_count += 1
                        last_capture_time = current_time

                        if frame_count % 10 == 0:  # Log every 10 frames
                            logger.debug(f"Captured {frame_count} frames")

                    except Exception as e:
                        logger.warning(f"Failed to capture frame {frame_count}: {e}")

                # Short sleep to prevent excessive CPU usage
                time.sleep(0.1)

            except Exception as e:
                logger.error(f"Error in recording thread: {e}")
                break

        logger.info(f"Recording thread finished. Captured {frame_count} frames")

    def create_video_from_temp_files(self):
        """Create MP4 video from temporary frame files (ultra-fast for Pi Zero W)"""
        try:
            import os
            import glob

            if not self.recording_temp_dir or not os.path.exists(self.recording_temp_dir):
                return None

            # Find all frame files
            frame_files = sorted(glob.glob(os.path.join(self.recording_temp_dir, "frame_*.jpg")))

            if len(frame_files) == 0:
                logger.warning("No frame files found for video creation")
                return None

            logger.info(f"Creating video from {len(frame_files)} frames")

            # Output path
            output_path = os.path.join(self.recording_temp_dir, "output.mp4")

            # Ultra-simple ffmpeg command for Pi Zero W (minimal processing)
            ffmpeg_cmd = [
                'ffmpeg', '-y',  # Overwrite output
                '-framerate', '0.5',  # Very slow framerate (1 frame per 2 seconds)
                '-i', os.path.join(self.recording_temp_dir, 'frame_%04d.jpg'),
                '-c:v', 'libx264',  # H.264 codec
                '-preset', 'ultrafast',  # Fastest encoding
                '-crf', '35',  # Lower quality for smaller files
                '-pix_fmt', 'yuv420p',
                '-movflags', '+faststart',  # Optimize for streaming
                output_path
            ]

            # Run ffmpeg with longer timeout
            result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, timeout=120)

            if result.returncode == 0 and os.path.exists(output_path):
                # Read the video file
                with open(output_path, 'rb') as f:
                    video_data = f.read()
                logger.info(f"Video created successfully: {len(video_data)} bytes")
                return video_data
            else:
                logger.error(f"FFmpeg failed: {result.stderr}")
                return None

        except Exception as e:
            logger.error(f"Error creating video: {e}")
            return None

    def get_recording_status(self):
        """Get current recording status (lightweight)"""
        if self.recording and self.recording_start_time:
            duration = time.time() - self.recording_start_time

            # Count frames from temp directory if available
            frame_count = 0
            if self.recording_temp_dir:
                try:
                    import os
                    import glob
                    frame_files = glob.glob(os.path.join(self.recording_temp_dir, "frame_*.jpg"))
                    frame_count = len(frame_files)
                except:
                    frame_count = 0

            return {
                'recording': True,
                'duration': duration,
                'frames': frame_count,
                'max_duration': self.max_recording_duration
            }
        else:
            return {'recording': False}

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
        .recording-controls {
            display: flex;
            justify-content: center;
            gap: 10px;
            margin: 15px 0;
            flex-wrap: wrap;
        }
        button {
            padding: 10px 20px;
            margin: 5px;
            background-color: #007bff;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 14px;
            min-width: 120px;
        }
        button:hover {
            background-color: #0056b3;
        }
        button:disabled {
            background-color: #6c757d;
            cursor: not-allowed;
        }
        .record-button {
            background-color: #0F6925;
            transition: background-color 0.3s ease;
        }
        .record-button:hover:not(:disabled) {
            background-color: #094717;
        }
        .record-button.recording {
            background-color: #A8192A;
        }
        .record-button.recording:hover:not(:disabled) {
            background-color: #70111C;
        }
        .record-button.processing {
            background-color: #A8192A;
        }
        .recording-status {
            background-color: #fff3cd;
            border: 1px solid #ffeaa7;
            border-radius: 5px;
            padding: 10px;
            margin: 10px 0;
            color: #856404;
            text-align: center;
        }
        .recording-status.active {
            background-color: #3A4142;
            border-color: #bee5eb;
            color: #0c5460;
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

        <!-- Recording Controls -->
        <div class="recording-controls">
            <button id="record-toggle-btn" class="record-button" onclick="toggleRecording()">Start Recording</button>
        </div>

        <div id="recording-status" class="recording-status" style="display: none;">
            <span id="recording-text">Recording: 00:00</span>
        </div>

        <div class="info">
            <p style="display: flex; justify-content: space-between; align-items: center;"><strong>Camera Status:</strong> <span id="camera-status" style="width: 12px; height: 12px; border-radius: 50%; background-color: #4CAF50; display: inline-block;"></span></p>
            <p style="display: flex; justify-content: space-between; align-items: center;"><strong>Recording Status:</strong> <span id="record-status" style="width: 12px; height: 12px; border-radius: 50%; background-color: #ddd; display: inline-block;"></span></p>
            <p style="display: flex; justify-content: space-between; align-items: center;"><strong>Motion Detection:</strong> <span id="motion-status" style="width: 12px; height: 12px; border-radius: 50%; background-color: #ddd; display: inline-block;"></span></p>
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

                        // Update recording status
                        const recordStatusEl = document.getElementById('record-status');
                        if (recordStatusEl && data.recording_status) {
                            if (data.recording_status.recording) {
                                recordStatusEl.style.backgroundColor = '#f44336'; // Red for recording
                                updateRecordingUI(true, data.recording_status.duration);
                            } else {
                                recordStatusEl.style.backgroundColor = '#ddd'; // Gray for not recording
                                updateRecordingUI(false);
                            }
                        }

                        // Update motion detection status
                        const motionStatusEl = document.getElementById('motion-status');
                        if (motionStatusEl) {
                            if (data.motion_detected) {
                                motionStatusEl.style.backgroundColor = '#ff9800'; // Orange for motion
                            } else {
                                motionStatusEl.style.backgroundColor = '#ddd'; // Gray for no motion
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
                // Update status immediately and then every 20 seconds (further reduced for Pi Zero W)
                updateStatus();
                setInterval(updateStatus, 20000);
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

            // Recording functions
            function toggleRecording() {
                const recordBtn = document.getElementById('record-toggle-btn');
                const isRecording = recordBtn.classList.contains('recording');

                if (isRecording) {
                    stopRecording();
                } else {
                    startRecording();
                }
            }

            function startRecording() {
                const recordBtn = document.getElementById('record-toggle-btn');

                // Immediate UI feedback
                recordBtn.disabled = true;
                recordBtn.classList.add('processing');
                recordBtn.textContent = 'Starting...';

                fetch('/start-recording', { method: 'POST' })
                    .then(response => response.json())
                    .then(data => {
                        if (data.status === 'success') {
                            console.log('Recording started');
                            recordBtn.disabled = false;
                            recordBtn.classList.remove('processing');
                            recordBtn.classList.add('recording');
                            recordBtn.textContent = 'Stop Recording';
                        } else {
                            alert('Failed to start recording: ' + data.message);
                            resetRecordButton();
                        }
                    })
                    .catch(error => {
                        console.error('Error starting recording:', error);
                        alert('Error starting recording');
                        resetRecordButton();
                    });
            }

            function stopRecording() {
                const recordBtn = document.getElementById('record-toggle-btn');

                // Immediate UI feedback
                recordBtn.disabled = true;
                recordBtn.classList.add('processing');
                recordBtn.textContent = 'Stopping...';

                fetch('/stop-recording', { method: 'POST' })
                    .then(response => response.json())
                    .then(data => {
                        if (data.status === 'success') {
                            alert('Recording saved: ' + data.message);
                        } else {
                            alert('Failed to stop recording: ' + data.message);
                        }
                        resetRecordButton();
                    })
                    .catch(error => {
                        console.error('Error stopping recording:', error);
                        alert('Error stopping recording');
                        resetRecordButton();
                    });
            }

            function resetRecordButton() {
                const recordBtn = document.getElementById('record-toggle-btn');
                recordBtn.disabled = false;
                recordBtn.classList.remove('recording', 'processing');
                recordBtn.textContent = 'Start Recording';
            }

            function updateRecordingUI(isRecording, duration = 0) {
                const recordBtn = document.getElementById('record-toggle-btn');
                const statusDiv = document.getElementById('recording-status');
                const statusText = document.getElementById('recording-text');

                if (isRecording) {
                    // Don't update button if it's in processing state
                    if (!recordBtn.classList.contains('processing')) {
                        recordBtn.classList.add('recording');
                        recordBtn.textContent = 'Stop Recording';
                    }

                    statusDiv.style.display = 'block';
                    statusDiv.classList.add('active');

                    const minutes = Math.floor(duration / 60);
                    const seconds = Math.floor(duration % 60);
                    statusText.textContent = `Recording: ${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
                } else {
                    // Don't update button if it's in processing state
                    if (!recordBtn.classList.contains('processing')) {
                        recordBtn.classList.remove('recording');
                        recordBtn.textContent = 'Start Recording';
                    }

                    statusDiv.style.display = 'none';
                    statusDiv.classList.remove('active');
                }
            }

            // Update datetime immediately and then every second
            updateDateTime();
            setInterval(updateDateTime, 1000);

            // Auto-refresh disabled for Pi Zero W to reduce resource usage
            // Uncomment below if needed:
            // setTimeout(function() {
            //     location.reload();
            // }, 600000);  // 10 minutes instead of 5
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
        'recording_status': streamer.get_recording_status(),
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

@app.route('/start-recording', methods=['POST'])
def start_recording():
    """Start video recording"""
    try:
        result = streamer.start_recording()
        return result
    except Exception as e:
        return {"status": "error", "message": f"Error starting recording: {str(e)}"}

@app.route('/stop-recording', methods=['POST'])
def stop_recording():
    """Stop video recording"""
    try:
        result = streamer.stop_recording()
        return result
    except Exception as e:
        return {"status": "error", "message": f"Error stopping recording: {str(e)}"}

@app.route('/recording-status')
def recording_status():
    """Get current recording status"""
    try:
        return streamer.get_recording_status()
    except Exception as e:
        return {"status": "error", "message": f"Error getting recording status: {str(e)}"}

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
            video_folder=OWNCLOUD_CONFIG.get("video_folder", "/recordings"),
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
            threaded=True,   # Enable threading for multiple connections
            use_reloader=False  # Disable reloader for Pi Zero W
        )
    except KeyboardInterrupt:
        print("\n🛑 Shutting down server...")
    finally:
        streamer.stop()
        print("✅ Camera server stopped successfully!")

if __name__ == '__main__':
    main()