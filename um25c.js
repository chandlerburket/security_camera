/**
 * um25c.js — UM25C Bluetooth power meter integration
 *
 * Drop this file next to server.js, then add to server.js:
 *
 *   const { startPowerMonitor } = require('./um25c');
 *   startPowerMonitor(io);   // pass your Socket.io server instance
 *
 * The device must already be bound on the host:
 *   sudo rfcomm bind 0 <UM25C_MAC>
 *
 * Emits socket event 'power-status' with shape:
 *   { online: true, voltage, current, power, mah, mwh, temp_c, ts }
 *   { online: false, ts }
 */

'use strict';

const { SerialPort } = require('serialport');

const SERIAL_PORT    = process.env.UM25C_PORT    || '/dev/rfcomm0';
const POLL_INTERVAL  = parseInt(process.env.UM25C_POLL_MS || '5000', 10);
const BAUD_RATE      = 9600;
const PACKET_LEN     = 130;

// ── Parser ────────────────────────────────────────────────────────────────────

/**
 * Parse the 130-byte UM25C response packet.
 * Protocol: https://sigrok.org/wiki/RDTech_UM_series
 * Returns null on bad data.
 */
function parsePacket(buf) {
  if (!Buffer.isBuffer(buf) || buf.length < PACKET_LEN) return null;

  try {
    const voltage  = buf.readUInt16BE(2)  / 1000;   // mV → V
    const current  = buf.readUInt16BE(4)  / 10000;  // 0.1mA → A
    const power    = buf.readUInt32BE(6)  / 1000;   // mW → W
    const mah      = buf.readUInt32BE(102);          // mAh (data group 0)
    const mwh      = buf.readUInt32BE(106);          // mWh (data group 0)
    const temp_c   = buf.readUInt16BE(10);           // °C

    // Sanity check — a Pi Zero should pull 4.8–5.2 V, 0–1 A
    if (voltage < 3.0 || voltage > 6.5) return null;

    return {
      voltage:  +voltage.toFixed(3),
      current:  +current.toFixed(4),
      power:    +power.toFixed(3),
      mah,
      mwh,
      temp_c,
    };
  } catch {
    return null;
  }
}

// ── Poller ────────────────────────────────────────────────────────────────────

function broadcast(io, payload) {
  io.emit('power-status', { ...payload, ts: new Date().toISOString() });
}

function startPowerMonitor(io) {
  let port        = null;
  let rxBuf       = Buffer.alloc(0);
  let pollTimer   = null;
  let reconnTimer = null;

  function cleanup() {
    if (pollTimer)   { clearInterval(pollTimer);  pollTimer   = null; }
    if (reconnTimer) { clearTimeout(reconnTimer); reconnTimer = null; }
    if (port && port.isOpen) {
      port.close(() => {});
    }
    port = null;
    rxBuf = Buffer.alloc(0);
  }

  function scheduleReconnect(delayMs = 10000) {
    cleanup();
    broadcast(io, { online: false });
    console.log(`[um25c] Reconnecting in ${delayMs / 1000}s…`);
    reconnTimer = setTimeout(connect, delayMs);
  }

  function sendRequest() {
    if (!port || !port.isOpen) return;
    // UM25C request byte: 0xF0 triggers a full packet response
    port.write(Buffer.from([0xf0]), (err) => {
      if (err) {
        console.error('[um25c] Write error:', err.message);
        scheduleReconnect();
      }
    });
  }

  function connect() {
    console.log(`[um25c] Opening ${SERIAL_PORT} @ ${BAUD_RATE} baud`);

    port = new SerialPort({
      path:     SERIAL_PORT,
      baudRate: BAUD_RATE,
      autoOpen: false,
    });

    port.on('error', (err) => {
      console.error('[um25c] Port error:', err.message);
      scheduleReconnect();
    });

    port.on('close', () => {
      console.warn('[um25c] Port closed');
      scheduleReconnect();
    });

    port.on('data', (chunk) => {
      rxBuf = Buffer.concat([rxBuf, chunk]);

      // Consume complete packets
      while (rxBuf.length >= PACKET_LEN) {
        const packet = rxBuf.slice(0, PACKET_LEN);
        rxBuf        = rxBuf.slice(PACKET_LEN);

        const parsed = parsePacket(packet);
        if (parsed) {
          broadcast(io, { online: true, ...parsed });
          console.debug(
            `[um25c] ${parsed.voltage}V  ${parsed.current}A  ${parsed.power}W  ${parsed.mah}mAh  ${parsed.temp_c}°C`
          );
        } else {
          console.warn('[um25c] Unparseable packet, flushing');
          rxBuf = Buffer.alloc(0);
        }
      }
    });

    port.open((err) => {
      if (err) {
        console.error('[um25c] Cannot open port:', err.message);
        scheduleReconnect(10000);
        return;
      }

      console.log('[um25c] Connected — polling every', POLL_INTERVAL, 'ms');

      // Poll immediately, then on interval
      sendRequest();
      pollTimer = setInterval(sendRequest, POLL_INTERVAL);
    });
  }

  // Kick off
  connect();

  // Expose a graceful shutdown hook
  return { stop: cleanup };
}

module.exports = { startPowerMonitor };
