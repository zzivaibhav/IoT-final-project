 #include <lmic.h>
#include <hal/hal.h>
#include <SPI.h>

// TTN credentials - your device
static const u1_t PROGMEM APPEUI[8] = { 0x1C, 0x1E, 0x20, 0x7D, 0xB8, 0x62, 0xDA, 0x2F };
void os_getArtEui(u1_t* buf) { memcpy_P(buf, APPEUI, 8); }

static const u1_t PROGMEM DEVEUI[8] = { 0x66, 0xE5, 0x40, 0xEE, 0xC4, 0xD6, 0x7D, 0x61 };
void os_getDevEui(u1_t* buf) { memcpy_P(buf, DEVEUI, 8); }

static const u1_t PROGMEM APPKEY[16] = { 0x54, 0xE2, 0x3A, 0xA7, 0xE1, 0x4B, 0xBF, 0xEC, 0x97, 0xAD, 0x0B, 0x00, 0xC8, 0xE7, 0xD4, 0xFD };
void os_getDevKey(u1_t* buf) { memcpy_P(buf, APPKEY, 16); }

// Pin mapping for TTGO LoRa32
const lmic_pinmap lmic_pins = {
    .nss = 18,
    .rxtx = LMIC_UNUSED_PIN,
    .rst = 14,
    .dio = {26, 33, 32},
};

static osjob_t keepalivejob;
bool joined = false;

// Keepalive interval in seconds
const unsigned TX_INTERVAL = 120;

void setup() {
    Serial.begin(115200);
    Serial.println("Simple LoRaWAN DISCOVER");
    
    // Initialize LMIC
    os_init();
    LMIC_reset();
    
    // Start join
    LMIC_startJoining();
}

void loop() {
    os_runloop_once();
    
    // Check for 'D' input after joining
    if (joined && Serial.available()) {
        String input = Serial.readString();
        input.trim();
        if (input.equalsIgnoreCase("D")) {
            Serial.println("DISCOVER command received from terminal");
            sendDiscover();
        }
    }
}

void sendDiscover() {
    if (LMIC.opmode & OP_TXRXPEND) {
        Serial.println("Radio busy, not sending DISCOVER (duty cycle or transmission in progress)");
        return;
    }
    
    // Simple DISCOVER message
    String msg = "{\"type\":\"DISCOVER\",\"id\":\"eui-66e540eec4d67d61\"}";
    
    Serial.println("Sending DISCOVER: " + msg);
    LMIC_setTxData2(1, (uint8_t*)msg.c_str(), msg.length(), 0);
}

void sendKeepalive() {
    // Simple keepalive message
    String msg = "{\"type\":\"KEEPALIVE\",\"id\":\"eui-66e540eec4d67d61\"}";
    
    Serial.println("Sending keepalive: " + msg);
    LMIC_setTxData2(1, (uint8_t*)msg.c_str(), msg.length(), 0);
}

void do_send(osjob_t* j) {
    if (LMIC.opmode & OP_TXRXPEND) {
        Serial.println("Previous tx not finished, skipping keepalive");
    } else {
        sendKeepalive();
    }
    // Always schedule next keepalive
    os_setTimedCallback(&keepalivejob, os_getTime()+sec2osticks(TX_INTERVAL), do_send);
}

void processRosterDownlink(const uint8_t* data, uint8_t len) {
    // Copy payload to a String for parsing
    String payload = "";
    for (uint8_t i = 0; i < len; i++) {
        payload += (char)data[i];
    }
    // Look for ROSTER type
    if (payload.indexOf("\"type\":\"ROSTER\"") != -1) {
        Serial.println("\n[ROSTER] Downlink received:");
        // Find devices array
        int devStart = payload.indexOf("\"devices\":[");
        if (devStart != -1) {
            devStart += 11; // move past '"devices":['
            int devEnd = payload.indexOf(']', devStart);
            if (devEnd != -1) {
                String devList = payload.substring(devStart, devEnd);
                // Split by comma
                int count = 0;
                int last = 0;
                Serial.println("  Devices discovered:");
                while (last < devList.length()) {
                    int next = devList.indexOf(',', last);
                    String dev = (next == -1) ? devList.substring(last) : devList.substring(last, next);
                    dev.trim();
                    dev.replace("\"", ""); // remove quotes
                    if (dev.length() > 0) {
                        Serial.print("    - ");
                        Serial.println(dev);
                        count++;
                    }
                    if (next == -1) break;
                    last = next + 1;
                }
                if (count == 0) Serial.println("    (none)");
            }
        }
    }
}

void onEvent(ev_t ev) {
    switch(ev) {
        case EV_JOINING:
            Serial.println("Joining...");
            break;
        case EV_JOINED:
            Serial.println("Joined! Type 'D' to send DISCOVER");
            joined = true;
            LMIC_setLinkCheckMode(0);
            // Start keepalive transmission
            os_setTimedCallback(&keepalivejob, os_getTime()+sec2osticks(TX_INTERVAL), do_send);
            break;
        case EV_JOIN_FAILED:
            Serial.println("Join failed");
            break;
        case EV_TXCOMPLETE:
            Serial.println("Message sent");
            if (LMIC.txrxFlags & TXRX_ACK)
                Serial.println("Received ack");
            if (LMIC.dataLen) {
                Serial.println("Received " + String(LMIC.dataLen) + " bytes of payload");
                processRosterDownlink(LMIC.frame+LMIC.dataBeg, LMIC.dataLen);
            }
            break;
        case EV_TXSTART:
            Serial.println("Transmitting...");
            break;
    }
}







