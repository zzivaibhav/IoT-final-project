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

// Message types
#define MSG_KEEPALIVE 0x01
#define MSG_DISCOVER  0x02
#define MSG_COMMAND   0x03
#define MSG_ACK       0x04

// Timing constants (in seconds)
#define KEEPALIVE_INTERVAL 60  // Send keepalive every 60 seconds

// Global variables
static osjob_t sendjob;
static uint8_t mydata[] = {MSG_KEEPALIVE};
static uint8_t roster[32];  // Buffer for received roster
static uint8_t roster_size = 0;
static unsigned long last_keepalive = 0;
static bool waiting_for_roster = false;
static bool send_ack_flag = false;
static bool tx_pending_logged = false;  // Track if we've already logged TX pending state

void printHex2(unsigned v) {
    v &= 0xff;
    if (v < 16)
        Serial.print('0');
    Serial.print(v, HEX);
}

void onEvent (ev_t ev) {
    Serial.print(os_getTime());
    Serial.print(": ");
    switch(ev) {
        case EV_SCAN_TIMEOUT:
            Serial.println(F("Network scan timed out - no gateways found"));
            break;
        case EV_BEACON_FOUND:
            Serial.println(F("Network beacon detected"));
            break;
        case EV_BEACON_MISSED:
            Serial.println(F("Network beacon signal lost"));
            break;
        case EV_BEACON_TRACKED:
            Serial.println(F("Network beacon signal locked"));
            break;
        case EV_JOINING:
            Serial.println(F("Attempting to join LoRaWAN network..."));
            break;
        case EV_JOINED:
            Serial.println(F("Successfully joined LoRaWAN network"));
   LMIC_setAdrMode(0);
LMIC_setDrTxpow(DR_SF7, 14);
            LMIC_setLinkCheckMode(0);
            break;
        case EV_JOIN_FAILED:
            Serial.println(F("Failed to join LoRaWAN network - check credentials"));
            break;
        case EV_REJOIN_FAILED:
            Serial.println(F("Failed to rejoin LoRaWAN network"));
            break;
        case EV_TXCOMPLETE:
            Serial.println(F("Message transmission completed"));
            tx_pending_logged = false;  // Reset flag when transmission completes
            if (LMIC.txrxFlags & TXRX_ACK)
              Serial.println(F("Server acknowledgment received"));
            if (LMIC.dataLen) {
              Serial.print(F("Received "));
              Serial.print(LMIC.dataLen);
              Serial.println(F(" bytes of data from server"));
              
              // Process received downlink
              if (LMIC.dataLen > 0) {
                uint8_t msg_type = LMIC.frame[LMIC.dataBeg];
                if (msg_type == 0x80) {  // ROSTER message
                  Serial.println(F("Device roster received from server"));
                  roster_size = LMIC.dataLen - 1;
                  memcpy(roster, &LMIC.frame[LMIC.dataBeg + 1], roster_size);
                  waiting_for_roster = false;
                  
                  // Print roster
                  Serial.print(F("Active devices: "));
                  for (int i = 0; i < roster_size; i += 2) {
                    Serial.print(i/2);
                    Serial.print(F(": "));
                    printHex2(roster[i]);
                    printHex2(roster[i+1]);
                    Serial.print(F(" "));
                  }
                  Serial.println();
                  
                  // Print instructions for user
                  Serial.println(F("Enter device number (0-n) to send command, or any other key to skip:"));
                  
                } else if (msg_type == MSG_COMMAND) {  // Received command
                  Serial.println(F("Command received from another device"));
                  send_ack_flag = true;
                }
              }
            }
            // Schedule next transmission
            os_setTimedCallback(&sendjob, os_getTime()+sec2osticks(2), do_send);
            break;
        case EV_LOST_TSYNC:
            Serial.println(F("Network time synchronization lost"));
            break;
        case EV_RESET:
            Serial.println(F("LoRaWAN module reset"));
            break;
        case EV_RXCOMPLETE:
            Serial.println(F("Data reception completed"));
            break;
        case EV_LINK_DEAD:
            Serial.println(F("Network connection lost"));
            break;
        case EV_LINK_ALIVE:
            Serial.println(F("Network connection restored"));
            break;
        case EV_TXSTART:
            Serial.println(F("Starting message transmission..."));
            break;
        default:
            Serial.print(F("Unknown network event: "));
            Serial.println((unsigned) ev);
            break;
    }
}

void send_keepalive() {
    mydata[0] = MSG_KEEPALIVE;
    LMIC_setTxData2(1, mydata, 1, 0);
    Serial.println(F("Sent KEEPALIVE"));
    last_keepalive = millis() / 1000;
}

void send_discover() {
    mydata[0] = MSG_DISCOVER;
    LMIC_setTxData2(1, mydata, 1, 0);
    Serial.println(F("Sent DISCOVER"));
    waiting_for_roster = true;
}

void send_command(uint8_t target_byte1, uint8_t target_byte2) {
    mydata[0] = MSG_COMMAND;
    mydata[1] = target_byte1;
    mydata[2] = target_byte2;
    mydata[3] = 0x42;  // Simple command data
    LMIC_setTxData2(1, mydata, 4, 0);
    Serial.print(F("Sent COMMAND to device: "));
    printHex2(target_byte1);
    printHex2(target_byte2);
    Serial.println();
}

void schedule_ack() {
    send_ack_flag = true;
}

void do_send(osjob_t* j){
    // Check if there is not a current TX/RX job running
    if (LMIC.opmode & OP_TXRXPEND) {
        if (!tx_pending_logged) {
            Serial.println(F("Radio busy - transmission pending, waiting..."));
            tx_pending_logged = true;
        }
        os_setTimedCallback(&sendjob, os_getTime()+sec2osticks(2), do_send);
        return;
    }
    
    unsigned long current_time = millis() / 1000;
    
    // Check if we need to send ACK first
    if (send_ack_flag) {
        mydata[0] = MSG_ACK;
        LMIC_setTxData2(1, mydata, 1, 0);
        Serial.println(F("Sent ACK"));
        send_ack_flag = false;
        return;
    }
    
    // Check if it's time for KEEPALIVE
    if (current_time - last_keepalive >= KEEPALIVE_INTERVAL) {
        send_keepalive();
    }
    else {
        // Schedule next check
        os_setTimedCallback(&sendjob, os_getTime()+sec2osticks(5), do_send);
    }
}

void setup() {
    Serial.begin(115200);
    Serial.println(F("Starting LoRaWAN P2P Messaging"));
    Serial.println(F("Commands:"));
    Serial.println(F("  D - Send DISCOVER to get active devices"));
    Serial.println(F("  0-9 - Send COMMAND to device number (after receiving roster)"));

    // LMIC init
    os_init();
    // Reset the MAC state. Session and pending data transfers will be discarded.
    LMIC_reset();

    // Start job (sending automatically starts OTAA too)
    do_send(&sendjob);
}

void loop() {
    os_runloop_once();
    
    // Handle serial input
    if (Serial.available() > 0) {
        char input = Serial.read();
        
        // Clear any extra characters in buffer
        while (Serial.available() > 0) {
            Serial.read();
        }
        
        if (input == 'D' || input == 'd') {
            if (LMIC.opmode & OP_TXRXPEND) {
                Serial.println(F("Transmission in progress, please wait..."));
            } else {
                send_discover();
            }
        }
        else if (input >= '0' && input <= '9' && roster_size > 0) {
            int device_index = input - '0';
            if (device_index < roster_size / 2) {  // Each device uses 2 bytes
                if (LMIC.opmode & OP_TXRXPEND) {
                    Serial.println(F("Transmission in progress, please wait..."));
                } else {
                    uint8_t byte1 = roster[device_index * 2];
                    uint8_t byte2 = roster[device_index * 2 + 1];
                    send_command(byte1, byte2);
                }
            } else {
                Serial.println(F("Invalid device number"));
            }
        }
        else if (roster_size == 0 && input >= '0' && input <= '9') {
            Serial.println(F("No roster available. Send 'D' to discover devices first."));
        }
    }
}