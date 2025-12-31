# Thermal-Controlled Fan Setup

Automatically control Group 1 (heat sink) fans based on Raspberry Pi 5 CPU temperature, following the same logic as the Pi's active cooler.

## Overview

The Pi 5's active cooler operates in 5 states based on CPU temperature:

| Temperature | Pi Fan State | Default Group 1 Speed |
|-------------|--------------|----------------------|
| < 50°C      | 0 (Off)      | 0%                   |
| 50-60°C     | 1 (Low)      | 30%                  |
| 60-67.5°C   | 2 (Med-Low)  | 50%                  |
| 67.5-75°C   | 3 (Med-High) | 70%                  |
| > 75°C      | 4 (Full)     | 100%                 |

## Two Control Modes

### Mode 1: Follow Pi Fan State (Discrete)
Reads the Pi's cooling device state and maps it directly to fan speed.

**Pros:**
- Exactly matches Pi behavior
- Simple and predictable
- Uses proven thermal management logic

**Cons:**
- Only 5 discrete speeds (steps)
- Fans may change speed noticeably

### Mode 2: Smooth Temperature Curve (Continuous)
Reads CPU temperature directly and uses continuous curves for smoother transitions.

**Pros:**
- Smooth speed transitions
- Less noticeable speed changes
- More responsive to small temp changes

**Cons:**
- Custom curve (not identical to Pi)

## Usage

### Basic Usage (Recommended)

Run with smooth temperature curve:
```bash
sudo /home/mover/.octa/bin/python3 thermal_fan_controller.py
```

This will:
- Group 1 (heat sink): AUTO - follows CPU temperature
- Group 2 (air sampling): OFF - manual control

### Follow Pi Fan State

To exactly match Pi's fan behavior:
```bash
sudo /home/mover/.octa/bin/python3 thermal_fan_controller.py --mode state
```

### Control Group 2 While Running

Set Group 2 (air sampling) to run at fixed speed:
```bash
sudo /home/mover/.octa/bin/python3 thermal_fan_controller.py --group2 75
```

This runs:
- Group 1: AUTO (thermal-controlled)
- Group 2: 75% (constant)

### Adjust Update Interval

Check temperature every 5 seconds (default is 2s):
```bash
sudo /home/mover/.octa/bin/python3 thermal_fan_controller.py --interval 5
```

### All Options Combined

```bash
sudo /home/mover/.octa/bin/python3 thermal_fan_controller.py \
    --mode temp \
    --interval 2 \
    --group2 80
```

## Output Example

```
======================================================================
Thermal Fan Controller - Raspberry Pi 5
======================================================================
Dual-group fan controller initialized:
  Group 1 (Heat Sink):   GPIO12, GPIO18
  Group 2 (Air Sampling): GPIO13, GPIO19
  PWM Frequency: 25000 Hz

Thermal Fan Controller initialized:
  Mode: Smooth temperature curve
  Update interval: 2.0s
  Group 1: AUTO (thermal-controlled)
  Group 2: MANUAL

Starting thermal monitoring...
Press Ctrl+C to stop

Temp:  51.2°C | Group 1:  12% | Group 2:   0%
Temp:  52.8°C | Group 1:  24% | Group 2:   0%
Temp:  54.5°C | Group 1:  36% | Group 2:   0%
Temp:  61.3°C | Group 1:  52% | Group 2:   0%
...
```

## Running as a Service

To run thermal control automatically at boot, create a systemd service:

### 1. Create Service File

```bash
sudo nano /etc/systemd/system/thermal-fan-control.service
```

Add:
```ini
[Unit]
Description=Thermal-Controlled Case Fans
After=multi-user.target

[Service]
Type=simple
User=root
WorkingDirectory=/home/mover/octa/src/fan
ExecStart=/home/mover/.octa/bin/python3 thermal_fan_controller.py --mode temp --group2 0
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 2. Enable and Start

```bash
sudo systemctl daemon-reload
sudo systemctl enable thermal-fan-control.service
sudo systemctl start thermal-fan-control.service
```

### 3. Check Status

```bash
sudo systemctl status thermal-fan-control.service
```

### 4. View Logs

```bash
sudo journalctl -u thermal-fan-control.service -f
```

## Customizing Temperature Curves

Edit `thermal_fan_controller.py` and modify the `temp_to_percent_smooth()` function:

```python
@staticmethod
def temp_to_percent_smooth(temp):
    """Custom temperature curve."""
    if temp < 45.0:
        return 0
    elif temp < 55.0:
        return int((temp - 45.0) / 10.0 * 40)  # 0-40% between 45-55°C
    elif temp < 70.0:
        return int(40 + (temp - 55.0) / 15.0 * 30)  # 40-70% between 55-70°C
    else:
        return min(100, int(70 + (temp - 70.0) / 10.0 * 30))  # 70-100% above 70°C
```

Or adjust the `STATE_TO_PERCENT` mapping:

```python
STATE_TO_PERCENT = {
    0: 0,      # Off
    1: 40,     # Low (was 30%)
    2: 60,     # Medium-low (was 50%)
    3: 80,     # Medium-high (was 70%)
    4: 100,    # Full speed
}
```

## Monitoring Temperature

### Check Current Temperature
```bash
cat /sys/class/thermal/thermal_zone0/temp | awk '{print $1/1000 "°C"}'
```

Or:
```bash
vcgencmd measure_temp
```

### Check Pi Fan State
```bash
cat /sys/class/thermal/cooling_device0/cur_state
```

### Watch Temperature in Real-Time
```bash
watch -n 1 'vcgencmd measure_temp'
```

## Troubleshooting

### Fans don't respond to temperature changes

Check if thermal monitoring is working:
```bash
cat /sys/class/thermal/thermal_zone0/temp
cat /sys/class/thermal/cooling_device0/cur_state
```

### Permission errors

Make sure to run with `sudo` (needed for PWM control).

### Fans stay at same speed

1. Check Pi temperature is actually changing:
   ```bash
   vcgencmd measure_temp
   ```

2. Load the CPU to test:
   ```bash
   stress-ng --cpu 4 --timeout 30s
   ```

3. Watch the thermal controller output - speeds should increase

### Service won't start

Check logs:
```bash
sudo journalctl -u thermal-fan-control.service -n 50
```

Verify Python path:
```bash
which python3
ls -la /home/mover/.octa/bin/python3
```

## Command Reference

```bash
# Run with smooth curve (recommended)
sudo python3 thermal_fan_controller.py

# Follow Pi fan exactly
sudo python3 thermal_fan_controller.py --mode state

# Set Group 2 to 60% while Group 1 follows temperature
sudo python3 thermal_fan_controller.py --group2 60

# Update every 5 seconds (slower, less CPU usage)
sudo python3 thermal_fan_controller.py --interval 5

# Get help
python3 thermal_fan_controller.py --help
```

## Integration Example

Use thermal control in your own scripts:

```python
from thermal_fan_controller import ThermalFanController

# Create controller
controller = ThermalFanController(mode='temp', update_interval=2.0)

# Set Group 2 for air sampling during measurement
controller.set_group2_speed(75)

# Run thermal control in background thread
import threading
thermal_thread = threading.Thread(target=controller.run, daemon=True)
thermal_thread.start()

# Your code here - Group 1 fans auto-adjust to temperature
# while Group 2 runs at fixed 75% for air sampling

# Clean up when done
controller.stop()
```
