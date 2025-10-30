#!/usr/bin/env python3
"""
Raspberry Pi Camera Client
Captures video and sends data to a central web server
Optimized for Pi Zero W
"""

import io
import time
import threading
import sys
import logging
import subprocess
import requests

# Try importing required packages
try:
    from picamera2 import Picamera2
except ImportError:
    print("❌ picamera2 not found. Install with: sudo apt install python3-picamera2")
    sys.exit(1)

try:
    import cv2
    import numpy as np
except ImportError:
    print("❌ OpenCV not found. Install with: sudo apt install python3-opencv python3-numpy")
    sys.exit(1)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CameraClient:
    def __init__(self, server_url, camera_id="camera1"):
        self.picam2 = None
        self.running = False
        self.server_url = server_url.rstrip('/')
        self.camera_id = camera_id

        # Motion detection variables
        self.motion_detected = False
        self.previous_frame = None
        self.motion_threshold = 2000
        self.last_motion_time = 0

        # Video recording variables
        self.recording = False
        self.recording_start_time = None
        self.recording_thread = None
        self.recording_temp_dir = None
        self.max_recording_duration = 120
        self.recording_frame_interval = 2.0

        # Status update interval
        self.status_update_interval = 5  # seconds
        self.last_status_update = 0


    def initialize_camera(self):
        """Initialize the camera"""
        try:
            self.picam2 = Picamera2()
            config = self.picam2.create_video_configuration(
                main={"size": (320, 240)},
                controls={"FrameRate": 15}
            )
            self.picam2.configure(config)
            self.picam2.start()
            time.sleep(1)
            logger.info("✅ Camera initialized")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to initialize camera: {e}")
            return False

    def detect_motion(self, frame_bytes):
        """Detect motion in frame"""
        try:
            nparr = np.frombuffer(frame_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (11, 11), 0)

            if self.previous_frame is None:
                self.previous_frame = gray
                return False

            frame_delta = cv2.absdiff(self.previous_frame, gray)
            thresh = cv2.threshold(frame_delta, 30, 255, cv2.THRESH_BINARY)[1]
            thresh = cv2.dilate(thresh, None, iterations=1)
            contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            motion_detected = False
            for contour in contours:
                if cv2.contourArea(contour) > self.motion_threshold:
                    motion_detected = True
                    self.last_motion_time = time.time()
                    break

            self.previous_frame = gray
            self.motion_detected = motion_detected or (time.time() - self.last_motion_time < 2.0)
            return self.motion_detected

        except Exception as e:
            logger.error(f"❌ Motion detection error: {e}")
            return False

    def upload_motion_image_to_server(self, frame_bytes):
        """Upload motion image to server (server handles Nextcloud/Pushover)"""
        try:
            response = requests.post(
                f"{self.server_url}/api/camera/motion-image",
                data=frame_bytes,
                headers={
                    'Content-Type': 'image/jpeg',
                    'X-Camera-ID': self.camera_id
                },
                timeout=5
            )

            if response.status_code == 200:
                result = response.json()
                if result.get('status') == 'ok':
                    logger.info(f"✅ Motion image uploaded: {result.get('filename')}")
                    return True
                elif result.get('status') == 'skipped':
                    return False

        except Exception as e:
            logger.error(f"❌ Motion image upload error: {e}")
        return False

    def send_status_update(self):
        """Send status update to server"""
        try:
            import socket
            import subprocess
            import re

            # Get system info
            status_data = {
                'camera_id': self.camera_id,
                'motion_detected': self.motion_detected,
                'last_motion_time': self.last_motion_time,
                'recording': self.recording
            }

            # Get system metrics
            try:
                with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                    temp = int(f.read().strip()) / 1000.0
                    status_data['cpu_temp'] = f"{temp:.1f}°C"
            except:
                status_data['cpu_temp'] = 'Unknown'

            try:
                with open('/proc/uptime', 'r') as f:
                    uptime_seconds = float(f.read().split()[0])
                    hours = int(uptime_seconds // 3600)
                    minutes = int((uptime_seconds % 3600) // 60)
                    status_data['uptime'] = f"{hours}h {minutes}m"
            except:
                status_data['uptime'] = 'Unknown'

            # Get WiFi signal
            try:
                result = subprocess.run(['iwconfig'], capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    signal_match = re.search(r'Signal level=(-?\d+) dBm', result.stdout)
                    if signal_match:
                        signal_dbm = int(signal_match.group(1))
                        status_data['wifi_signal_dbm'] = signal_dbm
                        status_data['wifi_signal_quality'] = (
                            'Excellent' if signal_dbm >= -30 else
                            'Good' if signal_dbm >= -67 else
                            'Fair' if signal_dbm >= -70 else
                            'Weak' if signal_dbm >= -80 else 'Poor'
                        )
            except:
                pass

            # Send to server
            response = requests.post(
                f"{self.server_url}/api/camera/status",
                json=status_data,
                timeout=5
            )

            if response.status_code == 200:
                # Check for commands from server
                data = response.json()
                if data.get('command'):
                    self.handle_command(data['command'])

        except Exception as e:
            logger.warning(f"⚠️  Status update failed: {e}")

    def handle_command(self, command):
        """Handle command from server"""
        if command == 'start_recording':
            logger.info("📹 Server requested recording start")
            self.start_recording()
        elif command == 'stop_recording':
            logger.info("⏹️  Server requested recording stop")
            self.stop_recording()

    def start_recording(self):
        """Start video recording"""
        if self.recording:
            return

        try:
            import tempfile
            self.recording_temp_dir = tempfile.mkdtemp(prefix="camera_rec_")
            self.recording = True
            self.recording_start_time = time.time()
            self.recording_thread = threading.Thread(target=self._record_frames, daemon=True)
            self.recording_thread.start()
            logger.info("🎥 Recording started")
        except Exception as e:
            logger.error(f"❌ Recording start failed: {e}")
            self.recording = False

    def stop_recording(self):
        """Stop recording and upload"""
        if not self.recording:
            return

        try:
            self.recording = False
            recording_duration = time.time() - self.recording_start_time

            if self.recording_thread and self.recording_thread.is_alive():
                self.recording_thread.join(timeout=5)

            video_data = self._create_video_from_temp_files()

            if video_data:
                self._upload_video_to_server(video_data)

        except Exception as e:
            logger.error(f"❌ Recording stop failed: {e}")
        finally:
            if self.recording_temp_dir:
                import shutil
                shutil.rmtree(self.recording_temp_dir, ignore_errors=True)
                self.recording_temp_dir = None

    def _upload_video_to_server(self, video_data):
        """Upload video to server (server handles Nextcloud upload)"""
        try:
            response = requests.post(
                f"{self.server_url}/api/camera/video",
                data=video_data,
                headers={
                    'Content-Type': 'video/mp4',
                    'X-Camera-ID': self.camera_id
                },
                timeout=60
            )

            if response.status_code == 200:
                result = response.json()
                if result.get('status') == 'ok':
                    logger.info(f"✅ Video uploaded: {result.get('filename')} ({result.get('size')} bytes)")
                    return True

        except Exception as e:
            logger.error(f"❌ Video upload error: {e}")
        return False

    def _record_frames(self):
        """Background thread for recording"""
        import os
        frame_count = 0
        last_capture_time = 0

        while self.recording:
            try:
                current_time = time.time()

                if current_time - self.recording_start_time > self.max_recording_duration:
                    self.recording = False
                    break

                if current_time - last_capture_time >= self.recording_frame_interval:
                    frame_path = os.path.join(self.recording_temp_dir, f"frame_{frame_count:04d}.jpg")
                    self.picam2.capture_file(frame_path)
                    frame_count += 1
                    last_capture_time = current_time

                time.sleep(0.1)
            except Exception as e:
                logger.error(f"❌ Recording frame error: {e}")
                break

    def _create_video_from_temp_files(self):
        """Create MP4 from frames"""
        try:
            import os
            import glob

            if not self.recording_temp_dir or not os.path.exists(self.recording_temp_dir):
                return None

            frame_files = sorted(glob.glob(os.path.join(self.recording_temp_dir, "frame_*.jpg")))
            if len(frame_files) == 0:
                return None

            output_path = os.path.join(self.recording_temp_dir, "output.mp4")

            ffmpeg_cmd = [
                'ffmpeg', '-y',
                '-framerate', '0.5',
                '-i', os.path.join(self.recording_temp_dir, 'frame_%04d.jpg'),
                '-c:v', 'libx264',
                '-preset', 'ultrafast',
                '-crf', '35',
                '-pix_fmt', 'yuv420p',
                '-movflags', '+faststart',
                output_path
            ]

            result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, timeout=120)

            if result.returncode == 0 and os.path.exists(output_path):
                with open(output_path, 'rb') as f:
                    return f.read()

        except Exception as e:
            logger.error(f"❌ Video creation error: {e}")
        return None

    def stream_to_server(self):
        """Continuously capture and stream to server"""
        self.running = True

        while self.running:
            try:
                buffer = io.BytesIO()
                self.picam2.capture_file(buffer, format='jpeg')
                frame_bytes = buffer.getvalue()

                # Motion detection
                motion_detected = self.detect_motion(frame_bytes)
                if motion_detected:
                    self.upload_motion_image_to_server(frame_bytes)

                # Send frame to server
                try:
                    response = requests.post(
                        f"{self.server_url}/api/camera/frame",
                        data=frame_bytes,
                        headers={
                            'Content-Type': 'image/jpeg',
                            'X-Camera-ID': self.camera_id
                        },
                        timeout=1.0  # Reduced timeout for faster recovery
                    )
                    if response.status_code != 200:
                        logger.warning(f"⚠️  Frame upload failed: HTTP {response.status_code}")
                except requests.exceptions.Timeout:
                    logger.warning(f"⚠️  Frame upload timeout")
                except requests.exceptions.ConnectionError:
                    logger.error(f"❌ Cannot connect to server at {self.server_url}")
                    time.sleep(5)  # Wait before retrying
                except Exception as e:
                    logger.warning(f"⚠️  Frame upload error: {e}")

                # Send status update periodically
                current_time = time.time()
                if current_time - self.last_status_update >= self.status_update_interval:
                    self.send_status_update()
                    self.last_status_update = current_time

                time.sleep(0.067)  # ~15 FPS

            except Exception as e:
                logger.error(f"❌ Streaming error: {e}")
                time.sleep(1)

    def stop(self):
        """Stop the camera"""
        self.running = False
        if self.picam2:
            self.picam2.stop()
            self.picam2.close()
        logger.info("Camera stopped")

def main():
    """Main function"""
    print("🎥 Starting Camera Client...")

    # Load server configuration
    try:
        from server_config import SERVER_CONFIG
        server_url = SERVER_CONFIG["server_url"]
        camera_id = SERVER_CONFIG.get("camera_id", "camera1")
    except ImportError:
        print("⚠️  No server_config.py found. Using defaults.")
        server_url = "http://192.168.1.100:5000"
        camera_id = "camera1"

    client = CameraClient(server_url, camera_id)

    # Initialize camera
    if not client.initialize_camera():
        print("❌ Camera initialization failed")
        return

    print(f"📡 Streaming to server: {server_url}")
    print(f"🎥 Camera ID: {camera_id}")
    print("🛑 Press Ctrl+C to stop\n")

    try:
        client.stream_to_server()
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
    finally:
        client.stop()
        print("✅ Camera client stopped")

if __name__ == '__main__':
    main()
