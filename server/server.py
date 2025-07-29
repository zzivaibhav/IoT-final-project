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
session_tracking = {}  # Track DISCOVER->ROSTER->COMMAND->ACK sessions

def get_message_type_name(msg_type):
    """Convert message type number to name"""
    type_map = {
        MSG_KEEPALIVE: "KEEPALIVE",
        MSG_DISCOVER: "DISCOVER", 
        MSG_COMMAND: "COMMAND",
        MSG_ACK: "ACK",
        ROSTER_MSG: "ROSTER"
    }
    return type_map.get(msg_type, f"UNKNOWN_{msg_type}")

def log_message(device_id, msg_type, rssi=None, snr=None, target_device_id=None, 
                success=True, spreading_factor=None, end_to_end_delay_ms=None, 
                session_id=None, payload_size=None):
    """Enhanced logging for experimental evaluation"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]  # Include milliseconds
    
    # Convert msg_type to string if it's a number
    if isinstance(msg_type, int):
        msg_type_str = get_message_type_name(msg_type)
    else:
        msg_type_str = msg_type
    
    entry = {
        'timestamp': timestamp,
        'message_type': msg_type_str,
        'source_device_id': device_id,
        'target_device_id': target_device_id or '',
        'success': success,
        'spreading_factor': spreading_factor or '',
        'rssi': rssi or '',
        'snr': snr or '',
        'end_to_end_delay_ms': end_to_end_delay_ms or '',
        'session_id': session_id or '',
        'payload_size_bytes': payload_size or '',
        'server_timestamp': datetime.now().timestamp()
    }
    
    data_log.append(entry)
    
    # Write to CSV
    csv_file = 'data/experimental_log.csv'
    os.makedirs('data', exist_ok=True)
    
    file_exists = os.path.isfile(csv_file)
    with open(csv_file, 'a', newline='') as f:
        fieldnames = ['timestamp', 'message_type', 'source_device_id', 'target_device_id', 
                     'success', 'spreading_factor', 'rssi', 'snr', 'end_to_end_delay_ms',
                     'session_id', 'payload_size_bytes', 'server_timestamp']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(entry)

def create_session_id(device_id):
    """Create unique session ID for tracking DISCOVER->ACK cycles"""
    return f"{device_id}_{int(datetime.now().timestamp() * 1000)}"

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

def send_downlink(client, device_id, payload, session_id=None):
    """Send downlink message to device"""
    topic = f"v3/{TTN_APP_ID}@ttn/devices/{device_id}/down/push"
    
    message = {
        "downlinks": [{
            "f_port": 1,
            "frm_payload": base64.b64encode(bytes(payload)).decode(),
            "priority": "NORMAL"
        }]
    }
    
    success = True
    try:
        client.publish(topic, json.dumps(message))
        print(f"Sent downlink to {device_id}: {payload}")
    except Exception as e:
        print(f"Failed to send downlink: {e}")
        success = False
    
    # Log the downlink
    msg_type = get_message_type_name(payload[0]) if payload else "UNKNOWN"
    log_message("SERVER", msg_type, target_device_id=device_id, 
                success=success, session_id=session_id, 
                payload_size=len(payload))

def process_uplink(client, device_id, payload, rssi, snr, spreading_factor=None):
    """Process received uplink message"""
    if not payload:
        return
        
    msg_type = payload[0]
    payload_size = len(payload)
    
    if msg_type == MSG_KEEPALIVE:
        print(f"KEEPALIVE from {device_id}")
        update_active_devices(device_id)
        log_message(device_id, msg_type, rssi, snr, 
                   spreading_factor=spreading_factor, payload_size=payload_size)
        
        # Check if device has pending commands
        if device_id in command_queue and command_queue[device_id]:
            command = command_queue[device_id].pop(0)
            send_downlink(client, device_id, command)
            print(f"Delivered queued command to {device_id}")
        
    elif msg_type == MSG_DISCOVER:
        print(f"DISCOVER from {device_id}")
        update_active_devices(device_id)
        
        # Create new session for tracking
        session_id = create_session_id(device_id)
        session_tracking[session_id] = {
            'start_time': datetime.now(),
            'source_device': device_id,
            'target_device': None
        }
        
        log_message(device_id, msg_type, rssi, snr,
                   spreading_factor=spreading_factor, session_id=session_id,
                   payload_size=payload_size)
        
        # Check if device has pending commands first
        if device_id in command_queue and command_queue[device_id]:
            command = command_queue[device_id].pop(0)
            send_downlink(client, device_id, command, session_id)
            print(f"Delivered queued command to {device_id}")
        else:
            # Send roster
            roster = get_roster()
            roster_devices = []
            for dev_id in roster:
                if dev_id != device_id:  # Exclude requesting device
                    if dev_id.startswith("eui-"):
                        hex_part = dev_id[4:]
                        last_bytes = hex_part[-4:]
                        roster_devices.append(int(last_bytes[:2], 16))
                        roster_devices.append(int(last_bytes[2:], 16))
            
            roster_payload = [ROSTER_MSG] + roster_devices
            send_downlink(client, device_id, roster_payload, session_id)
            
            # Log roster success based on number of devices found
            expected_devices = len([d for d in active_devices.keys() if d != device_id])
            found_devices = len(roster_devices) // 2
            roster_success = found_devices > 0 if expected_devices > 0 else True
            
            log_message("SERVER", ROSTER_MSG, target_device_id=device_id,
                       success=roster_success, session_id=session_id,
                       payload_size=len(roster_payload))
            
            print(f"Sent roster to {device_id}: {roster} -> payload: {roster_payload}")
        
    elif msg_type == MSG_COMMAND:
        print(f"COMMAND from {device_id}")
        update_active_devices(device_id)
        
        target_id = None
        if len(payload) >= 3:
            target_byte1 = payload[1]  
            target_byte2 = payload[2] if len(payload) > 2 else 0
            
            # Find matching device in active devices
            for dev_id in active_devices:
                if dev_id.startswith("eui-"):
                    hex_part = dev_id[4:]
                    last_bytes = hex_part[-4:]
                    if (int(last_bytes[:2], 16) == target_byte1 and 
                        int(last_bytes[2:], 16) == target_byte2):
                        target_id = dev_id
                        break
        
        # Find associated session
        session_id = None
        for sid, session in session_tracking.items():
            if session['source_device'] == device_id:
                session['target_device'] = target_id
                session_id = sid
                break
        
        command_success = target_id is not None
        log_message(device_id, msg_type, rssi, snr, target_device_id=target_id,
                   success=command_success, spreading_factor=spreading_factor,
                   session_id=session_id, payload_size=payload_size)
        
        # Check if device has pending commands first
        if device_id in command_queue and command_queue[device_id]:
            command = command_queue[device_id].pop(0)
            send_downlink(client, device_id, command)
            print(f"Delivered queued command to {device_id}")
        
        if target_id:
            command_data = payload[3:] if len(payload) > 3 else [0x42]
            
            # Queue command for target device
            if target_id not in command_queue:
                command_queue[target_id] = []
            
            command_queue[target_id].append([MSG_COMMAND] + command_data)
            print(f"Queued command for {target_id}")
        else:
            print(f"Target device not found for bytes: {payload[1]:02x}{payload[2]:02x}")
        
    elif msg_type == MSG_ACK:
        print(f"ACK from {device_id}")
        update_active_devices(device_id)
        
        # Calculate end-to-end delay if we can find the session
        end_to_end_delay = None
        session_id = None
        for sid, session in list(session_tracking.items()):
            if session.get('target_device') == device_id:
                delay_seconds = (datetime.now() - session['start_time']).total_seconds()
                end_to_end_delay = int(delay_seconds * 1000)  # Convert to milliseconds
                session_id = sid
                # Clean up completed session
                del session_tracking[sid]
                break
        
        log_message(device_id, msg_type, rssi, snr,
                   spreading_factor=spreading_factor, 
                   end_to_end_delay_ms=end_to_end_delay,
                   session_id=session_id, payload_size=payload_size)
        
        # Check if device has pending commands
        if device_id in command_queue and command_queue[device_id]:
            command = command_queue[device_id].pop(0)
            send_downlink(client, device_id, command)
            print(f"Delivered queued command to {device_id}")

def on_connect(client, userdata, flags, rc):
    """Callback for MQTT connection"""
    if rc == 0:
        print("Connected to TTN MQTT")
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
        uplink_msg = data.get('uplink_message', {})
        rx_metadata = uplink_msg.get('rx_metadata', [])
        rssi = rx_metadata[0].get('rssi') if rx_metadata else None
        snr = rx_metadata[0].get('snr') if rx_metadata else None
        
        # Extract spreading factor from settings
        settings = uplink_msg.get('settings', {})
        data_rate = settings.get('data_rate', {})
        spreading_factor = None
        if 'lora' in data_rate:
            spreading_factor = f"SF{data_rate['lora'].get('spreading_factor', '')}"
        
        # Decode payload
        frm_payload = uplink_msg.get('frm_payload')
        if frm_payload:
            payload = list(base64.b64decode(frm_payload))
            print(f"Received from {device_id}: {payload} (RSSI: {rssi}, SNR: {snr}, SF: {spreading_factor})")
            process_uplink(client, device_id, payload, rssi, snr, spreading_factor)
        
    except Exception as e:
        print(f"Error processing message: {e}")

def main():
    """Main function"""
    print("Starting LoRaWAN P2P Messaging Server")
    print("Enhanced logging for experimental evaluation enabled")
    
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