import paho.mqtt.client as mqtt
import json
import time
import base64
from datetime import datetime, timedelta
import csv
import os

# Configuration
TTN_MQTT_SERVER = "nam1.cloud.thethings.network"
TTN_MQTT_PORT = 8883
TTN_USERNAME = "test-dal@ttn" 
TTN_PASSWORD = "NNSXS.HATGGJ2NG5AZYYF4QKEYBCPSI3FLKK7GFFDUCVI.6Z373ADOU6RED6V3Y47CFRYM347RBSCN2ETWW4WIHUUGEFWOTRHQ"     
TTN_APP_ID = "test-dal"       

# Message types
MSG_KEEPALIVE = 0x01
MSG_DISCOVER = 0x02
MSG_COMMAND = 0x03
MSG_ACK = 0x04
ROSTER_MSG = 0x80

# Global variables
active_devices = {}  # {device_id: last_seen_timestamp}
command_queue = {}   # {device_id: [commands]}
data_log = []

def log_message(device_id, msg_type, rssi=None, snr=None, data=None):
    """Log message to CSV for analysis"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = {
        'timestamp': timestamp,
        'device_id': device_id,
        'message_type': msg_type,
        'rssi': rssi,
        'snr': snr,
        'data': data
    }
    data_log.append(entry)
    
    # Write to CSV
    csv_file = 'data/message_log.csv'
    os.makedirs('data', exist_ok=True)
    
    file_exists = os.path.isfile(csv_file)
    with open(csv_file, 'a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['timestamp', 'device_id', 'message_type', 'rssi', 'snr', 'data'])
        if not file_exists:
            writer.writeheader()
        writer.writerow(entry)

def update_active_devices(device_id):
    """Update device as active"""
    active_devices[device_id] = datetime.now()
    print(f"Device {device_id} marked as active")

def get_roster():
    """Get list of active devices (seen in last 5 minutes)"""
    cutoff_time = datetime.now() - timedelta(minutes=5)
    active = []
    
    for device_id, last_seen in list(active_devices.items()):
        if last_seen > cutoff_time:
            active.append(device_id)
        else:
            # Remove inactive devices
            del active_devices[device_id]
    
    return active

def send_downlink(client, device_id, payload):
    """Send downlink message to device"""
    topic = f"v3/{TTN_APP_ID}@ttn/devices/{device_id}/down/push"
    
    message = {
        "downlinks": [{
            "f_port": 1,
            "frm_payload": base64.b64encode(bytes(payload)).decode(),
            "priority": "NORMAL"
        }]
    }
    
    client.publish(topic, json.dumps(message))
    print(f"Sent downlink to {device_id}: {payload}")

def process_uplink(client, device_id, payload, rssi, snr):
    """Process received uplink message"""
    if not payload:
        return
        
    msg_type = payload[0]
    
    if msg_type == MSG_KEEPALIVE:
        print(f"KEEPALIVE from {device_id}")
        update_active_devices(device_id)
        log_message(device_id, "KEEPALIVE", rssi, snr)
        
        # Check if device has pending commands
        if device_id in command_queue and command_queue[device_id]:
            command = command_queue[device_id].pop(0)
            send_downlink(client, device_id, command)
            print(f"Delivered queued command to {device_id}")
        
    elif msg_type == MSG_DISCOVER:
        print(f"DISCOVER from {device_id}")
        update_active_devices(device_id)
        log_message(device_id, "DISCOVER", rssi, snr)
        
        # Check if device has pending commands
        if device_id in command_queue and command_queue[device_id]:
            command = command_queue[device_id].pop(0)
            send_downlink(client, device_id, command)
            print(f"Delivered queued command to {device_id}")
        else:
            # Send roster
            roster = get_roster()
            # Extract device ID suffix for roster (last 2 bytes of DevEUI)
            roster_devices = []
            for dev_id in roster:
                if dev_id != device_id:  # Exclude requesting device
                    # Extract last 2 bytes from device ID like "eui-617dd6c4ee40e566"
                    if dev_id.startswith("eui-"):
                        hex_part = dev_id[4:]  # Remove "eui-" prefix
                        # Take last 2 bytes (4 hex chars) and convert to bytes
                        last_bytes = hex_part[-4:]
                        roster_devices.append(int(last_bytes[:2], 16))  # First byte
                        roster_devices.append(int(last_bytes[2:], 16))  # Second byte
            
            roster_payload = [ROSTER_MSG] + roster_devices
            send_downlink(client, device_id, roster_payload)
            
            print(f"Sent roster to {device_id}: {roster} -> payload: {roster_payload}")
        
    elif msg_type == MSG_COMMAND:
        print(f"COMMAND from {device_id}")
        update_active_devices(device_id)
        
        # Check if device has pending commands first
        if device_id in command_queue and command_queue[device_id]:
            command = command_queue[device_id].pop(0)
            send_downlink(client, device_id, command)
            print(f"Delivered queued command to {device_id}")
        
        if len(payload) >= 3:
            # Reconstruct target device ID from received bytes
            target_byte1 = payload[1]
            target_byte2 = payload[2] if len(payload) > 2 else 0
            
            # Find matching device in active devices
            target_id = None
            for dev_id in active_devices:
                if dev_id.startswith("eui-"):
                    hex_part = dev_id[4:]
                    last_bytes = hex_part[-4:]
                    if (int(last_bytes[:2], 16) == target_byte1 and 
                        int(last_bytes[2:], 16) == target_byte2):
                        target_id = dev_id
                        break
            
            if target_id:
                command_data = payload[3:] if len(payload) > 3 else [0x42]
                log_message(device_id, "COMMAND", rssi, snr, f"target:{target_id}")
                
                # Queue command for target device
                if target_id not in command_queue:
                    command_queue[target_id] = []
                
                command_queue[target_id].append([MSG_COMMAND] + command_data)
                print(f"Queued command for {target_id}")
            else:
                print(f"Target device not found for bytes: {target_byte1:02x}{target_byte2:02x}")
        
    elif msg_type == MSG_ACK:
        print(f"ACK from {device_id}")
        update_active_devices(device_id)
        log_message(device_id, "ACK", rssi, snr)
        
        # Check if device has pending commands
        if device_id in command_queue and command_queue[device_id]:
            command = command_queue[device_id].pop(0)
            send_downlink(client, device_id, command)
            print(f"Delivered queued command to {device_id}")

def on_connect(client, userdata, flags, rc):
    """Callback for MQTT connection"""
    if rc == 0:
        print("Connected to TTN MQTT")
        # Subscribe to uplink messages
        topic = f"v3/{TTN_APP_ID}@ttn/devices/+/up"
        client.subscribe(topic)
        print(f"Subscribed to {topic}")
    else:
        print(f"Failed to connect to TTN MQTT: {rc}")

def on_message(client, userdata, msg):
    """Callback for received MQTT messages"""
    try:
        data = json.loads(msg.payload.decode())
        
        device_id = data.get('end_device_ids', {}).get('device_id')
        if not device_id:
            return
            
        # Extract metadata
        rx_metadata = data.get('uplink_message', {}).get('rx_metadata', [])
        rssi = rx_metadata[0].get('rssi') if rx_metadata else None
        snr = rx_metadata[0].get('snr') if rx_metadata else None
        
        # Decode payload
        frm_payload = data.get('uplink_message', {}).get('frm_payload')
        if frm_payload:
            payload = list(base64.b64decode(frm_payload))
            print(f"Received from {device_id}: {payload} (RSSI: {rssi}, SNR: {snr})")
            process_uplink(client, device_id, payload, rssi, snr)
        
    except Exception as e:
        print(f"Error processing message: {e}")

def main():
    """Main function"""
    print("Starting LoRaWAN P2P Messaging Server")
    
    # Setup MQTT client
    client = mqtt.Client()
    client.username_pw_set(TTN_USERNAME, TTN_PASSWORD)
    client.tls_set(cert_reqs=mqtt.ssl.CERT_NONE)
    client.tls_insecure_set(True)
    client.on_connect = on_connect
    client.on_message = on_message
    
    # Connect to TTN
    try:
        client.connect(TTN_MQTT_SERVER, TTN_MQTT_PORT, 60)
        print("Starting MQTT loop...")
        client.loop_forever()
    except Exception as e:
        print(f"Error connecting to TTN: {e}")

if __name__ == "__main__":
    main()