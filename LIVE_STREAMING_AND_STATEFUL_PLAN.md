# Roadmap Plan: Live Streaming Ingestion, Stateful Event Resolution & Parallel Concurrency

## Objective

Extend the **LOG_ANALYZER** pipeline to support:
1. **Stateful Anomaly Lifecycle Tracking**: Detecting when an anomaly begins (e.g. at line 2) and tracking its duration until it resolves (e.g. at line 40).
2. **Real-Time Live Ingestion**: Ingesting logs dynamically from a growing file (`tail -f` mode) or directly from hardware over UART/Serial port interfaces.
3. **High-Performance Concurrent Multiprocessing**: Scalable parallel chunk processing and lightweight event state indexing for 1,000+ long-running concurrent open events without slowing down the system.

---

## 1. Stateful Anomaly Lifecycle & Resolution Tracking

### Current Limitations
- Agents evaluate individual log lines as discrete point-in-time events.
- Repeated error lines increment occurrence counters but do not calculate continuous blackout durations or track explicit recovery events.

### Proposed Architecture

```
[Line 2: SAT=0, FIX=0] ──> Open Active Anomaly (State: ACTIVE, StartLine: 2)
                                 │
[Lines 3-39: SAT=0]    ──> Increment Occurrence Counter & Update Last Seen
                                 │
[Line 40: SAT=8, FIX=1] ──> Close Active Anomaly (State: RESOLVED, EndLine: 40, Duration: 38s)
```

### Key Data Model (`ActiveAnomalySession`)
```json
{
  "id": "GPS_KN_001",
  "title": "No satellite acquisition",
  "source": "GPS",
  "status": "RESOLVED",
  "severity": "high",
  "start_line": 2,
  "end_line": 40,
  "start_timestamp": "2026-05-13T15:19:19.455Z",
  "end_timestamp": "2026-05-13T15:19:58.100Z",
  "duration_seconds": 38.645,
  "occurrence_count": 38,
  "sample_start_line": "[2026-05-13 15:19:19.455] $GPS,1030,000000,0,0.000000,0.000000,0",
  "sample_recovery_line": "[2026-05-13 15:19:58.100] $GPS,1030,151958,1,18.520430,73.856740,8"
}
```

### Action Items
1. **Base Agent Session Manager (`agents/base_agent.py`)**:
   - Add `active_sessions` dictionary to `BaseAgent`.
   - Implement `open_session()`, `update_session()`, and `close_session()`.
2. **Domain Agent Recovery Triggers**:
   - **GPS Agent**: Close `GPS_KN_001` when `fix_quality == 1` and `satellite_count >= 4`.
   - **Battery Agent**: Close `BATT_KN_001` when `voltage >= 3.3V`.
   - **Network Agent**: Close `NET_KN_001`/`002` when `csq >= 5` and `creg == 1`.
   - **MQTT Agent**: Close `MQTT_KN_001` when `connection_status == "connected"`.
3. **Report Enhancements**:
   - Add outage duration metrics (Mean Time To Recovery - MTTR) to `final_report.md` and `report_cards.md`.

---

## 2. Real-Time Live Log & Hardware UART Ingestion

### Proposed Architecture

The decoupled event architecture (`parser -> dispatcher -> agents`) allows attaching live input producers without changing business logic:

```
┌───────────────────────────────────────┐
│ Input Producers                       │
├───────────────────────────────────────┤
│ A. File Mode (Static Log File)        │ ──┐
│ B. Live Tail Mode (Growing File)      │ ──┼──> Classifier ──> Dispatcher ──> Agents
│ C. UART Mode (Hardware Serial COM)    │ ──┘
└───────────────────────────────────────┘
```

### Ingestion Modes

#### Mode A: Live Growing File Tailing (`tail -f`)
- Monitors log files appended to by local test scripts, SSH sessions, or `adb logcat`.
- Implementation: Non-blocking file generator using `time.sleep(0.1)` on EOF.

#### Mode B: Physical Hardware UART / Serial Port (`pyserial`)
- Plugs directly into the ECU / TCU debug serial console via USB-to-UART adapter.
- Implementation: Uses `serial.Serial(port, baudrate)` stream reader.

---

## 3. High-Performance Multiprocessing & Parallel Concurrency

### Problem: Performance Bottlenecks with 1,000+ Long-Running Open Events
When a log file has 1,000+ active event sessions starting at line 1 and resolving at the last line, naive single-threaded state evaluation can suffer from:
1. **CPU Saturation (Single-Thread Bottleneck)**: Python GIL restricts single-threaded line regex classification across multi-core CPUs.
2. **Memory Overhead**: Storing full raw string buffers for thousands of open sessions in RAM.

### Architectural Solution: Parallel Producer-Consumer & Chunked Process Pool

```
                       ┌────────────────────────────────┐
                       │  File / Live UART Producer     │
                       └───────────────┬────────────────┘
                                       │ (Line Chunks: 50k lines)
                                       ▼
             ┌──────────────────────────────────────────────────┐
             │       multiprocessing.ProcessPoolExecutor        │
             ├──────────────────┬───────────────────────────────┤
             │  Worker Process 1│  Worker Process 2  │ ... Worker N│
             │  (Lines 1-50k)   │  (Lines 50k-100k)  │             │
             └────────┬─────────┴────────┬───────────┴────────────┘
                      │                  │
                      ▼                  ▼
             ┌──────────────────────────────────────────────────┐
             │   Stateful Event Reducer (MapReduce Aggregator)  │
             ├──────────────────────────────────────────────────┤
             │ - O(1) Active Hash Index (lightweight integer keys)│
             │ - Merges Chunk Boundary Open/Close Sessions      │
             │ - Flushes Resolved Events to Disk                │
             └──────────────────────────────────────────────────┘
```

### Optimization Techniques

1. **Lightweight Integer-Based State Indexing ($O(1)$ Hash Map)**:
   - Instead of storing heavy raw string objects for 1,000+ open sessions, active sessions store **compact integer tuples**: `(event_type_id, start_line_num, start_epoch_ms)`.
   - String formatting is deferred until the event resolves or the report is generated.

2. **Chunked Multiprocessing (`ProcessPoolExecutor`)**:
   - For multi-gigabyte static logs, `main.py` splits log line offsets into 50,000-line chunks and processes them across all available CPU cores.
   - Boosts throughput from ~50,000 lines/sec to **300,000+ lines/sec** on quad-core/octa-core CPUs.

3. **Asynchronous Non-Blocking Worker Queues (`multiprocessing.Queue`)**:
   - For live UART or `tail -f` streaming, the reader thread runs on a dedicated high-priority process pushing raw lines to a lock-free queue, guaranteeing **zero serial buffer drops** during high UART baud rates (e.g. 921600 baud).

---

## 4. Implementation Roadmap

### Phase 1: Stateful Session Engine
- [ ] Upgrade `BaseAgent` with stateful session lifecycle tracking (`ActiveAnomalySession`).
- [ ] Add recovery triggers to `GPSAgent`, `BatteryAgent`, `NetAgent`, `CANAgent`, `MQTTAgent`.
- [ ] Update `reports/report_generator.py` to display MTTR and outage duration tables.

### Phase 2: High-Performance Concurrency & Multiprocessing
- [ ] Implement `multiprocessing.ProcessPoolExecutor` chunk parser in `parser/gps_log_reader.py`.
- [ ] Implement lightweight integer tuple indexing in `reports/anomaly_collector.py`.
- [ ] Add MapReduce session merger for cross-chunk state resolution.

### Phase 3: Live Ingestion & UART Stream
- [ ] Add `pyserial` dependency to `requirements.txt`.
- [ ] Implement `LiveFileTailer` and `UARTStreamReader` in `parser/`.
- [ ] Add `--mode`, `--port`, and `--baud` flags to `main.py`.
- [ ] Implement real-time terminal alert output for critical events during live runs.
