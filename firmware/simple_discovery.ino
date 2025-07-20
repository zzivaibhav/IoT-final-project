#include <lmic.h>
#include <hal/hal.h>
#include <SPI.h>

// TTN credentials - Replace with your device credentials
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

// Timing intervals (in seconds)
const unsigned KEEPALIVE_INTERVAL = 120;  // 2 minutes for better Class A timing

void setup() {
    Serial.begin(115200);
    Serial.println("==========================================");
    Serial.println("    LoRaWAN DISCOVER/ROSTER Demo");
    Serial.println("           Project P2 - Class A");
    Serial.println("==========================================");
    
    // Initialize LMIC
    os_init();
    LMIC_reset();
    
    // Configure for Class A (this is default but explicit)
    LMIC_setClockError(MAX_CLOCK_ERROR * 1 / 100);
    
    // Start join procedure
    Serial.println("🔄 Starting LoRaWAN join...");
    LMIC_startJoining();
}

void loop() {
    os_runloop_once();
    
    // Check for user commands after joining
    if (joined && Serial.available()) {
        String input = Serial.readString();
        input.trim();
        input.toUpperCase();
        
        if (input == "D") {
            Serial.println("📡 User requested DISCOVER...");
            sendDiscover();
        } else if (input == "STATUS") {
            printStatus();
        } else if (input == "HELP") {
            printHelp();
        }
    }
}

void sendDiscover() {
    // Check if radio is busy
    if (LMIC.opmode & OP_TXRXPEND) {
        Serial.println("⚠️  Radio busy - cannot send DISCOVER now");
        return;
    }
    
    // Create DISCOVER message
    String msg = "{\"type\":\"DISCOVER\",\"id\":\"eui-617dd6c4ee40e566\"}";
    
    Serial.println("📤 Sending DISCOVER...");
    Serial.println("   Message: " + msg);
    
    // Send uplink (Class A will listen for downlink in RX1/RX2 windows)
    LMIC_setTxData2(1, (uint8_t*)msg.c_str(), msg.length(), 0);
}

void sendKeepalive() {
    // Simple keepalive to maintain active status
    String msg = "{\"type\":\"KEEPALIVE\",\"id\":\"eui-617dd6c4ee40e566\"}";
    
    Serial.println("💓 Sending keepalive...");
    LMIC_setTxData2(1, (uint8_t*)msg.c_str(), msg.length(), 0);
}

void scheduleKeepalive(osjob_t* j) {
    // Check if radio is available
    if (LMIC.opmode & OP_TXRXPEND) {
        Serial.println("⚠️  Skipping keepalive - radio busy");
    } else {
        sendKeepalive();
    }
    
    // Schedule next keepalive
    os_setTimedCallback(&keepalivejob, 
                       os_getTime() + sec2osticks(KEEPALIVE_INTERVAL), 
                       scheduleKeepalive);
}

void processRosterDownlink(const uint8_t* data, uint8_t len) {
    Serial.println("\n📥 DOWNLINK RECEIVED!");
    Serial.println("   Length: " + String(len) + " bytes");
    
    // Convert bytes to string
    String payload = "";
    for (uint8_t i = 0; i < len; i++) {
        payload += (char)data[i];
    }
    
    Serial.println("   Raw payload: " + payload);
    
    // Look for ROSTER message
    if (payload.indexOf("\"type\":\"ROSTER\"") != -1) {
        Serial.println("\n🎯 ROSTER MESSAGE DETECTED!");
        Serial.println("==========================================");
        
        // Parse devices array
        int devicesStart = payload.indexOf("\"devices\":[");
        if (devicesStart != -1) {
            devicesStart += 11; // Skip past '"devices":['
            int devicesEnd = payload.indexOf(']', devicesStart);
            
            if (devicesEnd != -1) {
                String devicesList = payload.substring(devicesStart, devicesEnd);
                
                // Count and display devices
                int deviceCount = 0;
                Serial.println("📋 Active devices discovered:");
                
                if (devicesList.length() > 0) {
                    int lastPos = 0;
                    while (lastPos < devicesList.length()) {
                        int nextComma = devicesList.indexOf(',', lastPos);
                        String device = (nextComma == -1) ? 
                                       devicesList.substring(lastPos) : 
                                       devicesList.substring(lastPos, nextComma);
                        
                        device.trim();
                        device.replace("\"", ""); // Remove quotes
                        
                        if (device.length() > 0) {
                            Serial.println("   • " + device);
                            deviceCount++;
                        }
                        
                        if (nextComma == -1) break;
                        lastPos = nextComma + 1;
                    }
                }
                
                if (deviceCount == 0) {
                    Serial.println("   (No other devices active)");
                }
                
                Serial.println("==========================================");
                Serial.println("✅ Discovery complete! Found " + String(deviceCount) + " active devices");
                
            } else {
                Serial.println("⚠️  Malformed ROSTER - no closing bracket");
            }
        } else {
            Serial.println("⚠️  ROSTER message missing devices array");
        }
    } else {
        Serial.println("⚠️  Unknown downlink message type");
    }
    
    Serial.println("\n💡 Type 'D' to discover again, 'HELP' for commands");
}

void onEvent(ev_t ev) {
    Serial.print("[" + String(millis()/1000) + "s] ");
    
    switch(ev) {
        case EV_JOINING:
            Serial.println("🔄 Joining network...");
            break;
            
        case EV_JOINED:
            Serial.println("✅ Successfully joined LoRaWAN network!");
            Serial.println("==========================================");
            Serial.println("📖 Commands:");
            Serial.println("   D      - Send DISCOVER request");
            Serial.println("   STATUS - Show device status"); 
            Serial.println("   HELP   - Show this help");
            Serial.println("==========================================");
            joined = true;
            
            // Disable link check (not needed for this demo)
            LMIC_setLinkCheckMode(0);
            
            // Start periodic keepalives
            os_setTimedCallback(&keepalivejob, 
                               os_getTime() + sec2osticks(KEEPALIVE_INTERVAL), 
                               scheduleKeepalive);
            break;
            
        case EV_JOIN_FAILED:
            Serial.println("❌ Join failed - check credentials");
            break;
            
        case EV_TXCOMPLETE:
            Serial.println("📤 Transmission complete");
            
            if (LMIC.txrxFlags & TXRX_ACK) {
                Serial.println("   ✅ ACK received");
            }
            
            // Check for downlink data (Class A)
            if (LMIC.dataLen) {
                Serial.println("   📥 Downlink received: " + String(LMIC.dataLen) + " bytes");
                processRosterDownlink(LMIC.frame + LMIC.dataBeg, LMIC.dataLen);
            } else {
                Serial.println("   📭 No downlink data");
            }
            break;
            
        case EV_TXSTART:
            Serial.println("📡 Starting transmission...");
            break;
            
        case EV_SCAN_TIMEOUT:
            Serial.println("⏰ Scan timeout");
            break;
            
        case EV_BEACON_FOUND:
            Serial.println("📡 Beacon found");
            break;
            
        case EV_BEACON_MISSED:
            Serial.println("📡 Beacon missed");
            break;
            
        case EV_BEACON_TRACKED:
            Serial.println("📡 Beacon tracked");
            break;
            
        case EV_RFU1:
            Serial.println("EV_RFU1");
            break;
            
        case EV_RFU2:
            Serial.println("EV_RFU2");
            break;
            
        default:
            Serial.println("Event: " + String(ev));
            break;
    }
}

void printStatus() {
    Serial.println("\n📊 DEVICE STATUS");
    Serial.println("==========================================");
    Serial.println("Network: " + String(joined ? "✅ Connected" : "❌ Not connected"));
    Serial.println("Uptime: " + String(millis()/1000) + " seconds");
    Serial.println("Free RAM: " + String(ESP.getFreeHeap()) + " bytes");
    Serial.println("Frequency: " + String(LMIC.freq/1000000.0, 1) + " MHz");
    Serial.println("Data Rate: SF" + String(getSF()));
    Serial.println("TX Power: " + String(LMIC.txpow) + " dBm");
    Serial.println("==========================================\n");
}

void printHelp() {
    Serial.println("\n📖 HELP - LoRaWAN Discovery Demo");
    Serial.println("==========================================");
    Serial.println("This demo shows how Class A devices can");
    Serial.println("discover other active LoRaWAN devices:");
    Serial.println("");
    Serial.println("1. Device sends DISCOVER uplink");
    Serial.println("2. Server responds with ROSTER downlink");
    Serial.println("3. Device displays active peer devices");
    Serial.println("");
    Serial.println("Commands:");
    Serial.println("   D      - Send DISCOVER request");
    Serial.println("   STATUS - Show device information");
    Serial.println("   HELP   - Show this help");
    Serial.println("");
    Serial.println("Note: Class A devices can only receive");
    Serial.println("downlinks immediately after uplinks!");
    Serial.println("==========================================\n");
}

int getSF() {
    // Extract spreading factor from data rate
    switch(LMIC.datarate) {
        case DR_SF12: return 12;
        case DR_SF11: return 11;
        case DR_SF10: return 10;
        case DR_SF9:  return 9;
        case DR_SF8:  return 8;
        case DR_SF7:  return 7;
        default:      return 7;
    }
}
