import paho.mqtt.client as mqtt
import json
import time
import threading
import base64
from datetime import datetime, timedelta
import queue
import logging
import csv
import os

# Configuration
TTN_MQTT_SERVER = "nam1.cloud.thethings.network"
TTN_MQTT_PORT = 8883
TTN_USERNAME = "test-dal@ttn"  # Replace with your TTN app ID
TTN_PASSWORD = "NNSXS.HATGGJ2NG5AZYYF4QKEYBCPSI3FLKK7GFFDUCVI.6Z373ADOU6RED6V3Y47CFRYM347RBSCN2ETWW4WIHUUGEFWOTRHQ"     # Replace with your TTN API key
TTN_APP_ID = "test-dal"        # Replace with your TTN app ID

# Device management
class DeviceManager:
    def __init__(self):
        self.active_devices = {}
        self.device_timeout = 300  # 5 minutes timeout
        self.message_buffer = {}
        self.discover_times = {}  # Track DISCOVER request times
        self.command_times = {}   # Track COMMAND send times
        self.lock = threading.Lock()
    
    def update_device(self, device_id, timestamp):
        with self.lock:
            self.active_devices[device_id] = timestamp
    
    def record_discover_time(self, device_id):
        with self.lock:
            self.discover_times[device_id] = time.time()
    
    def get_discover_delay(self, device_id):
        with self.lock:
            if device_id in self.discover_times:
                delay = (time.time() - self.discover_times[device_id]) * 1000  # Convert to ms
                del self.discover_times[device_id]  # Clean up
                return delay
            return None
    
    def record_command_time(self, sender_id, target_id, message):
        with self.lock:
            key = f"{sender_id}->{target_id}"
            self.command_times[key] = {
                'time': time.time(),
                'message': message,
                'sender': sender_id,
                'target': target_id
            }
    
    def get_command_delay(self, sender_id, target_id):
        with self.lock:
            key = f"{sender_id}->{target_id}"
            if key in self.command_times:
                delay = (time.time() - self.command_times[key]['time']) * 1000  # Convert to ms
                cmd_info = self.command_times[key]
                del self.command_times[key]  # Clean up
                return delay, cmd_info
            return None, None
    
    def update_device(self, device_id, timestamp):
        with self.lock:
            self.active_devices[device_id] = timestamp
    
    def get_active_devices(self):
        with self.lock:
            current_time = time.time()
            active = []
            expired_devices = []
            for device_id, last_seen in self.active_devices.items():
                if current_time - last_seen < self.device_timeout:
                    active.append(device_id)
                else:
                    expired_devices.append(device_id)
            
            # Remove expired devices
            for device_id in expired_devices:
                del self.active_devices[device_id]
                
            return active
    
    def buffer_message(self, target_id, message):
        with self.lock:
            if target_id not in self.message_buffer:
                self.message_buffer[target_id] = queue.Queue()
            self.message_buffer[target_id].put(message)
    
    def get_buffered_message(self, device_id):
        with self.lock:
            if device_id in self.message_buffer and not self.message_buffer[device_id].empty():
                return self.message_buffer[device_id].get()
            return None

# Global device manager
device_manager = DeviceManager()

# Data logging for analysis
class DataLogger:
    def __init__(self):
        self.log_dir = "data"
        os.makedirs(self.log_dir, exist_ok=True)
        self.lock = threading.Lock()
        
        # Initialize CSV files
        self.init_csv_files()
    
    def init_csv_files(self):
        # Message logs
        self.message_log_file = os.path.join(self.log_dir, "message_log.csv")
        if not os.path.exists(self.message_log_file):
            with open(self.message_log_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['timestamp', 'device_id', 'message_type', 'target_id', 
                               'payload_size', 'rssi', 'snr', 'spreading_factor', 'success'])
        
        # Roster performance logs
        self.roster_log_file = os.path.join(self.log_dir, "roster_performance.csv")
        if not os.path.exists(self.roster_log_file):
            with open(self.roster_log_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['timestamp', 'device_id', 'devices_discovered', 'devices_expected', 
                               'discovery_accuracy', 'response_delay_ms'])
        
        # Command delivery logs
        self.delivery_log_file = os.path.join(self.log_dir, "command_delivery.csv")
        if not os.path.exists(self.delivery_log_file):
            with open(self.delivery_log_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['timestamp', 'sender_id', 'target_id', 'message', 
                               'buffered_time', 'delivery_delay_ms', 'delivered', 'ack_received'])
    
    def log_message(self, device_id, message_type, ttn_message, target_id=None, success=True):
        with self.lock:
            timestamp = datetime.now().isoformat()
            
            # Extract metadata from TTN message
            payload_size = 0
            rssi = None
            snr = None
            spreading_factor = None
            
            if 'uplink_message' in ttn_message:
                uplink = ttn_message['uplink_message']
                if 'frm_payload' in uplink:
                    payload_size = len(base64.b64decode(uplink['frm_payload']))
                
                if 'rx_metadata' in uplink and uplink['rx_metadata']:
                    metadata = uplink['rx_metadata'][0]  # Use first gateway
                    rssi = metadata.get('rssi')
                    snr = metadata.get('snr')
                
                if 'settings' in uplink and 'data_rate' in uplink['settings']:
                    dr = uplink['settings']['data_rate']
                    if 'lora' in dr:
                        spreading_factor = dr['lora'].get('spreading_factor')
            
            with open(self.message_log_file, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([timestamp, device_id, message_type, target_id or '', 
                               payload_size, rssi or '', snr or '', spreading_factor or '', success])
    
    def log_roster_performance(self, device_id, devices_discovered, devices_expected, response_delay_ms):
        with self.lock:
            timestamp = datetime.now().isoformat()
            accuracy = devices_discovered / max(devices_expected, 1) if devices_expected > 0 else 1.0
            
            with open(self.roster_log_file, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([timestamp, device_id, devices_discovered, devices_expected, 
                               accuracy, response_delay_ms])
    
    def log_command_delivery(self, sender_id, target_id, message, buffered_time, 
                           delivery_delay_ms=None, delivered=False, ack_received=False):
        with self.lock:
            timestamp = datetime.now().isoformat()
            
            with open(self.delivery_log_file, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([timestamp, sender_id, target_id, message, buffered_time, 
                               delivery_delay_ms or '', delivered, ack_received])

# Global instances
data_logger = DataLogger()

# MQTT client setup - Updated to latest API version
mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

# Statistics tracking
class StatsTracker:
    def __init__(self):
        self.stats = {
            'total_uplinks': 0,
            'keepalive_count': 0,
            'discover_count': 0,
            'command_count': 0,
            'ack_count': 0,
            'roster_sent': 0,
            'commands_buffered': 0,
            'commands_delivered': 0,
            'start_time': time.time()
        }
        self.lock = threading.Lock()
    
    def increment(self, counter):
        with self.lock:
            self.stats[counter] += 1
    
    def get_stats(self):
        with self.lock:
            runtime = time.time() - self.stats['start_time']
            return {**self.stats, 'runtime_minutes': runtime / 60}

stats = StatsTracker()

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print("Connected to TTN MQTT broker")
        # Subscribe to uplink messages - TTN v3 format
        topic = f"v3/{TTN_USERNAME}/devices/+/up"
        client.subscribe(topic)
        print(f"Subscribed to: {topic}")
    else:
        print(f"Failed to connect to MQTT broker: {rc}")

def on_message(client, userdata, msg):
    try:
        # Parse TTN message
        ttn_message = json.loads(msg.payload.decode())
        
        # Extract device info
        if 'end_device_ids' not in ttn_message:
            print(f"No end_device_ids found in message")
            return
            
        device_id = ttn_message['end_device_ids']['device_id']
        
        # Decode payload
        if 'uplink_message' in ttn_message and 'frm_payload' in ttn_message['uplink_message']:
            payload_b64 = ttn_message['uplink_message']['frm_payload']
            payload_bytes = base64.b64decode(payload_b64)
            
            # Try to decode as UTF-8 first (for JSON devices)
            try:
                payload_str = payload_bytes.decode('utf-8')
                
                # Parse application message
                try:
                    app_message = json.loads(payload_str)
                    handle_uplink(device_id, app_message, ttn_message)
                except json.JSONDecodeError:
                    # Handle as binary if JSON parsing fails
                    handle_binary_uplink(device_id, payload_bytes, ttn_message)
                    
            except UnicodeDecodeError:
                # Handle binary payload devices
                handle_binary_uplink(device_id, payload_bytes, ttn_message)
        else:
            print(f"No uplink payload found in message from {device_id}")
        
        stats.increment('total_uplinks')
        
    except Exception as e:
        print(f"Error processing message: {e}")
        import traceback
        traceback.print_exc()

def handle_binary_uplink(device_id, payload_bytes, ttn_message):
    """Handle binary payload from devices that don't send JSON"""
    timestamp = time.time()
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {device_id}: Binary payload ({len(payload_bytes)} bytes)")
    
    # Update device as active (even for binary payloads)
    device_manager.update_device(device_id, timestamp)
    
    # Check for buffered messages for this device
    buffered_msg = device_manager.get_buffered_message(device_id)
    if buffered_msg:
        send_downlink(device_id, buffered_msg)
        stats.increment('commands_delivered')
        print(f"Delivered buffered message to {device_id}")
    
    # You can add specific binary payload parsing here if needed
    # For now, just treat it as a keepalive-like message
    stats.increment('keepalive_count')

def handle_uplink(device_id, app_message, ttn_message):
    message_type = app_message.get('type')
    timestamp = time.time()
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {device_id}: {message_type}")
    
    # Log the message
    data_logger.log_message(device_id, message_type, ttn_message)
    
    # Update device as active
    device_manager.update_device(device_id, timestamp)
    
    # Check for buffered messages for this device
    buffered_msg = device_manager.get_buffered_message(device_id)
    if buffered_msg:
        send_downlink(device_id, buffered_msg)
        stats.increment('commands_delivered')
        print(f"Delivered buffered message to {device_id}")
        
        # Log command delivery
        data_logger.log_command_delivery(
            buffered_msg.get('id', 'unknown'),
            device_id,
            buffered_msg.get('message', ''),
            buffered_msg.get('buffered_time', 0),
            delivered=True
        )
    
    # Handle different message types
    if message_type == "KEEPALIVE":
        stats.increment('keepalive_count')
        # No specific action needed for keepalive
        
    elif message_type == "DISCOVER":
        stats.increment('discover_count')
        device_manager.record_discover_time(device_id)
        handle_discover(device_id)
        
    elif message_type == "COMMAND":
        stats.increment('command_count')
        handle_command(device_id, app_message)
        
    elif message_type == "ACK":
        stats.increment('ack_count')
        handle_ack(device_id, app_message)

def handle_discover(device_id):
    active_devices = device_manager.get_active_devices()
    
    # Calculate performance metrics
    devices_discovered = len([dev for dev in active_devices if dev != device_id])
    devices_expected = len(active_devices) - 1  # Exclude requesting device
    response_delay = device_manager.get_discover_delay(device_id)
    
    # Log roster performance
    if response_delay is not None:
        data_logger.log_roster_performance(device_id, devices_discovered, devices_expected, response_delay)
    
    # Create roster message
    roster_message = {
        "type": "ROSTER",
        "devices": [dev for dev in active_devices if dev != device_id],  # Exclude self
        "timestamp": time.time()
    }
    
    send_downlink(device_id, roster_message)
    stats.increment('roster_sent')
    
    print(f"Sent roster to {device_id}: {len(roster_message['devices'])} active devices")
    if response_delay:
        print(f"  Response delay: {response_delay:.1f} ms")

def handle_command(device_id, app_message):
    target_id = app_message.get('target')
    message = app_message.get('message')
    
    if not target_id or not message:
        print(f"Invalid command from {device_id}: missing target or message")
        return
    
    # Record command timing
    device_manager.record_command_time(device_id, target_id, message)
    
    # Create command message for target
    command_message = {
        "type": "COMMAND",
        "id": device_id,
        "message": message,
        "timestamp": time.time(),
        "buffered_time": time.time()  # Track when message was buffered
    }
    
    # Buffer the message for the target device
    device_manager.buffer_message(target_id, command_message)
    stats.increment('commands_buffered')
    
    # Log command buffering
    data_logger.log_command_delivery(device_id, target_id, message, time.time())
    
    print(f"Buffered command from {device_id} to {target_id}: {message}")

def handle_ack(device_id, app_message):
    target_id = app_message.get('target')
    
    # Calculate end-to-end delay if we have command timing data
    delay, cmd_info = device_manager.get_command_delay(target_id, device_id)
    
    if delay and cmd_info:
        print(f"ACK from {device_id} to {target_id} - End-to-end delay: {delay:.1f} ms")
        
        # Update command delivery log with ACK information
        data_logger.log_command_delivery(
            cmd_info['sender'],
            cmd_info['target'],
            cmd_info['message'],
            cmd_info['time'],
            delivery_delay_ms=delay,
            delivered=True,
            ack_received=True
        )
    else:
        print(f"ACK from {device_id} to {target_id}")

def send_downlink(device_id, message):
    try:
        # Create TTN downlink message
        payload = json.dumps(message)
        payload_b64 = base64.b64encode(payload.encode()).decode()
        
        downlink_message = {
            "downlinks": [{
                "f_port": 1,
                "frm_payload": payload_b64,
                "priority": "NORMAL"
            }]
        }
        
        # Publish to TTN downlink topic
        topic = f"v3/{TTN_APP_ID}/devices/{device_id}/down/push"
        mqtt_client.publish(topic, json.dumps(downlink_message))
        
        print(f"Sent downlink to {device_id}: {message['type']}")
        
    except Exception as e:
        print(f"Error sending downlink to {device_id}: {e}")

def print_stats():
    while True:
        time.sleep(30)  # Print stats every 30 seconds
        current_stats = stats.get_stats()
        print("\n" + "="*60)
        print("LORAWAN PEER MESSAGING SYSTEM STATISTICS")
        print("="*60)
        print(f"Runtime: {current_stats['runtime_minutes']:.1f} minutes")
        print(f"Total uplinks: {current_stats['total_uplinks']}")
        print(f"Keepalives: {current_stats['keepalive_count']}")
        print(f"Discovers: {current_stats['discover_count']}")
        print(f"Commands: {current_stats['command_count']}")
        print(f"ACKs: {current_stats['ack_count']}")
        print(f"Rosters sent: {current_stats['roster_sent']}")
        print(f"Commands buffered: {current_stats['commands_buffered']}")
        print(f"Commands delivered: {current_stats['commands_delivered']}")
        
        # Calculate performance metrics
        if current_stats['discover_count'] > 0:
            roster_success_rate = (current_stats['roster_sent'] / current_stats['discover_count']) * 100
            print(f"Roster success rate: {roster_success_rate:.1f}%")
        
        if current_stats['commands_buffered'] > 0:
            delivery_rate = (current_stats['commands_delivered'] / current_stats['commands_buffered']) * 100
            print(f"Command delivery rate: {delivery_rate:.1f}%")
        
        active_devices = device_manager.get_active_devices()
        print(f"Active devices: {len(active_devices)}")
        for device in active_devices:
            print(f"  - {device}")
        
        print(f"\nData files created in: data/")
        print(f"  - message_log.csv: All message traffic")
        print(f"  - roster_performance.csv: DISCOVER/ROSTER performance")
        print(f"  - command_delivery.csv: Command delivery tracking")
        print("="*60 + "\n")

def main():
    # Setup logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    print("Starting LoRaWAN Peer Messaging Application Server")
    print(f"Data will be logged to: {os.path.abspath('data/')}")
    
    # Validate configuration
    if not TTN_USERNAME or not TTN_PASSWORD or not TTN_APP_ID:
        print("ERROR: TTN credentials not configured properly!")
        print("Please update TTN_USERNAME, TTN_PASSWORD, and TTN_APP_ID")
        return
    
    # Setup MQTT client
    mqtt_client.username_pw_set(TTN_USERNAME, TTN_PASSWORD)
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    
    # Add TLS support for TTN (port 8883 requires TLS) without certificate verification
    import ssl
    mqtt_client.tls_set(cert_reqs=ssl.CERT_NONE)
    mqtt_client.tls_insecure_set(True)
    
    # Connect to TTN
    print("Connecting to TTN MQTT broker...")
    print(f"Server: {TTN_MQTT_SERVER}")
    print(f"Port: {TTN_MQTT_PORT}")
    print(f"Username: {TTN_USERNAME}")
    print(f"App ID: {TTN_APP_ID}")
    
    try:
        mqtt_client.connect(TTN_MQTT_SERVER, TTN_MQTT_PORT, 60)
    except Exception as e:
        print(f"Failed to connect to TTN: {e}")
        return
    
    # Start statistics thread
    stats_thread = threading.Thread(target=print_stats, daemon=True)
    stats_thread.start()
    
    # Start MQTT loop
    print("Starting MQTT loop...")
    print("Press Ctrl+C to stop")
    try:
        mqtt_client.loop_forever()
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
        mqtt_client.disconnect()

if __name__ == "__main__":
    main()