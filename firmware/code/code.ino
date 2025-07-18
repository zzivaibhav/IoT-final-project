#include <lmic.h>
#include <hal/hal.h>
#include <SPI.h>
#include <ArduinoJson.h>

// DEVICE IDENTIFIERS (DevEUI, AppEUI, AppKey)
static const u1_t PROGMEM APPEUI[8] = { 0x1C, 0x1E, 0x20, 0x7D, 0xB8, 0x62, 0xDA, 0x2F };
void os_getArtEui (u1_t* buf) { memcpy_P(buf, APPEUI, 8);}

static const u1_t PROGMEM DEVEUI[8] = { 0x66, 0xE5, 0x40, 0xEE, 0xC4, 0xD6, 0x7D, 0x61 };
void os_getDevEui (u1_t* buf) { memcpy_P(buf, DEVEUI, 8);}

static const u1_t PROGMEM APPKEY[16] = { 0x54, 0xE2, 0x3A, 0xA7, 0xE1, 0x4B, 0xBF, 0xEC, 0x97, 0xAD, 0x0B, 0x00, 0xC8, 0xE7, 0xD4, 0xFD };
void os_getDevKey (u1_t* buf) {  memcpy_P(buf, APPKEY, 16);}

// Pin mapping for TTGO LoRa32
const lmic_pinmap lmic_pins = {
    .nss = 18,
    .rxtx = LMIC_UNUSED_PIN,
    .rst = 14,
    .dio = {26, 33, 32},
};

// Message types
enum MessageType {
    KEEPALIVE = 0x01,
    DISCOVER = 0x02,
    COMMAND = 0x03,
    ACK = 0x04
};

// State management
enum DeviceState {
    JOINING,
    SENDING_KEEPALIVE,
    SENDING_DISCOVER,
    SENDING_COMMAND,
    WAITING_FOR_DOWNLINK,
    PROCESSING_ROSTER
};

DeviceState currentState = JOINING;
unsigned long lastUplink = 0;
unsigned long keepaliveInterval = 60000; // 60 seconds
unsigned long discoverInterval = 120000; // 2 minutes
unsigned long lastDiscover = 0;
String deviceId;
String targetDeviceId;
String pendingMessage;
bool waitingForRoster = false;
bool waitingForAck = false;
unsigned long commandStartTime = 0;
unsigned long discoverStartTime = 0;

// Active devices list from roster
String activeDevices[10];
int activeDeviceCount = 0;

static osjob_t sendjob;

void setup() {
    Serial.begin(115200);
    Serial.println(F("Starting LoRaWAN Peer Messaging"));
    
    // Use TTN DevEUI as device ID (convert from array to hex string)
    deviceId = "";
    for (int i = 0; i < 8; i++) {
        if (DEVEUI[i] < 0x10) deviceId += "0";
        deviceId += String(DEVEUI[i], HEX);
    }
    deviceId = "eui-" + deviceId;
    Serial.println("Device ID: " + deviceId);
    
    // LMIC init
    os_init();
    LMIC_reset();
    LMIC_setClockError(MAX_CLOCK_ERROR * 1 / 100);
    
    // Start joining
    do_send(&sendjob);
}

void loop() {
    os_runloop_once();
    
    // Handle periodic tasks
    unsigned long now = millis();
    
    if (currentState == SENDING_KEEPALIVE && (now - lastUplink) > keepaliveInterval) {
        sendKeepalive();
    }
    
    if ((now - lastDiscover) > discoverInterval) {
        sendDiscover();
    }
    
    // Simulate user input for testing
    if (Serial.available()) {
        String input = Serial.readString();
        input.trim();
        
        if (input.startsWith("cmd:")) {
            String parts = input.substring(4);
            int colonIndex = parts.indexOf(':');
            if (colonIndex > 0) {
                targetDeviceId = parts.substring(0, colonIndex);
                pendingMessage = parts.substring(colonIndex + 1);
                sendCommand();
            }
        }
    }
}

void sendKeepalive() {
    if (LMIC.opmode & OP_TXRXPEND) {
        Serial.println(F("OP_TXRXPEND, not sending"));
        return;
    }
    
    // Create keepalive message
    StaticJsonDocument<64> msg;
    msg["type"] = "KEEPALIVE";
    msg["id"] = deviceId;
    msg["ts"] = millis();
    
    String payload;
    serializeJson(msg, payload);
    
    LMIC_setTxData2(1, (uint8_t*)payload.c_str(), payload.length(), 0);
    Serial.println(F("Keepalive sent"));
    
    lastUplink = millis();
    currentState = SENDING_KEEPALIVE;
}

void sendDiscover() {
    if (LMIC.opmode & OP_TXRXPEND) {
        Serial.println(F("OP_TXRXPEND, not sending"));
        return;
    }
    
    StaticJsonDocument<64> msg;
    msg["type"] = "DISCOVER";
    msg["id"] = deviceId;
    msg["ts"] = millis();
    
    String payload;
    serializeJson(msg, payload);
    
    LMIC_setTxData2(1, (uint8_t*)payload.c_str(), payload.length(), 0);
    Serial.println(F("Discover sent"));
    
    lastDiscover = millis();
    discoverStartTime = millis();
    currentState = SENDING_DISCOVER;
    waitingForRoster = true;
}

void sendCommand() {
    if (LMIC.opmode & OP_TXRXPEND) {
        Serial.println(F("OP_TXRXPEND, not sending"));
        return;
    }
    
    StaticJsonDocument<128> msg;
    msg["type"] = "COMMAND";
    msg["id"] = deviceId;
    msg["target"] = targetDeviceId;
    msg["message"] = pendingMessage;
    msg["ts"] = millis();
    
    String payload;
    serializeJson(msg, payload);
    
    LMIC_setTxData2(1, (uint8_t*)payload.c_str(), payload.length(), 0);
    Serial.println("Command sent to " + targetDeviceId + ": " + pendingMessage);
    
    commandStartTime = millis();
    currentState = SENDING_COMMAND;
    waitingForAck = true;
}

void sendAck(String originalSender) {
    if (LMIC.opmode & OP_TXRXPEND) {
        Serial.println(F("OP_TXRXPEND, not sending"));
        return;
    }
    
    StaticJsonDocument<96> msg;
    msg["type"] = "ACK";
    msg["id"] = deviceId;
    msg["target"] = originalSender;
    msg["ts"] = millis();
    
    String payload;
    serializeJson(msg, payload);
    
    LMIC_setTxData2(1, (uint8_t*)payload.c_str(), payload.length(), 0);
    Serial.println("ACK sent to " + originalSender);
}

void onEvent (ev_t ev) {
    Serial.print(os_getTime());
    Serial.print(": ");
    switch(ev) {
        case EV_SCAN_TIMEOUT:
            Serial.println(F("EV_SCAN_TIMEOUT"));
            break;
        case EV_BEACON_FOUND:
            Serial.println(F("EV_BEACON_FOUND"));
            break;
        case EV_BEACON_MISSED:
            Serial.println(F("EV_BEACON_MISSED"));
            break;
        case EV_BEACON_TRACKED:
            Serial.println(F("EV_BEACON_TRACKED"));
            break;
        case EV_JOINING:
            Serial.println(F("EV_JOINING"));
            break;
        case EV_JOINED:
            Serial.println(F("EV_JOINED"));
            LMIC_setLinkCheckMode(0);
            currentState = SENDING_KEEPALIVE;
            break;
        case EV_JOIN_FAILED:
            Serial.println(F("EV_JOIN_FAILED"));
            break;
        case EV_REJOIN_FAILED:
            Serial.println(F("EV_REJOIN_FAILED"));
            break;
        case EV_TXCOMPLETE:
            Serial.println(F("EV_TXCOMPLETE"));
            if (LMIC.txrxFlags & TXRX_ACK)
                Serial.println(F("Received ack"));
            if (LMIC.dataLen) {
                Serial.print(F("Received "));
                Serial.print(LMIC.dataLen);
                Serial.println(F(" bytes of payload"));
                handleDownlink();
            } else {
                Serial.println(F("No downlink received"));
            }
            os_setTimedCallback(&sendjob, os_getTime()+sec2osticks(60), do_send);
            break;
        case EV_LOST_TSYNC:
            Serial.println(F("EV_LOST_TSYNC"));
            break;
        case EV_RESET:
            Serial.println(F("EV_RESET"));
            break;
        case EV_RXCOMPLETE:
            Serial.println(F("EV_RXCOMPLETE"));
            break;
        case EV_LINK_DEAD:
            Serial.println(F("EV_LINK_DEAD"));
            break;
        case EV_LINK_ALIVE:
            Serial.println(F("EV_LINK_ALIVE"));
            break;
        case EV_TXSTART:
            Serial.println(F("EV_TXSTART"));
            break;
        default:
            Serial.print(F("Unknown event: "));
            Serial.println((unsigned) ev);
            break;
    }
}

void handleDownlink() {
    String payload = "";
    for (int i = 0; i < LMIC.dataLen; i++) {
        payload += (char)LMIC.frame[LMIC.dataBeg + i];
    }
    
    Serial.println("Downlink received: " + payload);
    
    StaticJsonDocument<512> doc;
    deserializeJson(doc, payload);
    
    String msgType = doc["type"];
    
    if (msgType == "ROSTER" && waitingForRoster) {
        handleRoster(doc);
        waitingForRoster = false;
        
        // Calculate discover delay
        unsigned long discoverDelay = millis() - discoverStartTime;
        Serial.println("Discover-to-Roster delay: " + String(discoverDelay) + " ms");
    }
    else if (msgType == "COMMAND") {
        handleCommand(doc);
    }
    else if (msgType == "ACK" && waitingForAck) {
        handleAckReceived(doc);
        waitingForAck = false;
        
        // Calculate command delay
        unsigned long commandDelay = millis() - commandStartTime;
        Serial.println("Command-to-ACK delay: " + String(commandDelay) + " ms");
    }
}

void handleRoster(StaticJsonDocument<512>& doc) {
    Serial.println("Processing roster...");
    
    activeDeviceCount = 0;
    JsonArray devices = doc["devices"];
    
    for (JsonVariant device : devices) {
        if (activeDeviceCount < 10) {
            activeDevices[activeDeviceCount] = device.as<String>();
            activeDeviceCount++;
        }
    }
    
    Serial.println("Active devices found: " + String(activeDeviceCount));
    for (int i = 0; i < activeDeviceCount; i++) {
        Serial.println("- " + activeDevices[i]);
    }
    
    currentState = PROCESSING_ROSTER;
}

void handleCommand(StaticJsonDocument<512>& doc) {
    String sender = doc["id"];
    String message = doc["message"];
    
    Serial.println("Command received from " + sender + ": " + message);
    
    // Send ACK back
    sendAck(sender);
}

void handleAckReceived(StaticJsonDocument<512>& doc) {
    String sender = doc["id"];
    Serial.println("ACK received from " + sender);
}

void do_send(osjob_t* j) {
    if (LMIC.opmode & OP_TXRXPEND) {
        Serial.println(F("OP_TXRXPEND, not sending"));
    } else {
        if (currentState == JOINING) {
            // Will trigger join
        } else {
            sendKeepalive();
        }
    }
}