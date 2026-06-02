# CAN Rules

## Purpose
This file stores domain-specific rules for CAN telemetry analysis. Rules are structured to support automated anomaly detection and explainable root cause reasoning.

## Rule Definitions
- `CAN_KN_001`: Engine overheating detected when engine temperature is above safe threshold.
- `CAN_KN_002`: Engine stall detected when RPM drops below idle while vehicle speed remains greater than zero.

## Guidance
Use these rules to validate parameter values and produce actionable anomaly findings in CAN message streams.
