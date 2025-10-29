# Security Camera - Quick Start Guide

## Installation

```bash
# 1. Install Node.js
sudo apt update
sudo apt install nodejs npm

# 2. Install dependencies
cd /path/to/security_camera
npm install

# 3. Make scripts executable
chmod +x start_nodejs_server.sh
chmod +x diagnose_stream.py
```

## Running the System

### Start Web Server (Node.js + Socket.io)

```bash
./start_nodejs_server.sh
```

### Start Camera Client (on Raspberry Pi)

```bash
python3 camera_client.py
```

## Access

- **Web Interface:** http://localhost:5000
- **Debug Info:** http://localhost:5000/debug/cameras

## Troubleshooting

### Quick Diagnostics

```bash
# Check if camera is sending frames
curl http://localhost:5000/debug/cameras

# Run full diagnostic
python3 diagnose_stream.py
```

### Common Issues

**No video stream:**
1. Check both camera client and server are running
2. Run: `curl http://localhost:5000/debug/cameras`
3. Look for `"has_frame": true` and `"is_alive": true`

**Address already in use:**
```bash
# Stop Flask server if running
pkill -f web_server.py
```

**Module not found:**
```bash
# Reinstall dependencies
npm install
```

## Configuration

### Camera Client (Python)
Located on Raspberry Pi, sends frames to server.

### Web Server (Node.js)
- **File:** `server.js`
- **Port:** 5000 (change with `PORT=5001 node server.js`)

### Nextcloud Setup
1. Copy config: `cp nextcloud_config_example.py nextcloud_config.py`
2. Edit with your Nextcloud URL and credentials
3. Restart camera client

## Production Deployment

```bash
# Install PM2
sudo npm install -g pm2

# Start with PM2
pm2 start server.js --name camera-server

# Auto-start on boot
pm2 startup
pm2 save
```

## File Overview

| File | Purpose |
|------|---------|
| `server.js` | Node.js web server (NEW) |
| `index.html` | Web interface with Socket.io (NEW) |
| `camera_client.py` | Python camera client (unchanged) |
| `web_server.py` | Old Flask server (backup) |
| `package.json` | Node.js dependencies |
| `NODEJS_SETUP.md` | Full setup guide |
| `DIAGNOSTICS.md` | Troubleshooting guide |

## URLs

- Main page: http://localhost:5000
- Camera debug: http://localhost:5000/debug/cameras
- Door status: http://localhost:5000/door-status
- Status API: http://localhost:5000/status

## More Help

- Full setup: See `NODEJS_SETUP.md`
- Diagnostics: See `DIAGNOSTICS.md`
- Check logs in terminal where server is running
