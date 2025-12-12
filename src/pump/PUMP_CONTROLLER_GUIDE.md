# 4-Wire Pump Controller - Complete Guide
## Raspberry Pi 5 with Hardware PWM

This guide covers everything you need to control a 4-wire PWM pump on Raspberry Pi 5.

---

## Table of Contents

1. [Overview](#overview)
2. [Hardware Setup](#hardware-setup)
3. [Software Installation](#software-installation)
4. [Usage](#usage)
5. [Troubleshooting](#troubleshooting)
6. [Technical Details](#technical-details)

---

## Overview

This pump controller provides:
- **Hardware PWM** at 10-30 kHz for smooth, precise speed control
- **Tachometer feedback** for real-time RPM monitoring
- **Inverted logic handling** (LOW=run, HIGH=stop) built-in
- **Safe startup/shutdown** - pump automatically stops when program exits

### Files

- **`pump_controller.py`** - Main controller library
- **`pump_demo.py`** - Interactive demonstration with keyboard controls

---

## Hardware Setup

### Required Hardware

- Raspberry Pi 5
- 4-wire PWM pump with:
  - Red wire: 12V power (+)
  - Black wire: Ground (-)
  - Blue wire: PWM control (10-30 kHz)
  - Green wire: Tachometer output (RPM feedback)
- 12V power supply (sufficient current for your pump)
- Jumper wires (female-to-female)

### Wiring Connections

```
Pump Wire  →  Connection
─────────────────────────────────────────
Red        →  12V Power Supply (+)
Black      →  12V Supply GND + Pi GND (Pin 6)  ← COMMON GROUND
Blue       →  GPIO12 (Physical Pin 32)
Green      →  GPIO23 (Physical Pin 16)
```

### Wiring Diagram

```
┌──────────────────┐
│   12V Power      │
│   Supply         │
└────┬─────────┬───┘
     │ +12V    │ GND
     │         │
     ↓         ↓
   ┌─────────────────┐
   │   4-Wire Pump   │
   │                 │
   │  Red ───────────┤ 12V input
   │  Black ─────────┤ GND ──┐
   │  Blue ──────────┤ PWM   │
   │  Green ─────────┤ Tach  │
   └─────────────────┘       │
        │       │             │
        │       │             │
   ┌────▼───────▼─────────────▼──┐
   │    Raspberry Pi 5           │
   │  Pin 32 (GPIO12) ← Blue     │
   │  Pin 16 (GPIO23) ← Green    │
   │  Pin 6  (GND)    ← Black ───┤
   └─────────────────────────────┘
                                  │
                       12V GND ───┘
```

### Critical Wiring Notes

⚠️ **IMPORTANT**:
1. **Common ground is essential** - Black wire connects to BOTH 12V supply GND AND Pi GND
2. **Never connect 12V to Pi GPIO** - Only 3.3V logic signals (blue/green wires)
3. **Inverted logic** - This pump runs when PWM is LOW (0V), stops when HIGH (3.3V)
   - The code handles this automatically

---

## Software Installation

### Step 1: Update System

```bash
sudo apt update
sudo apt upgrade -y
```

### Step 2: Install Hardware PWM Library

**This is REQUIRED for 25 kHz operation.**

```bash
# Install hardware PWM library
sudo pip3 install rpi-hardware-pwm
```

### Step 3: Enable PWM Device Tree Overlay

```bash
# Edit boot config
sudo nano /boot/firmware/config.txt

# Add this line at the end:
dtoverlay=pwm-2chan

# Save (Ctrl+O, Enter, Ctrl+X)
```

**Reboot to apply:**
```bash
sudo reboot
```

### Step 4: Install GPIO Libraries

```bash
# Install lgpio and gpiozero for tachometer
sudo apt install -y python3-lgpio python3-gpiozero

# Configure gpiozero backend
echo 'export GPIOZERO_PIN_FACTORY=lgpio' >> ~/.bashrc
source ~/.bashrc
```

### Step 5: Set Up Permissions

```bash
# Add user to gpio group
sudo usermod -a -G gpio $USER

# Set up PWM permissions
./setup_pwm_permissions.sh

# Reboot to apply
sudo reboot
```

### Step 6: Verify Installation

```bash
# Check hardware PWM library
python3 -c "from rpi_hardware_pwm import HardwarePWM; print('✓ Hardware PWM OK')"

# Check PWM device tree
ls /sys/class/pwm/
# Should show: pwmchip0  pwmchip1

# Check GPIO permissions
groups | grep gpio
# Should show gpio in the list
```

---

## Usage

### Basic Test

Run the test program to verify everything works:

```bash
sudo /home/mover/.octa/bin/python3 pump_controller.py
```

**Expected behavior:**
- Pump starts stopped (0%)
- Ramps through: 30% → 50% → 70% → 100% → back to 0%
- Displays RPM readings at each speed
- **Pump fully stops when program exits** ✓

### Interactive Demo

Run the interactive controller with keyboard controls:

```bash
sudo /home/mover/.octa/bin/python3 pump_demo.py
```

**Controls:**

| Key | Action |
|-----|--------|
| ↑ (Up) | Increase speed by 5% |
| ↓ (Down) | Decrease speed by 5% |
| → (Right) | Increase speed by 1% |
| ← (Left) | Decrease speed by 1% |
| 0-9 | Set speed to 0%, 10%, 20%, ... 90% |
| F | Full speed (100%) |
| S | Stop (0%) |
| R | Ramp to custom speed |
| Q or ESC | Quit |

**Display shows:**
- Current speed percentage with bar graph
- Real-time RPM reading
- Total pulse count
- Status messages

### Using in Your Code

**Simple example:**

```python
#!/usr/bin/env python3
from pump_controller import PumpController
import time

# Create pump controller
pump = PumpController()

try:
    # Set pump to 50% speed
    pump.set_speed_percent(50)
    time.sleep(5)

    # Read RPM
    rpm = pump.get_rpm()
    print(f"Current RPM: {rpm:.0f}")

    # Ramp to 80% over 3 seconds
    pump.ramp_speed(80, duration_seconds=3.0)
    time.sleep(2)

    # Stop pump
    pump.stop()

finally:
    # Always cleanup (sets GPIO HIGH to keep pump stopped)
    pump.cleanup()
```

**Using context manager (recommended):**

```python
with PumpController() as pump:
    pump.set_speed_percent(75)
    time.sleep(5)
    rpm = pump.get_rpm()
    print(f"RPM: {rpm:.0f}")
    # Automatic cleanup when exiting 'with' block
```

### API Reference

**PumpController class:**

```python
# Initialization
pump = PumpController(pwm_pin=12, tach_pin=23, frequency=25000)

# Speed control
pump.set_speed(0.5)              # 0.0-1.0 (50% speed)
pump.set_speed_percent(50)       # 0-100 (50% speed)
pump.stop()                      # Stop pump (0% speed)
pump.ramp_speed(80, duration_seconds=2.0, steps=20)  # Smooth ramp

# Speed reading
speed = pump.get_speed()         # Returns 0.0-1.0
speed_pct = pump.get_speed_percent()  # Returns 0-100

# RPM reading
rpm = pump.get_rpm()             # Returns current RPM
pulses = pump.get_pulse_count()  # Returns total pulses

# Cleanup
pump.cleanup()                   # Stop pump and release GPIO
```

---

## Troubleshooting

### Pump Doesn't Run

**Check wiring:**
```bash
# Test if pump works when manually grounded
# Disconnect blue wire from Pi
# Touch blue wire to Pi GND
# Pump should run at full speed
```

**Check GPIO12 can pull LOW:**
```bash
# Set GPIO12 LOW (pump should run)
sudo pinctrl set 12 op dl

# Set GPIO12 HIGH (pump should stop)
sudo pinctrl set 12 op dh
```

**Check GPIO12 is configured for PWM:**
```bash
pinctrl get 12
# Should show: 12: a0 pn | lo // GPIO12 = PWM0_CHAN0
# OR: 12: op dh pn | hi // GPIO12 = output (when stopped)
```

### Pump Runs After Program Exits

This is now fixed. The cleanup code sets GPIO12 HIGH (pump stopped) when exiting.

**Manual stop if needed:**
```bash
sudo pinctrl set 12 op dh
```

### Permission Errors

```
PermissionError: [Errno 13] Permission denied: '/sys/class/pwm/...'
```

**Solution:**
```bash
./setup_pwm_permissions.sh
sudo reboot
```

**Or run with sudo:**
```bash
sudo /home/mover/.octa/bin/python3 pump_controller.py
```

### RPM Always Shows 0

**Possible causes:**

1. **Tachometer wire not connected** - Check green wire to GPIO23
2. **Pump not spinning** - Verify pump is running (listen/feel vibration)
3. **Wrong pulses-per-revolution** - Default is 2, some pumps use 1 or 4

**To change pulses-per-revolution:**
```python
pump = PumpController()
pump.PULSES_PER_REVOLUTION = 1  # Try 1 or 4
```

### "bad PWM frequency" Error

```
lgpio.error: 'bad PWM frequency'
```

**Solution:** Install hardware PWM library (see installation steps above)

Without `rpi-hardware-pwm`, the system falls back to software PWM which has a 10 kHz limit.

---

## Technical Details

### PWM Specifications

- **Frequency:** 25 kHz (configurable 10-30 kHz)
- **Duty Cycle:** 0-100%
- **Polarity:** INVERTED (active-low)
  - 0% duty = 100% PWM (HIGH) = Pump STOPPED
  - 100% duty = 0% PWM (LOW) = Pump FULL SPEED
  - Code automatically inverts, so `set_speed_percent(50)` = 50% pump speed
- **Resolution:** Hardware PWM peripheral (~12-bit effective)
- **Output:** 3.3V logic level (0V LOW, 3.3V HIGH)

### Hardware PWM on Raspberry Pi 5

**Pi 5 GPIO PWM Mapping:**

| GPIO Pin | Physical Pin | PWM Channel | Usage |
|----------|--------------|-------------|-------|
| GPIO12   | 32           | PWM0_CHAN0  | **Pump (default)** |
| GPIO13   | 33           | PWM0_CHAN1  | Available |
| GPIO18   | 12           | PWM1_CHAN0  | Available |
| GPIO19   | 35           | PWM1_CHAN1  | Available |

**Notes:**
- Channels on same PWM block (PWM0 or PWM1) share frequency
- GPIO12 and GPIO13 must use same frequency if both used
- GPIO18 and GPIO19 must use same frequency if both used

### Pin Configuration States

The controller manages GPIO12 through these states:

**During initialization:**
```bash
sudo pinctrl set 12 op a0  # Set to PWM mode (ALT0)
```

**During operation:**
- GPIO12 is in PWM mode outputting 25 kHz signal
- Duty cycle varies from 0-100% (inverted for pump control)

**During cleanup:**
```bash
sudo pinctrl set 12 op dh  # Set to output HIGH (pump stopped)
```

This ensures the pump stays stopped even after the program exits.

### Tachometer Signal Processing

**Signal type:** Open-collector (open-drain) output
- Pulls to GND when active
- Floats when inactive
- Internal 50kΩ pull-up resistor enabled

**RPM Calculation:**
```python
pulses_per_second = 1 / time_between_pulses
revolutions_per_second = pulses_per_second / PULSES_PER_REVOLUTION
RPM = revolutions_per_second * 60
```

**Smoothing:** Moving average filter (70% old + 30% new reading)

### Why Hardware PWM is Required

**Software PWM limitations (lgpio):**
- Maximum frequency: 10 kHz
- Subject to Linux scheduler jitter
- CPU-dependent timing
- Unreliable for 25 kHz

**Hardware PWM advantages:**
- Frequency range: 0.1 Hz to >1 MHz
- Dedicated peripheral (no CPU timing)
- Zero jitter, precise timing
- <1% CPU usage

### Library Architecture

```
pump_controller.py
├── rpi-hardware-pwm ──> Hardware PWM control (25 kHz)
├── gpiozero ──────────> Tachometer input (interrupt-driven)
└── subprocess ────────> Pin configuration (pinctrl commands)
```

**Dependencies:**
- `rpi-hardware-pwm` - Hardware PWM access
- `gpiozero` - GPIO input for tachometer
- `lgpio` - GPIO backend for Pi 5
- `subprocess` - Execute pinctrl commands

---

## Quick Command Reference

### GPIO Control

```bash
# Stop pump immediately
sudo pinctrl set 12 op dh

# Run pump at full speed (careful!)
sudo pinctrl set 12 op dl

# Set GPIO12 to PWM mode
sudo pinctrl set 12 op a0

# Check current GPIO12 state
pinctrl get 12
```

### System Diagnostics

```bash
# Check PWM hardware
ls /sys/class/pwm/

# Check hardware PWM library
python3 -c "from rpi_hardware_pwm import HardwarePWM; print('OK')"

# Check GPIO permissions
groups | grep gpio

# Check device tree overlay
grep pwm /boot/firmware/config.txt
```

### Run Programs

```bash
# Basic test
sudo /home/mover/.octa/bin/python3 pump_controller.py

# Interactive demo
sudo /home/mover/.octa/bin/python3 pump_demo.py
```

---

## Safety Features

The pump controller includes several safety features:

1. **Safe startup** - Pump starts at 0% (stopped)
2. **Automatic cleanup** - Pump stops when program exits (even on crash)
3. **GPIO state management** - GPIO12 set HIGH after cleanup to keep pump stopped
4. **Context manager support** - Automatic cleanup with `with` statement
5. **Smooth ramping** - Gradual speed changes to prevent mechanical shock

---

## Example: Integration with Sensor Logging

```python
#!/usr/bin/env python3
"""
Example: Control pump based on sensor readings
"""
from pump_controller import PumpController
import time

with PumpController() as pump:
    # Start pump at 30%
    pump.set_speed_percent(30)

    while True:
        # Read your sensor here
        sensor_value = read_sensor()  # Your sensor function

        # Adjust pump speed based on sensor
        if sensor_value < 100:
            pump.set_speed_percent(30)
        elif sensor_value < 200:
            pump.set_speed_percent(50)
        else:
            pump.set_speed_percent(80)

        # Log data
        rpm = pump.get_rpm()
        print(f"Sensor: {sensor_value}, Speed: {pump.get_speed_percent():.1f}%, RPM: {rpm:.0f}")

        time.sleep(1)
```

---

## FAQ

**Q: Do I always need to run with sudo?**

A: Yes, for now. The `pinctrl` commands require sudo. Future versions may use alternative methods.

**Q: Can I use a different GPIO pin?**

A: Yes, but only GPIO12, 13, 18, or 19 support hardware PWM. Example:
```python
pump = PumpController(pwm_pin=18)  # Use GPIO18 instead
```

**Q: What if my pump uses different pulses per revolution?**

A: Change the value after initialization:
```python
pump = PumpController()
pump.PULSES_PER_REVOLUTION = 4  # Set to your pump's value
```

**Q: Can I change the PWM frequency?**

A: Yes, when creating the controller:
```python
pump = PumpController(frequency=30000)  # 30 kHz
```

**Q: What happens if I unplug the tachometer?**

A: RPM will read 0, but pump control still works normally.

**Q: Can I control multiple pumps?**

A: Yes, use different PWM pins:
```python
pump1 = PumpController(pwm_pin=12, tach_pin=23)
pump2 = PumpController(pwm_pin=13, tach_pin=24)
```

---

## Maintenance

### Check GPIO State After Reboot

```bash
# GPIO12 should be input (default) after reboot
pinctrl get 12
# Shows: 12: ip pn | hi // GPIO12 = input

# Pump controller will configure it automatically when running
```

### Update Software

```bash
# Update hardware PWM library
sudo pip3 install --upgrade rpi-hardware-pwm

# Update gpiozero
sudo apt update && sudo apt upgrade python3-gpiozero
```

---

## Support

For issues or questions:

1. Check [Troubleshooting](#troubleshooting) section
2. Verify wiring connections
3. Test with manual GPIO control
4. Check system logs: `dmesg | tail -20`
5. Verify all installation steps completed

---

**Document Version:** 2.0
**Last Updated:** 2025-11-21
**Tested On:** Raspberry Pi 5, Raspberry Pi OS (64-bit), Kernel 6.12.47
**Hardware:** 4-wire PWM pump with inverted logic (LOW=run, HIGH=stop)
