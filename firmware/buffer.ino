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

static osjob_t sendjob;
bool joined = false;

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
            sendDiscover();
        }
    }
}

void sendDiscover() {
    if (LMIC.opmode & OP_TXRXPEND) {
        Serial.println("Radio busy, not sending");
        return;
    }
    
    // Simple DISCOVER message
    String msg = "{\"type\":\"DISCOVER\",\"id\":\"eui-66e540eec4d67d61\"}";
    
    Serial.println("Sending: " + msg);
    LMIC_setTxData2(1, (uint8_t*)msg.c_str(), msg.length(), 0);
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
            break;
        case EV_JOIN_FAILED:
            Serial.println("Join failed");
            break;
        case EV_TXCOMPLETE:
            Serial.println("Message sent");
            break;
        case EV_TXSTART:
            Serial.println("Transmitting...");
            break;
    }
}




