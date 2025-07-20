import paho.mqtt.client as mqtt
import json
import base64
import os
import csv
from datetime import datetime

# Configuration (unchanged)
TTN_MQTT_SERVER = "nam1.cloud.thethings.network"
TTN_MQTT_PORT = 8883
TTN_USERNAME = "test-dal@ttn"
TTN_PASSWORD = "NNSXS.HATGGJ2NG5AZYYF4QKEYBCPSI3FLKK7GFFDUCVI.6Z373ADOU6RED6V3Y47CFRYM347RBSCN2ETWW4WIHUUGEFWOTRHQ"
TTN_APP_ID = "test-dal"
DEVICE_ID = "eui-66E540EEC4D67D61"

# Initialize log file
def init_downlink_log():
    log_dir = "data"
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "downlink_log.csv")
    if not os.path.exists(log_file):
        with open(log_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp', 'device_id', 'message_type', 'payload_size', 'success', 'error_message'])
    return log_file

# Log downlink attempt
def log_downlink(log_file, device_id, message_type, payload_size, success, error_message=''):
    timestamp = datetime.now().isoformat()
    with open(log_file, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([timestamp, device_id, message_type, payload_size, success, error_message])

# MQTT on_connect callback
def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0 and not userdata['downlink_sent']:
        print("Connected to TTN MQTT broker")
        send_downlink(client, userdata['log_file'])
        userdata['downlink_sent'] = True
    elif rc != 0:
        print(f"Failed to connect to MQTT broker: {rc}")
        log_downlink(userdata['log_file'], DEVICE_ID, "ROSTER", 0, False, f"MQTT connect error {rc}")

# Send single downlink
def send_downlink(client, log_file):
    try:
        # Create minimal JSON ROSTER payload
        message = {
            "type": "ROSTER",
            "devices": ["eui-12345678"]
        }
        payload = json.dumps(message)
        payload_bytes = payload.encode()
        payload_b64 = base64.b64encode(payload_bytes).decode()
        
        # Check payload size (LoRaWAN SF7 limit: ~51 bytes)
        if len(payload_bytes) > 51:
            print(f"Payload too large: {len(payload_bytes)} bytes")
            log_downlink(log_file, DEVICE_ID, "ROSTER", len(payload_bytes), False, "Payload too large")
            return
        
        # Create TTN downlink message
        downlink_message = {
            "downlinks": [{
                "f_port": 1,
                "frm_payload": payload_b64,
                "priority": "NORMAL"
            }]
        }
        
        # Publish to TTN downlink topic
        topic = f"v3/{TTN_APP_ID}/devices/{DEVICE_ID}/down/push"
        result = client.publish(topic, json.dumps(downlink_message))
        
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            print(f"Downlink sent to {DEVICE_ID}: ROSTER, {len(payload_bytes)} bytes")
            log_downlink(log_file, DEVICE_ID, "ROSTER", len(payload_bytes), True)
        else:
            error_msg = f"MQTT error {result.rc}"
            print(f"Downlink failed for {DEVICE_ID}: {error_msg}")
            log_downlink(log_file, DEVICE_ID, "ROSTER", len(payload_bytes), False, error_msg)
            
    except Exception as e:
        error_msg = str(e)
        print(f"Error sending downlink to {DEVICE_ID}: {error_msg}")
        log_downlink(log_file, DEVICE_ID, "ROSTER", len(payload_bytes) if 'payload_bytes' in locals() else 0, False, error_msg)

def main():
    # Initialize log file
    log_file = init_downlink_log()
    print(f"Logging to: {os.path.abspath(log_file)}")
    
    # Setup MQTT client with downlink_sent flag
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, userdata={'log_file': log_file, 'downlink_sent': False})
    client.username_pw_set(TTN_USERNAME, TTN_PASSWORD)
    client.on_connect = on_connect
    
    # Add TLS support (TTN requires TLS on port 8883)
    import ssl
    client.tls_set(cert_reqs=ssl.CERT_NONE)
    client.tls_insecure_set(True)
    
    # Connect to TTN
    print("Connecting to TTN MQTT broker...")
    print(f"Server: {TTN_MQTT_SERVER}")
    print(f"Port: {TTN_MQTT_PORT}")
    print(f"Username: {TTN_USERNAME}")
    print(f"App ID: {TTN_APP_ID}")
    print(f"Device ID: {DEVICE_ID}")
    
    try:
        client.connect(TTN_MQTT_SERVER, TTN_MQTT_PORT, 60)
        client.loop_start()  # Start MQTT loop in background
        print("Sending one downlink... Press Ctrl+C to exit")
        client.loop_forever()  # Keep running to maintain connection
    except Exception as e:
        print(f"Failed to connect to TTN: {e}")
        log_downlink(log_file, DEVICE_ID, "ROSTER", 0, False, f"Connect error: {e}")
    finally:
        client.disconnect()

if __name__ == "__main__":
    main()