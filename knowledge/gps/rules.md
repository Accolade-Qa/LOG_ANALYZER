# GPS Rules Specification

Version: 1.0
Owner: Telemetry Validation Team
Parameter Domain: GPS
Priority: High

---

# Purpose

Defines deterministic validation rules for GPS telemetry (pass/fail conditions).
Must be applied during log analysis phase.

---

# Required GPS Fields (R-001)

**Rule ID:** R_GPS_001  
**Name:** Required Fields Check  
**Severity:** HIGH  
**Category:** Missing Telemetry

**Required Fields:**
- GPS RX (message marker)
- LAT (latitude)
- LONG (longitude)
- FIX QUA (fix quality)
- SAT (satellite count)
- SPEED_KMPH (velocity)
- UTC (time)

**Condition:** All fields present in message

**Action if Failed:**
- Report missing field(s)
- Mark as "Incomplete Telemetry"
- Severity: HIGH

---

# Rule GPS_001: Fix Acquisition Timeout

**Rule ID:** GPS_001  
**Name:** GPS Fix Acquisition  
**Severity:** HIGH

**Condition:**
```
FIX QUA must become 1 within 120 seconds of boot
```

**Pass Criteria:**
- FIX QUA == 1 at timestamp ≤120 sec from boot

**Fail Criteria:**
- FIX QUA remains 0 after 120 sec elapsed

**Recommended Actions:**
1. Check antenna connection
2. Verify clear sky visibility (no obstructions)
3. Check GPS receiver initialization logs
4. Inspect for RF interference
5. Verify firmware loaded correctly

---

# Rule GPS_002: Satellite Availability

**Rule ID:** GPS_002  
**Name:** Satellite Visibility  
**Severity:** MEDIUM

**Thresholds:**
| Range | Status | Action |
|-------|--------|--------|
| SAT ≥ 8 | ✅ Strong | Normal operation |
| 4 ≤ SAT < 8 | ✅ Acceptable | Proceed with caution |
| 1 ≤ SAT < 4 | ⚠️ Warning | Check antenna/sky view |
| SAT = 0 | ❌ Fail | Critical - No satellites |

**Pass Condition:** SAT ≥ 4

**Fail Condition:** SAT = 0 (persistent)

**Recommended Actions:**
1. Inspect antenna for damage
2. Reposition antenna for clear sky view
3. Check for RF interference sources
4. Verify GPS module power supply

---

# Rule GPS_003: Coordinate Validity

**Rule ID:** GPS_003  
**Name:** Coordinate Sanity Check  
**Severity:** MEDIUM

**Condition:**
```
IF (FIX QUA == 1) THEN (LAT ≠ 0.0 AND LONG ≠ 0.0)
```

**Pass Criteria:**
- FIX QUA == 0 (no fix claimed, zero coords acceptable)
- OR FIX QUA == 1 AND (LAT ≠ 0.0 AND LONG ≠ 0.0)

**Fail Criteria:**
- FIX QUA == 1 AND (LAT == 0.0 OR LONG == 0.0)

**Recommended Actions:**
1. Check UART parser for bit errors
2. Verify serial connection integrity
3. Check for data corruption in transit
4. Inspect GPS receiver output format

---

# Rule GPS_004: Speed Range Validation

**Rule ID:** GPS_004  
**Name:** Speed Bounds Check  
**Severity:** MEDIUM

**Valid Range:** 0.0 – 180.0 km/h

**Fail Conditions:**
- SPEED_KMPH < 0 (impossible)
- SPEED_KMPH > 180 (beyond vehicle capability)

**Recommended Actions:**
1. Check for sign bit corruption
2. Verify speed calculation logic
3. Inspect for integer overflow

---

# Rule GPS_005: Accuracy Metric (HDOP)

**Rule ID:** GPS_005  
**Name:** Horizontal Dilution of Precision  
**Severity:** LOW

**Standards:**
- HDOP < 2.0 → Excellent accuracy
- 2.0 ≤ HDOP < 5.0 → Good accuracy
- HDOP ≥ 5.0 → Poor accuracy (degraded)

**Action if Degraded (HDOP > 5.0):**
- Flag for manual review
- Not critical but indicates weak geometry

---

# Rule GPS_006: Altitude Sanity

**Rule ID:** GPS_006  
**Name:** Altitude Bounds Check  
**Severity:** LOW

**Valid Range:** 0 to 8,848 meters (Mt. Everest)

**Fail Condition:**
- ALT < 0 (impossible - below sea level in most cases)
- ALT > 9,000 (unrealistic for vehicle)

**Recommended Actions:**
1. Check altitude extraction logic
2. Verify for data type conversion errors
3. Inspect receiver altitude output format

---

# Rule GPS_003

Rule ID: GPS_003
Name: Coordinate Validity

Expected:

LAT !=0
LONG !=0

Pass:

Non-zero coordinates

Fail:

LAT=0
OR
LONG=0

Severity:

HIGH

Recommended Action:

- Validate GPS parser
- Check NMEA decoding

---

# Rule GPS_004

Rule ID: GPS_004
Name: Coordinate Stability

Expected:

Coordinates should not jump abruptly.

Threshold:

Distance jump <=500 m between consecutive samples.

Fail:

Sudden jump >500 m

Severity:

MEDIUM

Recommended Action:

- Check GPS drift
- Check parser corruption

---

# Rule GPS_005

Rule ID: GPS_005
Name: Speed Validity

Expected:

GPS speed should be realistic.

Threshold:

0–180 kmph

Fail:

Negative speed
OR
Unrealistic speed

Severity:

MEDIUM

Recommended Action:

- Validate GPS payload parsing