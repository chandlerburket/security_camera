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
        self.nextcloud_config = None
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
        self.nextcloud_config = status_data.get('nextcloud_config')
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
            background-color: #09454F;
            transition: background-color 0.3s ease;
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

        <div id="recording-status" class="recording-status" style="display: none;">
            <span id="recording-text">Recording: 00:00</span>
        </div>

        <div class="info">
            <p style="display: flex; justify-content: space-between; align-items: center;"><strong>WiFi Signal:</strong> <span style="display: flex; align-items: center; gap: 8px;"><span class="wifi-bars" id="wifi-bars" style="display: inline-flex; align-items: baseline;"><span class="wifi-bar"></span><span class="wifi-bar"></span><span class="wifi-bar"></span><span class="wifi-bar"></span></span><span id="wifi-signal">Loading...</span></span></p>
            <p><strong>CPU Temperature:</strong> <span id="cpu-temp">Loading...</span></p>
            <p><strong>Uptime:</strong> <span id="uptime">Loading...</span></p>
            <p><strong>Door Status:</strong> <span id="door-status" style="font-weight: bold;">No data</span></p>
            <p><strong>Nextcloud Files:</strong></p>
            <p style="margin-left: 20px;">
                <a href="#" id="motion-captures-link" target="_blank" style="color: #17a2b8; text-decoration: none;">Motion Captures</a><br>
                <a href="#" id="recordings-link" target="_blank" style="color: #17a2b8; text-decoration: none;">Video Recordings</a>
            </p>
        </div>

        <!-- Recording Controls -->
        <div class="recording-controls">
            <button id="record-toggle-btn" class="record-button" onclick="toggleRecording()">Start Recording</button>
        </div>
        
        <script>
            // Function to update system status
            function updateStatus() {
                fetch('/status')
                    .then(response => {
                        if (!response.ok) {
                            throw new Error(`HTTP error! status: ${response.status}`);
                        }
                        return response.json();
                    })
                    .then(data => {
                        
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

                        // Update Nextcloud links
                        updateNextcloudLinks(data);

                        // Update webhook data
                        updateWebhookData();
                    })
                    .catch(error => {
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

            function updateWebhookData() {
                fetch('/door-status')
                    .then(response => response.json())
                    .then(data => {
                        const doorStatusEl = document.getElementById('door-status');
                        if (doorStatusEl) {
                            if (data.door_state !== null) {
                                const timeAgo = data.time_ago ? Math.floor(data.time_ago) : 0;
                                const state = data.door_state.toUpperCase();
                                const stateColor = data.door_state === 'open' ? '#dc3545' : '#28a745';
                                doorStatusEl.innerHTML = `<span style="color: ${stateColor};">${state}</span> (${timeAgo}s ago)`;
                            } else {
                                doorStatusEl.textContent = 'No data';
                                doorStatusEl.style.color = '#6c757d';
                            }
                        }
                    })
                    .catch(error => {
                        console.error('Error fetching door status:', error);
                    });
            }
            

            // Wait for page to load before updating status
            document.addEventListener('DOMContentLoaded', function() {
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
                            recordBtn.disabled = false;
                            recordBtn.classList.remove('processing');
                            recordBtn.classList.add('recording');
                            recordBtn.textContent = 'Stop Recording (00:00)';
                            startRecordingTimer();
                        } else {
                            resetRecordButton();
                        }
                    })
                    .catch(error => {
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
                        stopRecordingTimer();
                        resetRecordButton();
                    })
                    .catch(error => {
                        stopRecordingTimer();
                        resetRecordButton();
                    });
            }

            function resetRecordButton() {
                const recordBtn = document.getElementById('record-toggle-btn');
                stopRecordingTimer();
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

                        // Start timer if not already running and we don't have a local timer
                        if (!recordingStartTime) {
                            recordingStartTime = Date.now() - (duration * 1000);
                            if (!recordingTimerInterval) {
                                recordingTimerInterval = setInterval(updateRecordingTimer, 1000);
                            }
                        }
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
                        stopRecordingTimer();
                    }

                    statusDiv.style.display = 'none';
                    statusDiv.classList.remove('active');
                }
            }

            // Recording timer variables
            let recordingStartTime = null;
            let recordingTimerInterval = null;

            function startRecordingTimer() {
                recordingStartTime = Date.now();
                recordingTimerInterval = setInterval(updateRecordingTimer, 1000);
            }

            function stopRecordingTimer() {
                if (recordingTimerInterval) {
                    clearInterval(recordingTimerInterval);
                    recordingTimerInterval = null;
                }
                recordingStartTime = null;
            }

            function updateRecordingTimer() {
                if (recordingStartTime && recordingTimerInterval) {
                    const recordBtn = document.getElementById('record-toggle-btn');
                    if (recordBtn.classList.contains('recording') && !recordBtn.classList.contains('processing')) {
                        const elapsed = Math.floor((Date.now() - recordingStartTime) / 1000);
                        const minutes = Math.floor(elapsed / 60);
                        const seconds = elapsed % 60;
                        const timeString = `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
                        recordBtn.textContent = `Stop Recording (${timeString})`;
                    }
                }
            }

            function updateNextcloudLinks(data) {
                const motionLink = document.getElementById('motion-captures-link');
                const recordingsLink = document.getElementById('recordings-link');

                if (!motionLink || !recordingsLink) {
                    return;
                }

                if (data.nextcloud_enabled && data.nextcloud_config) {
                    const baseUrl = data.nextcloud_config.url;
                    const motionFolder = data.nextcloud_config.folder || '/motion_captures';
                    const videoFolder = data.nextcloud_config.video_folder || '/recordings';

                    // Construct Nextcloud web interface URLs
                    const motionUrl = `${baseUrl}/index.php/apps/files/?dir=${encodeURIComponent(motionFolder)}`;
                    const recordingsUrl = `${baseUrl}/index.php/apps/files/?dir=${encodeURIComponent(videoFolder)}`;

                    motionLink.href = motionUrl;
                    recordingsLink.href = recordingsUrl;
                    motionLink.style.color = '#17a2b8';
                    recordingsLink.style.color = '#17a2b8';
                    motionLink.textContent = 'Motion Captures';
                    recordingsLink.textContent = 'Video Recordings';
                } else {
                    motionLink.href = '#';
                    recordingsLink.href = '#';
                    motionLink.style.color = '#6c757d';
                    recordingsLink.style.color = '#6c757d';
                    motionLink.textContent = 'Motion Captures (Nextcloud disabled)';
                    recordingsLink.textContent = 'Video Recordings (Nextcloud disabled)';
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
        'nextcloud_config': camera.nextcloud_config,
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
