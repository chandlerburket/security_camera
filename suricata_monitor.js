/**
 * Suricata Network Monitoring Module
 * Monitors Suricata eve.json logs for security alerts and network events
 */

const fs = require('fs');
const { spawn } = require('child_process');
const readline = require('readline');

class SuricataMonitor {
    constructor(config) {
        this.eveLogPath = config.eveLogPath || '/var/log/suricata/eve.json';
        this.maxAlerts = config.maxAlerts || 100; // Maximum alerts to keep in memory
        this.maxEvents = config.maxEvents || 50;   // Maximum non-alert events to keep

        this.alerts = [];           // Recent security alerts
        this.events = [];           // Recent non-alert events (anomaly, dns, http, etc.)
        this.stats = {
            totalAlerts: 0,
            totalEvents: 0,
            alertsBySeverity: { 1: 0, 2: 0, 3: 0 }, // 1=High, 2=Medium, 3=Low
            alertsByCategory: {},
            lastUpdate: null,
            monitoringActive: false
        };

        this.tailProcess = null;
        this.eventEmitter = null;
    }

    /**
     * Start monitoring Suricata eve.json file
     * @param {EventEmitter} eventEmitter - Optional event emitter for real-time alerts
     */
    start(eventEmitter = null) {
        this.eventEmitter = eventEmitter;

        // Check if eve.json exists
        if (!fs.existsSync(this.eveLogPath)) {
            console.error(`❌ Suricata eve.json not found at: ${this.eveLogPath}`);
            console.error('   Make sure Suricata is installed and running');
            this.stats.monitoringActive = false;
            return false;
        }

        console.log(`🔍 Starting Suricata monitoring: ${this.eveLogPath}`);

        // Use tail -f to follow the log file
        this.tailProcess = spawn('tail', ['-f', '-n', '100', this.eveLogPath]);

        const rl = readline.createInterface({
            input: this.tailProcess.stdout,
            crlfDelay: Infinity
        });

        rl.on('line', (line) => {
            this.processLogLine(line);
        });

        this.tailProcess.stderr.on('data', (data) => {
            console.error(`Suricata monitor error: ${data}`);
        });

        this.tailProcess.on('close', (code) => {
            console.log(`Suricata monitor stopped (exit code: ${code})`);
            this.stats.monitoringActive = false;
        });

        this.stats.monitoringActive = true;
        this.stats.lastUpdate = new Date().toISOString();

        console.log('✅ Suricata monitoring started');
        return true;
    }

    /**
     * Process a single line from eve.json
     */
    processLogLine(line) {
        if (!line || line.trim() === '') return;

        try {
            const event = JSON.parse(line);

            // Update last update time
            this.stats.lastUpdate = event.timestamp || new Date().toISOString();

            // Handle different event types
            if (event.event_type === 'alert') {
                this.processAlert(event);
            } else {
                this.processEvent(event);
            }
        } catch (err) {
            // Silently ignore parse errors (incomplete lines, corrupted data)
            // Uncomment for debugging: console.error('Failed to parse Suricata log line:', err.message);
        }
    }

    /**
     * Process an alert event
     */
    processAlert(event) {
        const alert = {
            timestamp: event.timestamp,
            severity: event.alert?.severity || 3,
            category: event.alert?.category || 'Unknown',
            signature: event.alert?.signature || 'Unknown Alert',
            signature_id: event.alert?.signature_id,
            src_ip: event.src_ip,
            src_port: event.src_port,
            dest_ip: event.dest_ip,
            dest_port: event.dest_port,
            proto: event.proto,
            app_proto: event.app_proto,
            metadata: event.alert?.metadata || null,
            payload: event.payload_printable || null
        };

        // Add to alerts array (keep most recent)
        this.alerts.unshift(alert);
        if (this.alerts.length > this.maxAlerts) {
            this.alerts.pop();
        }

        // Update statistics
        this.stats.totalAlerts++;
        this.stats.alertsBySeverity[alert.severity] =
            (this.stats.alertsBySeverity[alert.severity] || 0) + 1;
        this.stats.alertsByCategory[alert.category] =
            (this.stats.alertsByCategory[alert.category] || 0) + 1;

        // Emit real-time alert event if event emitter is configured
        if (this.eventEmitter) {
            this.eventEmitter.emit('suricata-alert', alert);
        }

        // Log high-severity alerts
        if (alert.severity === 1) {
            console.log(`🚨 HIGH SEVERITY ALERT: ${alert.signature} (${alert.src_ip} → ${alert.dest_ip})`);
        }
    }

    /**
     * Process non-alert events (anomaly, http, dns, etc.)
     */
    processEvent(event) {
        const eventData = {
            timestamp: event.timestamp,
            event_type: event.event_type,
            src_ip: event.src_ip,
            dest_ip: event.dest_ip,
            proto: event.proto,
            app_proto: event.app_proto
        };

        // Add event-type specific data
        if (event.event_type === 'http' && event.http) {
            eventData.http = {
                hostname: event.http.hostname,
                url: event.http.url,
                http_method: event.http.http_method,
                status: event.http.status
            };
        } else if (event.event_type === 'dns' && event.dns) {
            eventData.dns = {
                query: event.dns.rrname,
                type: event.dns.rrtype,
                rcode: event.dns.rcode
            };
        } else if (event.event_type === 'anomaly' && event.anomaly) {
            eventData.anomaly = {
                type: event.anomaly.type,
                event: event.anomaly.event
            };
        }

        // Add to events array (keep most recent)
        this.events.unshift(eventData);
        if (this.events.length > this.maxEvents) {
            this.events.pop();
        }

        this.stats.totalEvents++;
    }

    /**
     * Get recent alerts with optional filtering
     */
    getAlerts(options = {}) {
        const { limit = 20, severity = null, category = null, since = null } = options;

        let filtered = this.alerts;

        // Filter by severity
        if (severity !== null) {
            filtered = filtered.filter(a => a.severity === severity);
        }

        // Filter by category
        if (category) {
            filtered = filtered.filter(a => a.category === category);
        }

        // Filter by time
        if (since) {
            const sinceDate = new Date(since);
            filtered = filtered.filter(a => new Date(a.timestamp) >= sinceDate);
        }

        return filtered.slice(0, limit);
    }

    /**
     * Get recent non-alert events
     */
    getEvents(options = {}) {
        const { limit = 20, event_type = null } = options;

        let filtered = this.events;

        if (event_type) {
            filtered = filtered.filter(e => e.event_type === event_type);
        }

        return filtered.slice(0, limit);
    }

    /**
     * Get statistics
     */
    getStats() {
        return {
            ...this.stats,
            recentAlerts: this.alerts.length,
            recentEvents: this.events.length
        };
    }

    /**
     * Get alert summary for dashboard
     */
    getSummary() {
        const now = Date.now();
        const oneHourAgo = now - (60 * 60 * 1000);
        const last24HoursAgo = now - (24 * 60 * 60 * 1000);

        const recentAlerts = this.alerts.filter(a =>
            new Date(a.timestamp).getTime() >= oneHourAgo
        );

        const last24HourAlerts = this.alerts.filter(a =>
            new Date(a.timestamp).getTime() >= last24HoursAgo
        );

        const highSeverityAlerts = this.alerts.filter(a => a.severity === 1);

        return {
            monitoring_active: this.stats.monitoringActive,
            last_update: this.stats.lastUpdate,
            alerts_last_hour: recentAlerts.length,
            alerts_last_24h: last24HourAlerts.length,
            high_severity_alerts: highSeverityAlerts.length,
            total_alerts: this.stats.totalAlerts,
            top_categories: this.getTopCategories(5),
            latest_alert: this.alerts[0] || null
        };
    }

    /**
     * Get top alert categories
     */
    getTopCategories(limit = 5) {
        const sorted = Object.entries(this.stats.alertsByCategory)
            .sort((a, b) => b[1] - a[1])
            .slice(0, limit);

        return sorted.map(([category, count]) => ({ category, count }));
    }

    /**
     * Stop monitoring
     */
    stop() {
        if (this.tailProcess) {
            this.tailProcess.kill();
            this.tailProcess = null;
            console.log('🛑 Suricata monitoring stopped');
        }
        this.stats.monitoringActive = false;
    }

    /**
     * Clear stored alerts and events
     */
    clear() {
        this.alerts = [];
        this.events = [];
        this.stats = {
            totalAlerts: 0,
            totalEvents: 0,
            alertsBySeverity: { 1: 0, 2: 0, 3: 0 },
            alertsByCategory: {},
            lastUpdate: null,
            monitoringActive: this.stats.monitoringActive
        };
        console.log('🧹 Cleared Suricata monitoring data');
    }
}

module.exports = SuricataMonitor;
