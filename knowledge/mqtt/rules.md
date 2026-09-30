# MQTT Rules

## Purpose
This file defines MQTT-specific analysis rules for the message broker domain. Rules help detect connectivity issues, latency problems, and common broker failures.

## Rule Definitions
- `MQTT_KN_001`: Detects broker disconnection by checking the MQTT connection status.
- `MQTT_KN_002`: Detects high latency when message round-trip delay exceeds threshold.

## Guidance
Keep MQTT rules focused on connectivity, timing, and broker health. Combine them with parameter validation to create precise anomaly findings.
