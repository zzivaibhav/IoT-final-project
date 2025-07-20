#!/usr/bin/env python3
"""
Simplified LoRaWAN Server for Project P2
Handles only DISCOVER -> ROSTER functionality
"""

import paho.mqtt.client as mqtt
import json
import time
import base64
from datetime import datetime
import csv
import os
import ssl

# Configuration
TTN_MQTT_SERVER = "nam1.cloud.thethings.network"
TTN_MQTT_PORT = 8883
TTN_USERNAME = "test-dal@ttn"
TTN_PASSWORD = "NNSXS.HATGGJ2NG5AZYYF4QKEYBCPSI3FLKK7GFFDUCVI.6Z373ADOU6RED6V3Y47CFRYM347RBSCN2ETWW4WIHUUGEFWOTRHQ"
TTN_APP_ID = "test-dal"

# Simple device tracking
active_devices = {}
DEVICE_TIMEOUT = 300  # 5 minutes

# Add fake devices for single-device testing
def add_test_devices():
    """Add fake devices to simulate a multi-device environment"""
    current_time = time.time()
    # Add some fake active devices for testing
    active_devices["eui-test-device-001"] = current_time - 30   # 30 seconds ago
    active_devices["eui-test-device-002"] = current_time - 60   # 1 minute ago  
    active_devices["eui-test-device-003"] = current_time - 90   # 1.5 minutes ago
    print("🧪 Added 3 test devices for single-device testing")

# Initialize test devices
add_test_devices()

# Simple data logging
def log_event(device_id, event_type, details=""):
    timestamp = datetime.now().isoformat()
    filename = "data/simple_log.csv"
    
    # Create directory if it doesn't exist
    os.makedirs("data", exist_ok=True)
    
    # Create file with header if it doesn't exist
    if not os.path.exists(filename):
        with open(filename, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp', 'device_id', 'event_type', 'details'])
    
    # Log the event
    with open(filename, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([timestamp, device_id, event_type, details])

def get_active_devices():
    """Get list of devices active within timeout period"""
    current_time = time.time()
    active = []
    
    # Remove expired devices and build active list
    expired = []
    for device_id, last_seen in active_devices.items():
        if current_time - last_seen < DEVICE_TIMEOUT:
            active.append(device_id)
        else:
            expired.append(device_id)
    
    # Clean up expired devices
    for device_id in expired:
        del active_devices[device_id]
    
    return active

def send_roster(device_id):
    """Send ROSTER downlink immediately (Class A compatibility)"""
    active_devs = get_active_devices()
    # Exclude the requesting device from the roster
    roster_devices = [dev for dev in active_devs if dev != device_id]
    
    roster_message = {
        "type": "ROSTER", 
        "devices": roster_devices[:5]  # Limit to 5 to stay under 51 bytes
    }
    
    try:
        # Convert to base64 for TTN
        payload = json.dumps(roster_message)
        payload_b64 = base64.b64encode(payload.encode()).decode()
        
        # Check size limit (LoRaWAN SF7 = ~51 bytes max)
        if len(base64.b64decode(payload_b64)) > 51:
            # Further truncate if needed
            roster_message["devices"] = roster_devices[:3]
            payload = json.dumps(roster_message)
            payload_b64 = base64.b64encode(payload.encode()).decode()
        
        downlink = {
            "downlinks": [{
                "f_port": 1,
                "frm_payload": payload_b64,
                "priority": "NORMAL"
            }]
        }
        
        # Send downlink via MQTT
        topic = f"v3/{TTN_APP_ID}/devices/{device_id}/down/push"
        mqtt_client.publish(topic, json.dumps(downlink))
        
        print(f"✓ Sent ROSTER to {device_id}: {len(roster_message['devices'])} devices")
        log_event(device_id, "ROSTER_SENT", f"devices={len(roster_message['devices'])}")
        
    except Exception as e:
        print(f"✗ Failed to send ROSTER to {device_id}: {e}")
        log_event(device_id, "ROSTER_FAILED", str(e))

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print("✓ Connected to TTN MQTT broker")
        topic = f"v3/{TTN_USERNAME}/devices/+/up"
        client.subscribe(topic)
        print(f"✓ Subscribed to: {topic}")
    else:
        print(f"✗ Failed to connect: {rc}")

def on_message(client, userdata, msg):
    try:
        # Parse TTN message
        ttn_message = json.loads(msg.payload.decode())
        
        if 'end_device_ids' not in ttn_message:
            return
            
        device_id = ttn_message['end_device_ids']['device_id']
        current_time = time.time()
        
        # Always update device as active
        active_devices[device_id] = current_time
        
        # Decode payload
        if 'uplink_message' in ttn_message and 'frm_payload' in ttn_message['uplink_message']:
            payload_b64 = ttn_message['uplink_message']['frm_payload']
            payload_bytes = base64.b64decode(payload_b64)
            payload_str = payload_bytes.decode('utf-8')
            
            try:
                app_message = json.loads(payload_str)
                message_type = app_message.get('type')
                
                print(f"[{datetime.now().strftime('%H:%M:%S')}] {device_id}: {message_type}")
                
                if message_type == "KEEPALIVE":
                    log_event(device_id, "KEEPALIVE")
                    
                elif message_type == "DISCOVER":
                    log_event(device_id, "DISCOVER")
                    # Send ROSTER immediately for Class A compatibility
                    send_roster(device_id)
                    
            except json.JSONDecodeError:
                print(f"✗ Invalid JSON from {device_id}")
                
    except Exception as e:
        print(f"✗ Error processing message: {e}")

def print_status():
    """Print current system status"""
    active_devs = get_active_devices()
    print(f"\n📊 Status: {len(active_devs)} active devices")
    for dev in active_devs:
        last_seen = time.time() - active_devices[dev]
        test_indicator = "🧪" if "test-device" in dev else "📱"
        print(f"  {test_indicator} {dev} (last seen {last_seen:.0f}s ago)")
    print()

def refresh_test_devices():
    """Keep test devices active by refreshing their timestamps"""
    current_time = time.time()
    test_devices = ["eui-test-device-001", "eui-test-device-002", "eui-test-device-003"]
    for device in test_devices:
        if device in active_devices:
            # Refresh with slight variation to make them look realistic
            active_devices[device] = current_time - (30 + (hash(device) % 60))

def main():
    global mqtt_client
    
    print("🚀 Starting Simplified LoRaWAN Server for Project P2")
    print("🧪 Test devices enabled for single-device demonstration")
    print("📁 Data will be logged to: data/simple_log.csv")
    
    # Setup MQTT client
    mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    mqtt_client.username_pw_set(TTN_USERNAME, TTN_PASSWORD)
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    
    # TLS for TTN
    mqtt_client.tls_set(cert_reqs=ssl.CERT_NONE)
    mqtt_client.tls_insecure_set(True)
    
    # Connect and run
    try:
        mqtt_client.connect(TTN_MQTT_SERVER, TTN_MQTT_PORT, 60)
        print("🔄 Starting MQTT loop...")
        print("📝 Device activity:")
        print("   - Type 'D' in your Arduino to send DISCOVER")
        print("   - Press Ctrl+C to stop")
        
        # Run forever
        last_status = time.time()
        last_refresh = time.time()
        while True:
            mqtt_client.loop(timeout=1)
            
            # Refresh test devices every 60 seconds to keep them active
            if time.time() - last_refresh > 60:
                refresh_test_devices()
                last_refresh = time.time()
            
            # Print status every 30 seconds
            if time.time() - last_status > 30:
                print_status()
                last_status = time.time()
                
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
        mqtt_client.disconnect()

if __name__ == "__main__":
    main()
