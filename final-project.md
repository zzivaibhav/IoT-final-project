# Final Project
**Course:** CSCI-4270 / CSCI-6712 – Wireless Technologies for the Internet of Things

**Deadline:** 7:00 PM on **August 1, 2025**

**Submission:** Upload as **one zip file** on Brightspace

**Project Teams:** Students must form their project groups (4 students per group or simply a merge of two groups as defined during assignments) and choose one project by **Tuesday, July 8, 2025 at 11:59 PM**. Groups not submitted by the deadline will be assigned randomly.

**Hardware Provided:**
- **Project P1**: 2 × ESP32-C6 development boards per team
- **Project P2**: 2 × TTGO LoRa32 boards per team
- **Additional devices**: May be provided if available and required by your specific design (request during mid-project review)

**Mid-Project Review:** **Tuesday, July 22, 2025** - In-class progress review and troubleshooting session 
<!--
## 📋 Mid-Project Review Requirements (July 22, 2025)

Each team must present a **5-minute progress update** during the July 22nd lecture covering:

### Required Demo Components (Easily Verifiable):
- [ ] **Working prototype demonstration**: Show basic functionality on hardware
- [ ] **Code compilation**: Demonstrate that current code compiles and runs
- [ ] **Data collection progress**: Show sample data files (even if incomplete)
- [ ] **Team work distribution**: Clear explanation of who is doing what

### Progress Checklist:
- [ ] Hardware setup complete and tested
- [ ] Core functionality implemented (advertising/scanning for P1, or DISCOVER/ROSTER for P2)
- [ ] Initial data collection begun
- [ ] Report outline drafted
- [ ] Identified challenges and mitigation strategies

### Deliverables for Review:
- **Brief progress slides** (3-4 slides max): Current status, preliminary results, remaining work
- **Working code demonstration** (must compile and show basic functionality)
- **Sample data** (CSV file with at least 10 data points)

**Note**: This review is worth 10% of your final project grade and will help identify teams needing additional support.

---
-->

## 📋 General Requirements

### README File
Each submission must include a `README.txt` file for **reproducibility and setup** (see Assignment A1 for template structure):
- **Team information**: Group number, names, student IDs, track designation
- **Project choice**: P1 or P2 with brief rationale
- **Work distribution**: Who contributed to each component
- **File structure**: Brief description of each directory/file
- **Hardware setup**: Complete parts list, pin connections, assembly instructions
- **Software dependencies**: Required libraries, tools, specific versions used
- **Compilation/execution instructions**: Step-by-step setup and run commands
- **Reproduction guide**: How to replicate your experiments
- **Troubleshooting**: Known bugs, workarounds, common setup issues

### Report Format and Expectations
Your `report.pdf` should be structured as a **scientific technical report** focused on **analysis and findings**:
- **Length**: 3-4 pages minimum, 6 pages maximum (excluding references)
- **Format**: Scientific report format with clear section headers
- **Structure**: Abstract, Introduction, Methods, Results, Discussion, Conclusion
- **Focus**: Experimental design, data analysis, performance evaluation, and scientific insights
- **References**: Include relevant technical documentation, standards, and tools used

### Statistical Analysis Requirements
Your experimental evaluation should include appropriate statistical measures consistent with Assignment A1. The following list provides examples of statistical analysis that may be relevant to your project:
- **Descriptive statistics**: Mean, median, standard deviation for all quantitative metrics
- **95% confidence intervals**: For key performance metrics (RSSI, delivery rates, delays, etc.)
- **Correlation analysis**: Pearson correlation coefficients where relationships are examined (e.g., RSSI vs. distance, power vs. battery life)
- **Error analysis**: Quantify measurement uncertainty and systematic errors
- **Sample sizes**: Minimum 30 measurements per test condition for statistical validity

**Tools for Analysis**: Statistical analysis and visualization can be performed using Python (matplotlib, scipy, pandas), MATLAB, R, or advanced Excel functions. Choose the tool that best fits your team's experience and project needs.

---

# Project P1 – BLE Contact Tracer with Exposure Logic and Energy Budget

## 📡 Project Overview

In the context of virus outbreaks such as COVID-19, digital contact tracing has emerged as a promising tool for early detection and transmission mitigation. This project builds on those principles to explore decentralized BLE-based solutions for proximity sensing, privacy preservation, and energy-efficient deployment in wireless IoT systems.

In this project, you are required to build a decentralized BLE-based contact tracing system using the **2 ESP32-C6 devices provided to your team**. Each device must advertise a randomized identifier and simultaneously scan for nearby identifiers. Devices should log all contact encounters with associated timestamps and RSSI values, enabling proximity estimation and exposure tracking.

You will define and implement an exposure rule (e.g., "cumulative proximity ≥ 5 minutes within 1.5 meters"), calibrate the RSSI–distance relationship through controlled experiments, and evaluate the system's detection accuracy, false positives/negatives, and energy consumption. Data analysis can be performed locally on the devices or post-processed on a PC.

---

## 🧪 Project Features and Evaluation Goals

### Core Functionality

* Periodic BLE advertisements with randomized ID
* BLE scan and contact detection based on **RSSI > threshold**
* Local storage of encounter logs in flash or EEPROM
* Optional: user-initiated exposure check (e.g., button press + LED alert)

### Experimental Evaluation

* **RSSI–distance calibration**: Measure and plot RSSI vs actual distance in different conditions
* **Proximity detection performance**:
  * Deploy devices in real settings
  * Compare logged contact sessions against ground-truth (video or manual logs)
* **Energy profiling**:
  * Use the [Nordic Online Power Profiler](https://devzone.nordicsemi.com/power/w/opp/2/online-power-profiler-for-bluetooth-le) to estimate current draw based on BLE parameters
  * Compare BLE settings (advertising interval, scan interval, transmit power)
  * Estimate battery life across configurations
* **Data offloading and retrieval**:
  * Store all logs on-device in persistent storage
  * Implement Wi-Fi bulk upload functionality to transfer stored logs to a PC or server at the end of the deployment period

---

## 📦 Required Deliverables

| Component               | Description                                                                | Verification Criteria |
| ----------------------- | -------------------------------------------------------------------------- | --------------------- |
| `README.txt`            | Team info, setup instructions, file structure (see general requirements)  | Complete template fields, clear instructions |
| `firmware/`             | BLE scanner + advertiser source code, with exposure logic                  | Code compiles, well-commented, implements core functionality |
| `data/`                 | CSV log of detected contacts: timestamp, peer ID, RSSI, duration           | Minimum 30 data points per condition, proper CSV format |
| `plots/`                | RSSI vs. distance, energy vs. scan settings, detection accuracy            | Clear labels, appropriate scales, statistical annotations |
| `report.pdf`            | 3-6 pages: design, calibration setup, detection metrics, power analysis   | Follows scientific report structure, includes required sections |
| `demo.mp4` *(optional)* | Video showing detection logic in action (LED alert, serial log)            | Clear demonstration of working system |

---

## 📝 Evaluation Criteria

| Category                                                   | Points  |
| ---------------------------------------------------------- | ------- |
| BLE protocol design (advertising, scanning, ID management) | 15      |
| Encounter logging and proximity estimation logic           | 15      |
| RSSI–distance calibration and exposure analysis            | 20      |
| Energy measurement and optimization                        | 20      |
| Statistical analysis and experimental rigor                | 15      |
| Final report quality, figures, and code documentation      | 15      |
| **Total**                                                  | **100** |

# Project P2 – LoRaWAN Interactive Peer-Messaging Service

## 📡 Project Overview

In large-scale sensor deployments using LoRaWAN, devices can only receive downlink messages immediately following their own uplinks. This constraint complicates direct communication between devices. In this project, you will implement a lightweight, asynchronous messaging protocol where any device can initiate a communication session with another peer by interacting with a centralized application server using the **2 TTGO LoRa32 boards provided to your team**.

The system works as follows:

1. All devices periodically send **keepalive uplinks** (e.g., every 60–120 seconds) to indicate they are active.
2. These uplinks are collected by the application server (Python script subscribed to the TTN MQTT feed), which maintains a dynamic list of recently seen device IDs.
3. Any device can initiate communication by sending a **DISCOVER uplink**, requesting the current list of active device IDs.
4. The application server responds with a **ROSTER downlink** containing this list. The ROSTER is a compact message structure encoding the IDs of devices that have recently sent uplinks (i.e., are active and reachable). It allows the requesting node to select a viable recipient for its next COMMAND message.
5. The requesting device selects a target and sends a **COMMAND uplink**, referencing the target ID and message.
6. The network server buffers the command and delivers it to the target device during its next downlink window (RX1 or RX2) following its next uplink.
7. The target device may optionally respond with an ACK or application-level response during its next scheduled uplink.

This architecture allows peer-like communication within the strict timing and energy constraints of LoRaWAN. You will evaluate this system's performance across several dimensions, including delay, delivery reliability, false message rates, and energy consumption, analyzing the system's responsiveness and reliability under realistic constraints, including duty cycle, downlink scheduling, spreading factor variation, and message queuing delay.

---

## 🧪 Project Features and Evaluation Goals

### Core Functionality

* Any device periodically sends a DISCOVER uplink to request the list of active nodes
* The application server receives the uplink via MQTT and responds with a downlink ROSTER message
* The originating device parses the ROSTER and sends a targeted COMMAND uplink referencing a selected device ID
* The network server buffers the COMMAND and delivers it as a downlink to the target device during its next RX1 or RX2 window
* Target devices may optionally respond with an ACK uplink or a status report

### Experimental Evaluation

* **Roster discovery performance**:
  * Log number of devices discovered vs expected
  * Analyze false negatives or missed targets
* **Command delivery reliability**:
  * Measure successful command delivery ratio across multiple attempts
  * Quantify effect of transmission interval and spreading factor
* **End-to-end delay**:
  * Compute time from DISCOVER to ROSTER reception and from command to ACK
* **Energy profiling and trade-off analysis**:
  * Use the [Semtech LoRa Calculator](https://www.semtech.com/design-support/lora-calculator) to estimate energy consumption and time-on-air for different payload sizes and spreading factors
  * Explore how varying the **polling interval** of target nodes (i.e., their uplink frequency) affects:
    * Message delivery latency
    * Buffer retention time at the network server
    * Average energy cost per device
  * Quantify the trade-offs between lower latency (frequent uplinks) and energy efficiency (longer sleep intervals)
  * Estimate average power consumption under different polling intervals and SFs

---

## 📦 Required Deliverables

| Component               | Description                                                                | Verification Criteria |
| ----------------------- | -------------------------------------------------------------------------- | --------------------- |
| `README.txt`            | Team info, setup instructions, file structure (see general requirements)  | Complete template fields, clear instructions |
| `firmware/`             | Source code for all participating LoRaWAN nodes (DISCOVER + COMMAND logic) | Code compiles, well-commented, implements messaging protocol |
| `data/`                 | CSV logs: message timestamps, target IDs, success/failure, SF, RSSI        | Minimum 30 data points per condition, proper CSV format |
| `plots/`                | Roster accuracy, delivery success rate, end-to-end delay graphs            | Clear labels, appropriate scales, statistical annotations |
| `report.pdf`            | 3-6 pages: architecture, experiments, analysis, limitations               | Follows scientific report structure, includes required sections |
| `demo.mp4` *(optional)* | Short walkthrough of interaction and debugging output                      | Clear demonstration of working system |

---

## 📊 Evaluation Criteria

| Category                                            | Points  |
| --------------------------------------------------- | ------- |
| DISCOVER and peer messaging functionality           | 15      |
| ROSTER parsing and device discovery accuracy        | 15      |
| End-to-end delay and delivery evaluation            | 20      |
| False positives/negatives and message loss analysis | 20      |
| Statistical analysis and experimental rigor         | 15      |
| Final report quality, figures, and code documentation | 15      |
| **Total**                                           | **100** |