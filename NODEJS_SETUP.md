# Node.js + Socket.io Setup Guide

This guide will help you migrate from the Flask-based web server to the Node.js/Express/Socket.io server for better real-time streaming performance.

## Why Node.js + Socket.io?

The Flask development server has limitations with streaming:
- Buffering issues
- Connection timeout problems
- Not designed for real-time applications

Socket.io provides:
- ✅ **Real-time bidirectional communication**
- ✅ **Automatic reconnection**
- ✅ **No buffering issues**
- ✅ **Better performance** for streaming
- ✅ **Built-in connection management**

## Prerequisites

1. **Node.js and npm** (Node Package Manager)

   Check if installed:
   ```bash
   node --version
   npm --version
   ```

   Install if needed:
   ```bash
   # Ubuntu/Debian/Raspberry Pi OS
   sudo apt update
   sudo apt install nodejs npm

   # Or use NodeSource for latest version
   curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
   sudo apt install -y nodejs
   ```

## Setup Steps

### 1. Navigate to Project Directory

```bash
cd /path/to/security_camera
```

### 2. Install Node.js Dependencies

```bash
npm install
```

This will install:
- `express` - Web framework
- `socket.io` - Real-time communication library
- `body-parser` - Parse request bodies

### 3. Start the Server

**Option A: Using the startup script (recommended):**
```bash
chmod +x start_nodejs_server.sh
./start_nodejs_server.sh
```

**Option B: Direct start:**
```bash
node server.js
```

**Option C: Development mode with auto-restart:**
```bash
npm run dev
```

### 4. Keep Camera Client Running

The Python camera client remains unchanged! It will work with the Node.js server because we kept the same REST API endpoints.

```bash
# On Raspberry Pi
python3 camera_client.py
```

### 5. Access the Web Interface

Open your browser to:
- Local: http://localhost:5000
- Network: http://[server-ip]:5000

## File Structure

```
security_camera/
├── server.js                    # Node.js server (NEW)
├── index.html                   # HTML with Socket.io (NEW)
├── package.json                 # Node.js dependencies (NEW)
├── start_nodejs_server.sh       # Startup script (NEW)
├── camera_client.py             # Python camera client (UNCHANGED)
├── web_server.py                # Old Flask server (can keep for backup)
└── nextcloud_config.py          # Config files (UNCHANGED)
```

## How It Works

### Architecture Flow

1. **Camera Client (Python)** → Captures frames from Pi Camera
2. **Camera Client** → POSTs frames to `/api/camera/frame` on Node.js server
3. **Node.js Server** → Receives frames via REST API
4. **Node.js Server** → Broadcasts frames to all web clients via Socket.io
5. **Web Browser** → Receives frames in real-time via Socket.io
6. **Web Browser** → Updates image element immediately

### Key Differences from Flask

| Feature | Flask | Node.js + Socket.io |
|---------|-------|---------------------|
| Streaming method | Multipart HTTP | WebSocket |
| Buffering | Yes (problematic) | No |
| Real-time updates | Polling | Push |
| Reconnection | Manual | Automatic |
| Performance | Limited | Excellent |

## API Endpoints

The Node.js server maintains the same API as Flask:

### Camera Client Endpoints (used by Python client)

- `POST /api/camera/frame` - Receive frame from camera
- `POST /api/camera/status` - Receive status update

### Web Interface Endpoints

- `GET /` - Serve main page
- `GET /status` - Get camera status
- `POST /start-recording` - Start recording
- `POST /stop-recording` - Stop recording
- `POST /webhook` - Door sensor webhook
- `GET /door-status` - Get door status

### Debug Endpoints

- `GET /debug/cameras` - Check camera connection status

### Socket.io Events

**Server → Client:**
- `frame` - New frame available
- `status` - Status update
- `door-status` - Door sensor update

**Client → Server:**
- `connect` - Client connected
- `disconnect` - Client disconnected

## Testing the Setup

### 1. Check Server is Running

```bash
curl http://localhost:5000/debug/cameras
```

Expected output:
```json
{
  "total_cameras": 1,
  "cameras": {
    "camera1": {
      "has_frame": true,
      "frame_size": 15234,
      "frame_age_seconds": 0.5,
      "is_alive": true,
      "frame_count": 150
    }
  }
}
```

### 2. Check Browser Console

Open browser DevTools (F12) and check Console tab. You should see:
```
✅ Connected to server
📊 Received 100 frames
📊 Received 200 frames
```

### 3. Monitor Server Logs

The server will show:
```
📺 New client connected: [socket-id]
📸 Received 50 frames from camera1, size: 15234 bytes
📸 Received 100 frames from camera1, size: 15234 bytes
```

## Troubleshooting

### Issue: "Cannot find module 'express'"

**Solution:** Install dependencies
```bash
npm install
```

### Issue: "Address already in use"

**Solution:** Port 5000 is occupied (probably by Flask server)
```bash
# Stop Flask server first
pkill -f web_server.py

# Or use a different port
PORT=5001 node server.js
```

### Issue: Connection status shows "Disconnected"

**Solutions:**
1. Check server is running: `curl http://localhost:5000/debug/cameras`
2. Check browser console for errors
3. Verify no firewall blocking WebSocket connections
4. Try different browser

### Issue: No frames received

**Solutions:**
1. Check camera client is running
2. Verify camera client can reach server:
   ```bash
   curl -X POST http://server-ip:5000/api/camera/frame \
     -H "Content-Type: image/jpeg" \
     -H "X-Camera-ID: camera1" \
     --data-binary @test.jpg
   ```
3. Check `/debug/cameras` endpoint shows frames arriving

### Issue: Frames are delayed/laggy

**Possible causes:**
- Network latency
- Camera client too slow
- Too many web clients connected

**Solutions:**
1. Reduce frame rate in camera_client.py (line 476):
   ```python
   time.sleep(0.1)  # Slower frame rate
   ```
2. Reduce image quality/resolution
3. Check network connection

## Production Deployment

### Using PM2 (Process Manager)

PM2 keeps your Node.js server running and restarts it if it crashes.

1. **Install PM2:**
   ```bash
   sudo npm install -g pm2
   ```

2. **Start server with PM2:**
   ```bash
   pm2 start server.js --name camera-server
   ```

3. **Make it start on boot:**
   ```bash
   pm2 startup
   pm2 save
   ```

4. **Useful PM2 commands:**
   ```bash
   pm2 status              # Check status
   pm2 logs camera-server  # View logs
   pm2 restart camera-server  # Restart server
   pm2 stop camera-server     # Stop server
   pm2 delete camera-server   # Remove from PM2
   ```

### Using systemd

Create `/etc/systemd/system/camera-server-nodejs.service`:

```ini
[Unit]
Description=Security Camera Web Server (Node.js)
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/security_camera
ExecStart=/usr/bin/node server.js
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable camera-server-nodejs
sudo systemctl start camera-server-nodejs
sudo systemctl status camera-server-nodejs
```

View logs:
```bash
sudo journalctl -u camera-server-nodejs -f
```

## Performance Tips

1. **Run server on same machine as camera client** if possible (reduces network latency)

2. **Limit concurrent connections** if server is resource-constrained

3. **Monitor resource usage:**
   ```bash
   top
   # Press 'M' to sort by memory, 'P' to sort by CPU
   ```

4. **Adjust frame rate** in camera client based on network/server capacity

5. **Use wired Ethernet** instead of WiFi when possible

## Migrating Back to Flask

If you need to go back to the Flask server:

1. Stop Node.js server: `Ctrl+C` or `pm2 stop camera-server`
2. Start Flask server: `python3 web_server.py`
3. Camera client works with both (no changes needed)

## Next Steps

- ✅ Test the streaming performance
- ✅ Set up production deployment (PM2 or systemd)
- ✅ Configure firewall rules if needed
- ✅ Set up SSL/HTTPS for remote access (optional)
- ✅ Add authentication for security (optional)

## Getting Help

If you encounter issues:

1. Check server logs
2. Check browser console (F12)
3. Test with `/debug/cameras` endpoint
4. Verify camera client is sending frames
5. Check network connectivity

Include this information when seeking help:
- Node.js version: `node --version`
- npm version: `npm --version`
- Server logs
- Browser console errors
- Output of `/debug/cameras`
