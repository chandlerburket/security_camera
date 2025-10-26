# Architecture Comparison

## Overview

This project now supports two architectures. Choose the one that fits your needs.

## Single-Device Architecture (Original)

### Files
- `security_cam.py` - All-in-one script

### Setup
```
[Pi Zero W]
├── Camera capture
├── Motion detection
├── Web server
├── Nextcloud upload
└── Pushover notifications
```

### Usage
```bash
# On Pi Zero W
python3 security_cam.py

# Access at http://pi-ip:5000
```

### Pros
- ✅ Simple setup (one device)
- ✅ No network dependencies
- ✅ All-in-one solution

### Cons
- ❌ High CPU usage on Pi Zero W
- ❌ Slower web interface
- ❌ Single point of failure
- ❌ Cannot support multiple cameras

### Best For
- Quick testing
- Single camera setups
- No additional hardware available

---

## Client-Server Architecture (New)

### Files
- `camera_client.py` - Runs on camera device
- `web_server.py` - Runs on separate server
- `server_config.py` - Client configuration

### Setup
```
[Pi Zero W - Camera]          [Server - Web Interface]
├── Camera capture            ├── Receive video stream
├── Motion detection   ───────>├── Host web UI
├── Nextcloud upload          ├── Receive webhooks
└── Send data to server       └── Send commands

Browser ────────────────────────> Access web UI on server
```

### Usage
```bash
# On server machine
python3 web_server.py

# On Pi Zero W
python3 camera_client.py

# Access at http://server-ip:5000
```

### Pros
- ✅ Lower CPU usage on Pi Zero W
- ✅ Faster web interface
- ✅ Better performance
- ✅ Can support multiple cameras
- ✅ Server can be more powerful machine
- ✅ Easier to scale

### Cons
- ❌ Requires two machines
- ❌ Network dependency
- ❌ Slightly more complex setup

### Best For
- Production deployments
- Better performance needed
- Multiple cameras (future)
- You have a spare computer/server

---

## Feature Comparison

| Feature | Single-Device | Client-Server |
|---------|--------------|---------------|
| Video streaming | ✅ Direct | ✅ Via server |
| Motion detection | ✅ On Pi | ✅ On Pi |
| Nextcloud upload | ✅ On Pi | ✅ On Pi |
| Pushover notifications | ✅ On Pi | ✅ On Pi |
| Video recording | ✅ On Pi | ✅ On Pi |
| Web interface | ⚠️ Slow | ✅ Fast |
| Door webhooks | ✅ On Pi | ✅ On server |
| Multiple cameras | ❌ No | ✅ Yes* |
| CPU usage (Pi) | ⚠️ High | ✅ Low |
| Network required | ✅ Local only | ⚠️ Pi↔Server |

\* Multiple camera support coming soon

---

## Performance Comparison

### Pi Zero W CPU Usage (Estimated)

**Single-Device:**
- Camera capture: ~20%
- Motion detection: ~15%
- Web server: ~20%
- Video encoding: ~15%
- **Total: ~70%**

**Client-Server:**
- Camera capture: ~20%
- Motion detection: ~15%
- Streaming to server: ~10%
- **Total: ~45%** (35% reduction!)

### Web Interface Response Time

**Single-Device:**
- Page load: ~2-3 seconds
- Video stream delay: ~1-2 seconds
- Status updates: ~500ms

**Client-Server:**
- Page load: ~0.5-1 second
- Video stream delay: ~0.5 second
- Status updates: ~100ms

---

## Migration Guide

### From Single-Device to Client-Server

1. **Keep your existing configs**:
   - `nextcloud_config.py` ✅ Keep
   - `pushover_config.py` ✅ Keep

2. **Create new config**:
   ```bash
   cp server_config_example.py server_config.py
   # Edit with your server's IP
   ```

3. **Set up server machine**:
   ```bash
   pip3 install flask
   python3 web_server.py
   ```

4. **Switch camera script**:
   ```bash
   # Instead of:
   python3 security_cam.py

   # Run:
   python3 camera_client.py
   ```

5. **Access web interface**:
   ```
   # Instead of: http://pi-ip:5000
   # Use: http://server-ip:5000
   ```

### From Client-Server to Single-Device

1. **Stop both services**:
   ```bash
   # Stop camera client and web server
   ```

2. **Run single-device script**:
   ```bash
   python3 security_cam.py
   ```

3. **Access directly**:
   ```
   http://pi-ip:5000
   ```

---

## Recommended Setup

### Home Use (1 camera)
- **Start with**: Single-Device
- **Upgrade to**: Client-Server if performance is an issue

### Multiple Cameras (Future)
- **Use**: Client-Server (required)

### Production/24/7 Operation
- **Use**: Client-Server
- **Server**: Run as systemd service
- **Camera**: Run as systemd service

---

## Quick Decision Guide

**Choose Single-Device if:**
- ✓ You only have the Pi Zero W
- ✓ You want simplest setup
- ✓ You're just testing
- ✓ Performance is acceptable

**Choose Client-Server if:**
- ✓ You have another computer/server
- ✓ You need better performance
- ✓ You want faster web interface
- ✓ You plan to add more cameras
- ✓ Pi Zero W is overloaded

---

## Configuration Files Summary

### Single-Device Needs:
```
security_cam.py
nextcloud_config.py (optional)
pushover_config.py (optional)
```

### Client-Server Needs:

**On Camera (Pi Zero W):**
```
camera_client.py
server_config.py (required!)
nextcloud_config.py (optional)
pushover_config.py (optional)
```

**On Server:**
```
web_server.py
```

---

## Both Architectures Support

- ✅ Motion detection
- ✅ Nextcloud image uploads
- ✅ Video recording to Nextcloud
- ✅ Pushover notifications
- ✅ Door sensor webhooks
- ✅ Live video streaming
- ✅ System monitoring

The main difference is WHERE the web interface runs and HOW the data flows.
