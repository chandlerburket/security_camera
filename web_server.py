#!/usr/bin/env python3
"""
Security Camera Web Server
Receives video stream and data from camera client(s)
Hosts web interface for viewing
"""

import time
import threading
import logging
from flask import Flask, render_template_string, Response, request, jsonify

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Store camera data
cameras = {}
camera_lock = threading.Lock()

# Door sensor data
door_sensor_data = {
    'door_state': None,
    'timestamp': None,
    'device': None,
    'last_updated': None
}

# Recording command queue
recording_commands = {}

class CameraData:
    def __init__(self, camera_id):
        self.camera_id = camera_id
        self.latest_frame = None
        self.frame_lock = threading.Lock()
        self.last_frame_time = 0

        # Status data
        self.motion_detected = False
        self.last_motion_time = 0
        self.recording = False
        self.cpu_temp = "Unknown"
        self.uptime = "Unknown"
        self.wifi_signal_dbm = None
        self.wifi_signal_quality = "Unknown"
        self.nextcloud_enabled = False
        self.pushover_enabled = False
        self.last_status_update = 0

    def update_frame(self, frame_bytes):
        """Update latest frame"""
        with self.frame_lock:
            self.latest_frame = frame_bytes
            self.last_frame_time = time.time()

    def get_frame(self):
        """Get latest frame"""
        with self.frame_lock:
            return self.latest_frame

    def update_status(self, status_data):
        """Update camera status"""
        self.motion_detected = status_data.get('motion_detected', False)
        self.last_motion_time = status_data.get('last_motion_time', 0)
        self.recording = status_data.get('recording', False)
        self.cpu_temp = status_data.get('cpu_temp', 'Unknown')
        self.uptime = status_data.get('uptime', 'Unknown')
        self.wifi_signal_dbm = status_data.get('wifi_signal_dbm')
        self.wifi_signal_quality = status_data.get('wifi_signal_quality', 'Unknown')
        self.nextcloud_enabled = status_data.get('nextcloud_enabled', False)
        self.pushover_enabled = status_data.get('pushover_enabled', False)
        self.last_status_update = time.time()

def get_camera(camera_id):
    """Get or create camera data object"""
    with camera_lock:
        if camera_id not in cameras:
            cameras[camera_id] = CameraData(camera_id)
        return cameras[camera_id]

# API Endpoints for camera client

@app.route('/api/camera/frame', methods=['POST'])
def receive_frame():
    """Receive frame from camera"""
    try:
        camera_id = request.headers.get('X-Camera-ID', 'camera1')
        frame_bytes = request.data

        camera = get_camera(camera_id)
        camera.update_frame(frame_bytes)

        return jsonify({'status': 'ok'})
    except Exception as e:
        logger.error(f"Error receiving frame: {e}")
        return jsonify({'status': 'error'}), 500

@app.route('/api/camera/status', methods=['POST'])
def receive_status():
    """Receive status update from camera"""
    try:
        status_data = request.get_json()
        camera_id = status_data.get('camera_id', 'camera1')

        camera = get_camera(camera_id)
        camera.update_status(status_data)

        # Check if there's a command for this camera
        response = {'status': 'ok'}
        if camera_id in recording_commands:
            response['command'] = recording_commands.pop(camera_id)

        return jsonify(response)
    except Exception as e:
        logger.error(f"Error receiving status: {e}")
        return jsonify({'status': 'error'}), 500

# Web interface endpoints

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Security Camera</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {
            font-family: Arial, sans-serif;
            color: slategray;
            margin: 0;
            background-color: #000000;
            text-align: center;
        }
        .container {
            position: relative;
            max-width: 1200px;
            margin: 0 auto;
            background-color: black;
            padding: 20px;
            border-radius: 10px;
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
            background-color: #09454F;
        }
        .record-button:hover:not(:disabled) {
            background-color: #073038;
        }
        .record-button.recording {
            background-color: #A8192A;
        }
        .record-button.recording:hover:not(:disabled) {
            background-color: #70111C;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Security Camera</h1>

        <div class="video-container">
            <img src="{{ url_for('video_feed', camera_id='camera1') }}" class="camera-stream" alt="Camera Stream">
            <div id="datetime-overlay" style="position: absolute; bottom: 10px; right: 10px; background: rgba(0, 0, 0, 0.7); color: white; padding: 4px 8px; border-radius: 4px; font-size: 12px; font-family: monospace;"></div>
        </div>

        <div class="info">
            <p><strong>Motion Status:</strong> <span id="motion-status">No motion</span></p>
            <p><strong>Recording:</strong> <span id="recording-status">Not recording</span></p>
            <p><strong>WiFi Signal:</strong> <span id="wifi-signal">Loading...</span></p>
            <p><strong>CPU Temperature:</strong> <span id="cpu-temp">Loading...</span></p>
            <p><strong>Uptime:</strong> <span id="uptime">Loading...</span></p>
            <p><strong>Door Status:</strong> <span id="door-status" style="font-weight: bold;">No data</span></p>
        </div>

        <div class="recording-controls">
            <button id="record-toggle-btn" class="record-button" onclick="toggleRecording()">Start Recording</button>
        </div>

        <script>
            function updateStatus() {
                fetch('/status?camera_id=camera1')
                    .then(response => response.json())
                    .then(data => {
                        // Motion status
                        const motionEl = document.getElementById('motion-status');
                        if (motionEl) {
                            motionEl.textContent = data.motion_detected ? 'Motion detected!' : 'No motion';
                            motionEl.style.color = data.motion_detected ? '#dc3545' : '#28a745';
                        }

                        // Recording status
                        const recordingEl = document.getElementById('recording-status');
                        const recordBtn = document.getElementById('record-toggle-btn');
                        if (recordingEl && recordBtn) {
                            if (data.recording) {
                                recordingEl.textContent = 'Recording...';
                                recordingEl.style.color = '#dc3545';
                                recordBtn.classList.add('recording');
                                recordBtn.textContent = 'Stop Recording';
                            } else {
                                recordingEl.textContent = 'Not recording';
                                recordingEl.style.color = '#6c757d';
                                recordBtn.classList.remove('recording');
                                recordBtn.textContent = 'Start Recording';
                            }
                        }

                        // WiFi signal
                        const wifiEl = document.getElementById('wifi-signal');
                        if (wifiEl) {
                            let signalClass = '';
                            if (data.wifi_signal_dbm !== null) {
                                const quality = data.wifi_signal_quality.toLowerCase();
                                signalClass = `signal-${quality}`;
                                wifiEl.textContent = `${data.wifi_signal_quality} (${data.wifi_signal_dbm} dBm)`;
                            } else {
                                wifiEl.textContent = 'Unknown';
                            }
                            wifiEl.className = signalClass;
                        }

                        // System info
                        const tempEl = document.getElementById('cpu-temp');
                        if (tempEl) tempEl.textContent = data.cpu_temp;

                        const uptimeEl = document.getElementById('uptime');
                        if (uptimeEl) uptimeEl.textContent = data.uptime;

                        // Door status
                        updateDoorStatus();
                    })
                    .catch(error => console.error('Status update error:', error));
            }

            function updateDoorStatus() {
                fetch('/door-status')
                    .then(response => response.json())
                    .then(data => {
                        const doorStatusEl = document.getElementById('door-status');
                        if (doorStatusEl && data.door_state !== null) {
                            const timeAgo = data.time_ago ? Math.floor(data.time_ago) : 0;
                            const state = data.door_state.toUpperCase();
                            const stateColor = data.door_state === 'open' ? '#dc3545' : '#28a745';
                            doorStatusEl.innerHTML = `<span style="color: ${stateColor};">${state}</span> (${timeAgo}s ago)`;
                        }
                    })
                    .catch(error => console.error('Door status error:', error));
            }

            function toggleRecording() {
                const recordBtn = document.getElementById('record-toggle-btn');
                const isRecording = recordBtn.classList.contains('recording');

                const endpoint = isRecording ? '/stop-recording' : '/start-recording';
                recordBtn.disabled = true;

                fetch(endpoint + '?camera_id=camera1', { method: 'POST' })
                    .then(response => response.json())
                    .then(data => {
                        console.log(data.message);
                    })
                    .catch(error => console.error('Recording error:', error))
                    .finally(() => {
                        recordBtn.disabled = false;
                        updateStatus();
                    });
            }

            function updateDateTime() {
                const now = new Date();
                const year = now.getFullYear();
                const month = String(now.getMonth() + 1).padStart(2, '0');
                const day = String(now.getDate()).padStart(2, '0');
                let hours = now.getHours();
                const ampm = hours >= 12 ? 'PM' : 'AM';
                hours = hours % 12;
                hours = hours ? hours : 12;
                const hoursFormatted = String(hours).padStart(2, '0');
                const minutes = String(now.getMinutes()).padStart(2, '0');
                const seconds = String(now.getSeconds()).padStart(2, '0');
                const dateTimeString = `${year}-${month}-${day} ${hoursFormatted}:${minutes}:${seconds} ${ampm}`;
                const overlay = document.getElementById('datetime-overlay');
                if (overlay) overlay.textContent = dateTimeString;
            }

            // Update immediately and periodically
            document.addEventListener('DOMContentLoaded', function() {
                updateStatus();
                setInterval(updateStatus, 5000);
                updateDateTime();
                setInterval(updateDateTime, 1000);
            });
        </script>
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    """Main page"""
    return render_template_string(HTML_TEMPLATE)

@app.route('/video_feed')
def video_feed():
    """Video streaming route"""
    camera_id = request.args.get('camera_id', 'camera1')

    def generate():
        camera = get_camera(camera_id)
        while True:
            frame = camera.get_frame()
            if frame:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            time.sleep(0.033)  # ~30 FPS max

    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/status')
def status():
    """Status API endpoint"""
    camera_id = request.args.get('camera_id', 'camera1')
    camera = get_camera(camera_id)

    # Calculate WiFi signal percentage
    wifi_signal_percent = None
    if camera.wifi_signal_dbm is not None:
        dbm = camera.wifi_signal_dbm
        wifi_signal_percent = (
            100 if dbm >= -30 else
            70 if dbm >= -67 else
            50 if dbm >= -70 else
            30 if dbm >= -80 else 10
        )

    return jsonify({
        'status': 'running',
        'camera_id': camera_id,
        'motion_detected': camera.motion_detected,
        'last_motion_time': camera.last_motion_time,
        'recording': camera.recording,
        'cpu_temp': camera.cpu_temp,
        'uptime': camera.uptime,
        'wifi_signal_dbm': camera.wifi_signal_dbm,
        'wifi_signal_percent': wifi_signal_percent,
        'wifi_signal_quality': camera.wifi_signal_quality,
        'nextcloud_enabled': camera.nextcloud_enabled,
        'pushover_enabled': camera.pushover_enabled,
        'last_update': camera.last_status_update
    })

@app.route('/start-recording', methods=['POST'])
def start_recording():
    """Start recording command"""
    camera_id = request.args.get('camera_id', 'camera1')
    recording_commands[camera_id] = 'start_recording'
    logger.info(f"Recording start command queued for {camera_id}")
    return jsonify({'status': 'success', 'message': 'Recording start command sent'})

@app.route('/stop-recording', methods=['POST'])
def stop_recording():
    """Stop recording command"""
    camera_id = request.args.get('camera_id', 'camera1')
    recording_commands[camera_id] = 'stop_recording'
    logger.info(f"Recording stop command queued for {camera_id}")
    return jsonify({'status': 'success', 'message': 'Recording stop command sent'})

@app.route('/webhook', methods=['POST'])
def webhook():
    """Receive webhook data from door sensor"""
    try:
        data = request.get_json()
        door_sensor_data['door_state'] = data.get('door_state')
        door_sensor_data['timestamp'] = data.get('timestamp')
        door_sensor_data['device'] = data.get('device')
        door_sensor_data['last_updated'] = time.time()
        logger.info(f"Door sensor webhook: {data.get('door_state')}")
        return jsonify({'status': 'success'})
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({'status': 'error'}), 500

@app.route('/door-status')
def door_status():
    """Get door sensor status"""
    return jsonify({
        'door_state': door_sensor_data['door_state'],
        'timestamp': door_sensor_data['timestamp'],
        'device': door_sensor_data['device'],
        'last_updated': door_sensor_data['last_updated'],
        'time_ago': time.time() - door_sensor_data['last_updated'] if door_sensor_data['last_updated'] else None
    })

def main():
    """Main function"""
    print("🌐 Starting Security Camera Web Server...")
    print("📱 Access the interface at:")
    print("   - Local: http://localhost:5000")
    print("   - Network: http://[server-ip]:5000")
    print("\n🛑 Press Ctrl+C to stop\n")

    try:
        app.run(
            host='0.0.0.0',
            port=5000,
            debug=False,
            threaded=True
        )
    except KeyboardInterrupt:
        print("\n🛑 Shutting down server...")
    finally:
        print("✅ Web server stopped")

if __name__ == '__main__':
    main()
