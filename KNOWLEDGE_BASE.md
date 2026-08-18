# LOG_ANALYZER Comprehensive Knowledge Base & Telemetry Specification

## 1. Subsystem Architecture & Log Classification

The **LOG_ANALYZER** ingests multi-domain telemetry traces from Telematics Control Units (TCUs), Vehicle Tracking Units, and Electronic Control Units (ECUs). Log entries are classified into 5 core subsystems:

```
                          ┌──────────────────────────┐
                          │   Classifier Regexes     │
                          └────────────┬─────────────┘
                                       │
     ┌──────────────┬──────────────┬───┴──────────┬──────────────┐
     ▼              ▼              ▼              ▼              ▼
  [ GPS ]       [ BATTERY ]     [ CAN ]        [ NET ]        [ MQTT ]
```

---

## 2. Telemetry Syntax & Format Specifications

The parser recognizes two primary log formats:

### Format A: ATCU Snapshot NMEA-style Format (`$TAG`)
Generated during boot, periodic heartbeats, or status polling:
- **`$GPS,<message_id>,<utc_time>,<fix_quality>,<latitude>,<longitude>,<satellite_count>`**
  - Example: `[2026-05-13 15:19:19.455] $GPS,1030,000000,0,0.000000,0.000000,0`
- **`$GSM,<csq>,<creg>,<cgreg>,<tcp_skt>,<mqtt_count>,"<operator>",...`**
  - Example: `[2026-05-13 15:19:19.455] $GSM,0,0,0,0,0,"no service",-,0,0`
- **`$ANALOG,<ext_batt>,<int_batt>,<tmpr>,<an1>,<an2>`**
  - Example: `[2026-05-13 15:19:19.445] $ANALOG,0.00,23.60,0,0.00,24.63`
- **`$CAN2,<bus_state>,<error_flag>`**
  - Example: `[2026-05-13 15:19:19.471] $CAN2,1,0`

### Format B: Component Execution Format (`[PLA]`, `[NET]`, `[CAN]`)
Generated during active firmware module execution:
- **GPS Component**: `[2026-05-13 15:22:00] INFO: [PLA] GPS RX FIX QUA 0 SAT 0 LAT 0.000000 LONG 0.000000`
- **Battery Component**: `[2026-05-13 15:22:00] INFO: [PLA] ANALOG INT BATT 3.35V 14.66 PERCENT, TMPR 0`
- **Network Component**: `[2026-05-13 15:22:00] DEBUG: [NET] CSQ 18 CREG 1 CGREG 1`
- **CAN/UDS Component**: `[2026-05-13 15:22:00] ERROR: [PLA] UDS Session Timeout`

---

## 3. Subsystem Knowledge Rule Matrix & Anomaly IDs

| Subsystem | Anomaly Rule ID | Trigger Condition | Severity | Root Cause / Remediation Strategy |
| :--- | :--- | :--- | :--- | :--- |
| **GPS** | `GPS_KN_001` | `SAT == 0` and `FIX == 0` | High | Satellite signal occlusion or antenna disconnect. Re-orient GPS antenna. |
| **GPS** | `GPS_KN_002` | `SAT >= 4` and `FIX == 0` | High | Satellites visible but fix not acquired. Check GPS cold-boot search timeouts. |
| **GPS** | `GPS_KN_004` | `0 < SAT < 4` | Medium | Weak satellite reception (<4 satellites). Check sky visibility. |
| **BATTERY** | `BATT_KN_001` | `Voltage < 3.0V` | High | Battery voltage drop / cell degradation. Inspect battery charging circuit. |
| **BATTERY** | `BATT_KN_002` | `Temperature > 50°C` | High | Battery thermal threshold breached (>50°C). Verify cooling & thermal pad. |
| **CAN** | `CAN_KN_001` | `UDS Session Timeout` | High | UDS diagnostic session timeout. Check ECU CAN transceiver stability. |
| **CAN** | `CAN_KN_002` | `DTC Code 0x...` | Critical | Diagnostic Trouble Code reported by ECU. Review fault code dictionary. |
| **NET** | `NET_KN_001` | `CSQ < 5` | Medium | Poor cellular signal quality (CSQ < 5). Check LTE/GSM antenna connection. |
| **NET** | `NET_KN_002` | `CREG == 0` | High | GSM network registration failed. Verify SIM card attachment and credentials. |
| **NET** | `NET_KN_003` | `CGREG == 0` | High | GPRS packet data registration failed. Verify APN settings. |
| **NET** | `NET_KN_004` | `Operator Missing` | Low | SIM operator name missing. Confirm operator network availability. |
| **NET** | `NET_KN_005` | `TCP == 0 & MQTT == 0` | Medium | No active socket or telemetry traffic. Check mobile data connection. |
| **MQTT** | `MQTT_KN_001` | `Status == disconnected` | High | MQTT broker disconnected. Verify server keepalive and TLS certificates. |
| **MQTT** | `MQTT_KN_002` | `Latency > 5000 ms` | Medium | High MQTT packet latency (>5 sec). Improve network QoS or message size. |

---

## 4. Parameter Specs & Range Configurations

All valid thresholds are externalized in `knowledge/<subsystem>/parameters.yaml`:

### GPS Domain (`knowledge/gps/parameters.yaml`)
- `fix_quality`: valid range `[0, 1]` (0=No Fix, 1=Valid Fix)
- `satellite_count`: valid range `[0, 32]` (Thresholds: weak `[0, 3]`, acceptable `[4, 7]`, strong `[8, 32]`)
- `latitude`: valid range `[-90.0, 90.0]` (invalid at `0.0` when fix=1)
- `longitude`: valid range `[-180.0, 180.0]` (invalid at `0.0` when fix=1)
- `hdop`: valid range `[0.5, 50.0]` (excellent `<2.0`, good `<5.0`, poor `>5.0`)

### Battery Domain (`knowledge/battery/parameters.yaml`)
- `voltage`: valid range `[3.0V, 4.2V]`
- `state_of_charge`: valid range `[0.0%, 100.0%]`
- `temperature`: valid range `[-20°C, 50°C]`

---

## 5. System Execution Modes & Commands

| Execution Mode | Command Example | Use Case |
| :--- | :--- | :--- |
| **Static File Analysis** | `python main.py --log-file logs/REL18_TO_REL24.log` | Flash release testing & FOTA regression log triage. |
| **Live File Tailing** | `python main.py --mode tail --log-file logs/live.log` | Monitoring active test logs dynamically written to disk. |
| **Hardware UART Stream** | `python main.py --mode uart --port COM3 --baud 115200` | Real-time debug streaming from ECU hardware via USB-to-UART. |

---

## 6. Global Configuration Schema (`config.yaml`)

```yaml
paths:
  log_dir: "logs"
  artifact_dir: "artifacts"
  default_log_file: "logs/REL18_TO_REL24.log"
  raw_anomalies_json: "artifacts/raw_anomalies.json"
  report_cards_md: "artifacts/report_cards.md"
  final_report_md: "artifacts/final_report.md"
  ai_summary_md: "artifacts/ai_summary.md"

uart:
  default_port: "COM3"
  default_baudrate: 115200
  timeout: 1.0

live_tail:
  poll_interval: 0.1
  stop_on_idle_sec: 5.0

ai:
  model: "gemini-2.5-flash"
  api_url: "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
```
