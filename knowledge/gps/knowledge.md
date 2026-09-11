# GPS Domain Knowledge

Version: 1.0
Role: GPS Expert Knowledge Base
Scope: FALCON AIS140/TMLCVP Telemetry

---

# Purpose

Provides GPS behavior understanding, known issues, baseline expectations, and troubleshooting guidance.
Supports AI reasoning and behavioral context (non-deterministic patterns).

---

# GPS Fundamentals

## Fix Quality Levels
- **0** = No Fix
- **1** = Valid Fix

## Satellite Count Classification
- **0-3**: Weak acquisition (poor positioning)
- **4-7**: Acceptable (minimum operational)
- **≥8**: Strong GPS health (high confidence)

---

# Baseline Expectations (from REL18-REL24 logs)

## Cold Start (Power-on from 0% state)
- Expected fix time: 60–120 seconds
- Expected satellite count: 5–15
- Allow 30–120 sec stabilization window

## Hot Start (Resume from valid state)
- Expected fix time: 10–30 seconds
- Expected satellite count: ≥5

## Log Sequence (Normal Operation)
```
GPS RX, FIX QUA 0, SAT 0     (boot phase)
  ↓ (30-120 sec stabilization)
GPS RX, FIX QUA 1, SAT ≥5, LAT ≠0, LONG ≠0   (ready)
```

---

# Known Field Trial Behaviors

### During Boot
Expected transient state:
- SAT may remain 0
- FIX QUA may remain 0
- LAT/LONG may remain 0.000000

**Action:** Do NOT raise anomaly immediately. Allow stabilization window (30–120 sec).

---

# Known Failure Patterns (with Root Causes)

## GPS_KN_001: No Satellite Acquisition
**Pattern:** SAT=0, FIX=0 (persistent after 120+ sec)

**Interpretation:** GPS receiver cannot see satellites.

**Root Causes:**
- Antenna disconnected or damaged
- Indoor/enclosed location (no sky view)
- GPS RF interference
- Receiver hardware failure

**Confidence:** High

---

## GPS_KN_002: Satellite Visible but No Fix
**Pattern:** SAT≥4, FIX=0 (persistent)

**Interpretation:** Satellites visible but receiver cannot establish lock.

**Root Causes:**
- Timing synchronization issue
- GPS software stack bug
- Receiver initialization incomplete
- Firmware incompatibility

**Confidence:** High

---

## GPS_KN_003: Invalid Coordinates
**Pattern:** FIX=1 but LAT=0.000000 and LONG=0.000000

**Interpretation:** Fix claimed but coordinates default/corrupted.

**Root Causes:**
- UART parser error
- Data corruption in transmission
- Coordinate extraction logic bug

**Confidence:** High

---

## GPS_KN_004: Low Satellite Count
**Pattern:** SAT < 4 (for extended periods)

**Interpretation:** Poor satellite visibility.

**Root Causes:**
- Weak RF signal (indoor, obstructed)
- Antenna position suboptimal
- Multipath interference
- Atmospheric conditions

**Confidence:** Medium

Medium

---

# Known Failure Pattern GPS_KN_003

Pattern:

FIX=1
LAT=0
LONG=0

Interpretation:

GPS fix exists but coordinates invalid.

Likely parser or payload issue.

Confidence:

High

---

# Known Failure Pattern GPS_KN_004

Pattern:

Sudden coordinate jump

Interpretation:

GPS drift or corrupted parsing.

Possible Causes:

- noisy RF
- parsing corruption
- timestamp mismatch

Confidence:

Medium

---

# Field Trial Notes

Temporary GPS degradation:

Acceptable:

- tunnels
- dense urban area
- parking basement

Do not classify immediately as failure.

Context awareness required.

---

# Recommendation Logic

If:

SAT=0
AND
FIX=0

Recommend:

- inspect antenna
- verify sky visibility

If:

FIX=1
AND
LAT=0

Recommend:

- parser verification
- payload validation