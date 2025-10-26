# Client-Server Architecture Setup Guide

This guide explains how to set up the security camera system in a client-server architecture, where the camera device (Pi Zero W) sends data to a separate web server.

## Architecture Overview

### Old Architecture (Single Device)
- Pi Zero W runs both camera capture AND web interface
- High resource usage on Pi Zero W
- Single point of failure

### New Architecture (Client-Server)
- **Camera Client** (Pi Zero W): Captures video, detects motion, uploads to Nextcloud
- **Web Server** (Separate machine): Hosts web interface, receives video stream
- Lower resource usage on Pi Zero W
- Better performance and scalability

## Components

### 1. Camera Client (`camera_client.py`)
Runs on: **Raspberry Pi Zero W** (camera device)

Responsibilities:
- Capture video frames
- Detect motion
- Upload images/videos to Nextcloud when motion detected
- Send Pushover notifications
- Push video stream to web server
- Send status updates to web server
- Receive recording commands from web server

### 2. Web Server (`web_server.py`)
Runs on: **Separate machine** (desktop, laptop, or another Pi)

Responsibilities:
- Host web interface
- Receive video stream from camera
- Display camera status
- Receive door sensor webhooks
- Send recording commands to camera
- Serve video to web browsers

## Setup Instructions

### Step 1: Prepare the Web Server Machine

1. **Choose your server machine**:
   - Desktop computer
   - Laptop
   - Raspberry Pi 3/4 (more powerful than Pi Zero W)
   - Cloud server

2. **Install Python and Flask**:
   ```bash
   sudo apt update
   sudo apt install python3 python3-pip
   pip3 install flask
   ```

3. **Copy server files**:
   ```bash
   # Copy only the web server script
   scp web_server.py user@server-machine:/path/to/camera/
   ```

4. **Run the web server**:
   ```bash
   cd /path/to/camera/
   python3 web_server.py
   ```

   The server will start on port 5000. Note the server's IP address.

### Step 2: Configure the Camera Client

1. **On your Pi Zero W**, create server configuration:
   ```bash
   cp server_config_example.py server_config.py
   nano server_config.py
   ```

2. **Update the configuration**:
   ```python
   SERVER_CONFIG = {
       "server_url": "http://192.168.1.100:5000",  # Your web server's IP
       "camera_id": "camera1",
   }
   ```

3. **Ensure Nextcloud and Pushover configs exist** (if using):
   ```bash
   # These should already be configured
   ls nextcloud_config.py
   ls pushover_config.py
   ```

### Step 3: Start the Camera Client

1. **Run the camera client**:
   ```bash
   python3 camera_client.py
   ```

2. **You should see**:
   ```
   🎥 Starting Camera Client...
   ✅ Nextcloud configured
   ✅ Pushover configured
   ✅ Camera initialized
   📡 Streaming to server: http://192.168.1.100:5000
   🎥 Camera ID: camera1
   ```

### Step 4: Access the Web Interface

1. **Open your browser** and navigate to:
   ```
   http://[server-ip]:5000
   ```

2. **You should see**:
   - Live video stream from camera
   - Motion detection status
   - Recording controls
   - System information (CPU temp, WiFi signal, etc.)
   - Door sensor status

## Network Configuration

### Local Network (Recommended for testing)
- Server and camera on same network
- No special configuration needed
- Access via local IP: `http://192.168.1.100:5000`

### External Access
If you want to access from outside your network:

1. **Configure port forwarding** on your router:
   - Forward external port 5000 → server machine port 5000

2. **Use HTTPS** (recommended for security):
   - Set up reverse proxy (nginx, Apache)
   - Use Let's Encrypt for SSL certificate

3. **Access via**:
   - `http://your-external-ip:5000`
   - Or use a domain name with DNS

## Running as Services (Recommended)

### Web Server Service

Create `/etc/systemd/system/camera-webserver.service`:
```ini
[Unit]
Description=Security Camera Web Server
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/home/your-username/camera
ExecStart=/usr/bin/python3 /home/your-username/camera/web_server.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable camera-webserver
sudo systemctl start camera-webserver
```

### Camera Client Service

On Pi Zero W, create `/etc/systemd/system/camera-client.service`:
```ini
[Unit]
Description=Security Camera Client
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/camera
ExecStart=/usr/bin/python3 /home/pi/camera/camera_client.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable camera-client
sudo systemctl start camera-client
```

## Communication Flow

### Video Streaming
```
Camera → POST /api/camera/frame → Server
       (JPEG frames, ~15 FPS)

Browser → GET /video_feed → Server
        (MJPEG stream)
```

### Status Updates
```
Camera → POST /api/camera/status → Server
       (Every 5 seconds)
       {motion_detected, cpu_temp, wifi, etc.}

Server → Response → Camera
       (May include commands)
       {command: "start_recording"}
```

### Recording Control
```
Browser → POST /start-recording → Server
Server → Queue command
Camera → GET status → Server
Server → Response with command → Camera
Camera → Executes command
```

### Door Sensor
```
Door Sensor → POST /webhook → Server
Server → Stores state
Browser → GET /door-status → Server
```

## Features

### What Runs on Camera (Pi Zero W)
- ✅ Video capture
- ✅ Motion detection
- ✅ Nextcloud uploads
- ✅ Pushover notifications
- ✅ Video recording
- ✅ Stream to server

### What Runs on Server
- ✅ Web interface
- ✅ Video streaming to browsers
- ✅ Door webhook receiver
- ✅ Command coordination

### What's Improved
- 🚀 Lower CPU usage on Pi Zero W
- 🚀 Faster web interface response
- 🚀 Multiple cameras support (future)
- 🚀 Better separation of concerns

## Troubleshooting

### Camera Can't Connect to Server
1. **Check server is running**:
   ```bash
   curl http://server-ip:5000/status?camera_id=camera1
   ```

2. **Check firewall**:
   ```bash
   # On server
   sudo ufw allow 5000
   ```

3. **Check network connectivity**:
   ```bash
   # From camera
   ping server-ip
   ```

### No Video in Web Interface
1. Check camera client is sending frames:
   - Look for errors in camera client logs
   - Verify server URL is correct

2. Check server is receiving frames:
   - Look at server logs for incoming frame POSTs

3. Refresh browser and check browser console

### Recording Not Working
1. Camera must have Nextcloud configured
2. Check server can send commands to camera
3. Commands are queued and sent on next status update (5 sec delay)

### High Bandwidth Usage
- Reduce camera resolution in `camera_client.py`
- Reduce frame rate (increase sleep time)
- Use local network instead of internet

## Performance Tips

### Pi Zero W Optimization
- Lower camera resolution: `(320, 240)` → `(240, 180)`
- Lower frame rate: 15 FPS → 10 FPS
- Increase status update interval: 5s → 10s

### Server Optimization
- Run on wired connection (not WiFi)
- Use SSD instead of SD card
- Multiple cores help with multiple cameras

## Migration from Single-Device Setup

If you're migrating from the original `security_cam.py`:

1. **Keep using** `nextcloud_config.py` and `pushover_config.py`
2. **Create** `server_config.py` with server URL
3. **Run** `camera_client.py` on Pi instead of `security_cam.py`
4. **Run** `web_server.py` on separate machine
5. **Access** web interface on server instead of Pi

Your Nextcloud uploads and Pushover notifications will continue to work exactly as before!

## Security Considerations

- **Don't expose web server directly to internet** without HTTPS
- **Use strong passwords** for Nextcloud
- **Consider VPN** for external access
- **Update regularly** to get security fixes
- **Firewall rules** to restrict access

## Future Enhancements

- Support for multiple cameras on one server
- WebSocket for real-time updates
- Authentication for web interface
- Camera health monitoring
- Automatic failover
- Recording to server storage
