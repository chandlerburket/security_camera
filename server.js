#!/usr/bin/env node
/**
 * Security Camera Web Server
 * Node.js + Express + Socket.io
 * Receives video stream from camera client(s) and broadcasts to web clients
 */

const express = require('express');
const http = require('http');
const socketIo = require('socket.io');
const bodyParser = require('body-parser');

const app = express();
const server = http.createServer(app);
const io = socketIo(server, {
    cors: {
        origin: "*",
        methods: ["GET", "POST"]
    }
});

// Middleware
app.use(bodyParser.json());
app.use(bodyParser.raw({ type: 'image/jpeg', limit: '5mb' }));

// Store camera data
const cameras = new Map();

// Door sensor data
const doorSensorData = {
    door_state: null,
    timestamp: null,
    device: null,
    last_updated: null
};

// Recording command queue
const recordingCommands = new Map();

// Camera Data Class
class CameraData {
    constructor(cameraId) {
        this.cameraId = cameraId;
        this.latestFrame = null;
        this.lastFrameTime = 0;

        // Status data
        this.motionDetected = false;
        this.lastMotionTime = 0;
        this.recording = false;
        this.cpuTemp = 'Unknown';
        this.uptime = 'Unknown';
        this.wifiSignalDbm = null;
        this.wifiSignalQuality = 'Unknown';
        this.nextcloudEnabled = false;
        this.nextcloudConfig = null;
        this.pushoverEnabled = false;
        this.lastStatusUpdate = 0;
        this.frameCount = 0;
    }

    updateFrame(frameBytes) {
        this.latestFrame = frameBytes;
        this.lastFrameTime = Date.now();
        this.frameCount++;

        // Log every 50th frame
        if (this.frameCount % 50 === 0) {
            console.log(`📸 Received ${this.frameCount} frames from ${this.cameraId}, size: ${frameBytes.length} bytes`);
        }
    }

    getFrame() {
        return this.latestFrame;
    }

    isAlive() {
        return (Date.now() - this.lastFrameTime) < 10000; // 10 seconds
    }

    getFrameAge() {
        if (this.lastFrameTime === 0) return null;
        return (Date.now() - this.lastFrameTime) / 1000;
    }

    updateStatus(statusData) {
        this.motionDetected = statusData.motion_detected || false;
        this.lastMotionTime = statusData.last_motion_time || 0;
        this.recording = statusData.recording || false;
        this.cpuTemp = statusData.cpu_temp || 'Unknown';
        this.uptime = statusData.uptime || 'Unknown';
        this.wifiSignalDbm = statusData.wifi_signal_dbm || null;
        this.wifiSignalQuality = statusData.wifi_signal_quality || 'Unknown';
        this.nextcloudEnabled = statusData.nextcloud_enabled || false;
        this.nextcloudConfig = statusData.nextcloud_config || null;
        this.pushoverEnabled = statusData.pushover_enabled || false;
        this.lastStatusUpdate = Date.now();
    }
}

// Get or create camera
function getCamera(cameraId) {
    if (!cameras.has(cameraId)) {
        cameras.set(cameraId, new CameraData(cameraId));
    }
    return cameras.get(cameraId);
}

// API Endpoints for camera client

// Receive frame from camera
app.post('/api/camera/frame', (req, res) => {
    try {
        const cameraId = req.headers['x-camera-id'] || 'camera1';
        const frameBytes = req.body;

        if (!frameBytes || frameBytes.length === 0) {
            console.warn(`⚠️  Received empty frame from ${cameraId}`);
            return res.status(400).json({ status: 'error', message: 'Empty frame' });
        }

        const camera = getCamera(cameraId);
        camera.updateFrame(frameBytes);

        // Broadcast frame to all connected web clients via Socket.io
        const frameBase64 = frameBytes.toString('base64');
        io.emit('frame', {
            cameraId: cameraId,
            frame: frameBase64,
            timestamp: Date.now()
        });

        res.json({ status: 'ok' });
    } catch (error) {
        console.error(`Error receiving frame: ${error}`);
        res.status(500).json({ status: 'error' });
    }
});

// Receive status update from camera
app.post('/api/camera/status', (req, res) => {
    try {
        const statusData = req.body;
        const cameraId = statusData.camera_id || 'camera1';

        const camera = getCamera(cameraId);
        camera.updateStatus(statusData);

        // Broadcast status to web clients
        io.emit('status', {
            cameraId: cameraId,
            status: statusData
        });

        // Check if there's a command for this camera
        const response = { status: 'ok' };
        if (recordingCommands.has(cameraId)) {
            response.command = recordingCommands.get(cameraId);
            recordingCommands.delete(cameraId);
        }

        res.json(response);
    } catch (error) {
        console.error(`Error receiving status: ${error}`);
        res.status(500).json({ status: 'error' });
    }
});

// Web interface endpoints

// Status API endpoint
app.get('/status', (req, res) => {
    const cameraId = req.query.camera_id || 'camera1';
    const camera = getCamera(cameraId);

    // Calculate WiFi signal percentage
    let wifiSignalPercent = null;
    if (camera.wifiSignalDbm !== null) {
        const dbm = camera.wifiSignalDbm;
        wifiSignalPercent =
            dbm >= -30 ? 100 :
            dbm >= -67 ? 70 :
            dbm >= -70 ? 50 :
            dbm >= -80 ? 30 : 10;
    }

    res.json({
        status: 'running',
        camera_id: cameraId,
        motion_detected: camera.motionDetected,
        last_motion_time: camera.lastMotionTime,
        recording: camera.recording,
        cpu_temp: camera.cpuTemp,
        uptime: camera.uptime,
        wifi_signal_dbm: camera.wifiSignalDbm,
        wifi_signal_percent: wifiSignalPercent,
        wifi_signal_quality: camera.wifiSignalQuality,
        nextcloud_enabled: camera.nextcloudEnabled,
        nextcloud_config: camera.nextcloudConfig,
        pushover_enabled: camera.pushoverEnabled,
        last_update: camera.lastStatusUpdate
    });
});

// Start recording
app.post('/start-recording', (req, res) => {
    const cameraId = req.query.camera_id || 'camera1';
    recordingCommands.set(cameraId, 'start_recording');
    console.log(`Recording start command queued for ${cameraId}`);
    res.json({ status: 'success', message: 'Recording start command sent' });
});

// Stop recording
app.post('/stop-recording', (req, res) => {
    const cameraId = req.query.camera_id || 'camera1';
    recordingCommands.set(cameraId, 'stop_recording');
    console.log(`Recording stop command queued for ${cameraId}`);
    res.json({ status: 'success', message: 'Recording stop command sent' });
});

// Door sensor webhook
app.post('/webhook', (req, res) => {
    try {
        const data = req.body;
        doorSensorData.door_state = data.door_state;
        doorSensorData.timestamp = data.timestamp;
        doorSensorData.device = data.device;
        doorSensorData.last_updated = Date.now();

        // Broadcast to web clients
        io.emit('door-status', doorSensorData);

        console.log(`Door sensor webhook: ${data.door_state}`);
        res.json({ status: 'success' });
    } catch (error) {
        console.error(`Webhook error: ${error}`);
        res.status(500).json({ status: 'error' });
    }
});

// Get door status
app.get('/door-status', (req, res) => {
    res.json({
        door_state: doorSensorData.door_state,
        timestamp: doorSensorData.timestamp,
        device: doorSensorData.device,
        last_updated: doorSensorData.last_updated,
        time_ago: doorSensorData.last_updated ? (Date.now() - doorSensorData.last_updated) / 1000 : null
    });
});

// Debug endpoints

// Camera status debug
app.get('/debug/cameras', (req, res) => {
    const cameraInfo = {};
    cameras.forEach((camData, camId) => {
        const frameAge = camData.getFrameAge();
        cameraInfo[camId] = {
            has_frame: camData.latestFrame !== null,
            frame_size: camData.latestFrame ? camData.latestFrame.length : 0,
            frame_age_seconds: frameAge,
            is_alive: camData.isAlive(),
            last_frame_time: camData.lastFrameTime,
            last_status_update: camData.lastStatusUpdate,
            frame_count: camData.frameCount
        };
    });

    res.json({
        total_cameras: cameras.size,
        cameras: cameraInfo
    });
});

// Serve main page
app.get('/', (req, res) => {
    res.sendFile(__dirname + '/index.html');
});

// Socket.io connection handling
io.on('connection', (socket) => {
    console.log('📺 New client connected:', socket.id);

    // Send current camera status when client connects
    cameras.forEach((camera, cameraId) => {
        if (camera.latestFrame) {
            socket.emit('frame', {
                cameraId: cameraId,
                frame: camera.latestFrame.toString('base64'),
                timestamp: Date.now()
            });
        }
    });

    socket.on('disconnect', () => {
        console.log('🔌 Client disconnected:', socket.id);
    });
});

// Start server
const PORT = process.env.PORT || 5000;
server.listen(PORT, '0.0.0.0', () => {
    console.log('🌐 Starting Security Camera Web Server...');
    console.log('📱 Access the interface at:');
    console.log(`   - Local: http://localhost:${PORT}`);
    console.log(`   - Network: http://[server-ip]:${PORT}`);
    console.log('\n🔍 Debug endpoints:');
    console.log(`   - Camera status: http://localhost:${PORT}/debug/cameras`);
    console.log('\n🛑 Press Ctrl+C to stop\n');
});

// Graceful shutdown
process.on('SIGINT', () => {
    console.log('\n🛑 Shutting down server...');
    server.close(() => {
        console.log('✅ Web server stopped');
        process.exit(0);
    });
});
