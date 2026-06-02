# GPS Log Examples — REL18_TO_REL24.log

Real log line format observed from the FALCON device running AIS140/TMLCVP firmware.

---

## Log Line Format

```
[YYYY-MM-DD HH:MM:SS.mmm] INFO:  [PLA] GPS     RX <sat>,DT <date>,TM <utc_time>,LAT <lat>,LAT DIR <dir>,LONG <long>,LONG DIR <dir>,FIX QUA <fix>,SAT <sat_count>,ALT <alt>,PDOP <pdop>,HDOP <hdop>,VDOP <vdop>,SPEED_KMPH <speed>,HEADING DEG <heading>
```

---

## Example 1: No Fix (Anomaly State)

```
[2026-05-13 15:21:57.201] INFO:  [PLA] GPS     RX 322,DT 060180,TM 000123,LAT 0.000000,LAT DIR -,LONG 0.000000,LONG DIR -,FIX QUA 0,SAT 0,ALT 0.000000,PDOP 0.000000,HDOP 0.000000,VDOP 0.000000,SPEED_KMPH 0.00,HEADING DEG 0.00
```

**Interpretation:**
- `FIX QUA 0` → No GPS lock acquired
- `SAT 0` → Zero satellites visible
- `LAT 0.000000` / `LONG 0.000000` → Default/invalid coordinates
- **Anomaly Rules Triggered:** GPS_001 (no fix), GPS_002 (sat=0), GPS_003 (zero coords)

---

## Example 2: Valid Fix (Normal State)

```
[2026-05-13 16:30:00.000] INFO:  [PLA] GPS     RX 322,DT 130526,TM 110000,LAT 18.516726,LAT DIR N,LONG 73.856255,LONG DIR E,FIX QUA 1,SAT 8,ALT 560.000000,PDOP 1.200000,HDOP 0.900000,VDOP 0.800000,SPEED_KMPH 0.00,HEADING DEG 270.00
```

**Interpretation:**
- `FIX QUA 1` → Valid GPS lock
- `SAT 8` → 8 satellites (strong signal, >= 4 is acceptable)
- `LAT 18.516726 N` / `LONG 73.856255 E` → Valid Pune, India coordinates
- All anomaly rules pass ✅

---

## Raw $GPS Short Format (also present in logs)

```
[2026-05-13 15:19:19.455] $GPS,1030,000000,0,0.000000,0.000000,0
```

**Field mapping:** `$GPS,<sat>,<utc_time>,<fix_quality>,<lat>,<long>,<speed>`

---

## GPSL Context Events

```
[2026-05-13 15:21:54.169] WARNING: GPSL context 'AIS140_PRIMARY' going for repair (data may be lost)!
[2026-05-13 15:21:54.193] WARNING: GPSL context 'AIS140_PRIMARY' going for reset (data will be lost)!
[2026-05-13 15:21:54.210] INFO: GPSL context 'AIS140_PRIMARY' was initialized by reset.
```

**Interpretation:** GPS library context reset — typically triggered after prolonged no-fix state to attempt re-acquisition.

---

## Field Reference

| Field        | Type    | Valid Range              | Anomaly When          |
|:-------------|:--------|:-------------------------|:----------------------|
| FIX QUA      | int     | 0 (no fix) or 1 (valid)  | == 0 after 120 sec    |
| SAT          | int     | 0 – 32                   | == 0 (critical)       |
| LAT          | float   | -90.0 to 90.0            | == 0.000000           |
| LONG         | float   | -180.0 to 180.0          | == 0.000000           |
| SPEED_KMPH   | float   | 0.0 – 180.0              | < 0 or > 180          |
| HDOP         | float   | < 2.0 ideal              | > 5.0 poor accuracy   |
| ALT          | float   | meters above sea level   | Unexpected negatives  |
