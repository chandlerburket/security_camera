/**
 * Server Integrations Configuration
 * Copy this file and rename to server_integrations_config.local.js
 * Update with your actual credentials
 */

module.exports = {
    // Nextcloud Configuration
    nextcloud: {
        enabled: false,  // Set to true to enable Nextcloud uploads
        url: "http://192.168.1.100",  // Your Nextcloud server URL
        username: "camera_user",  // Nextcloud username
        password: "your_password",  // Nextcloud password
        motionFolder: "/motion_captures",  // Folder for motion detection images
        videoFolder: "/recordings",  // Folder for video recordings
        saveInterval: 10  // Minimum seconds between saving motion images
    },

    // Pushover Configuration
    pushover: {
        enabled: false,  // Set to true to enable Pushover notifications
        userKey: "your_pushover_user_key",  // Your Pushover user key
        apiToken: "your_pushover_api_token",  // Your Pushover API token
        notifyInterval: 120,  // Minimum seconds between notifications
        priority: 0,  // -2 to 2 (lowest to emergency)
        sound: "pushover"  // Notification sound
    },

    // Suricata Network Monitoring Configuration
    suricata: {
        enabled: true,  // Set to true to enable Suricata monitoring
        eveLogPath: "/var/log/suricata/eve.json",  // Path to Suricata eve.json log file
        maxAlerts: 100,  // Maximum number of alerts to keep in memory
        maxEvents: 50,  // Maximum number of non-alert events to keep
        alertNotifications: false,  // Set to true to send Pushover notifications for high-severity alerts
        notifyOnSeverity: 1  // Only notify for alerts with this severity or higher (1=High, 2=Medium, 3=Low)
    }
};
