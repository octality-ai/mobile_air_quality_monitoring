# Fan Tachometer Setup Guide

## Overview

This guide describes the GPIO pin assignments for reading RPM from 4-pin PWM fans on the Raspberry Pi 5. The tachometer pins are optimally paired with PWM pins for clean wiring.

## Pin Assignment Strategy

**Key Principle**: Each PWM pin is paired with an **adjacent** tachometer pin in the same column (odd or even) to minimize wire length and clutter.

On the 40-pin GPIO header:
- **Odd pins** (31, 33, 35, 37...) are in the **left column**
- **Even pins** (12, 16, 32, 36...) are in the **right column**

## GPIO Pin Assignments

### Group 2 Fans (Air Sampling - PRIORITY)

| Fan | PWM GPIO | PWM Pin | Tach GPIO | Tach Pin | Layout |
|-----|----------|---------|-----------|----------|--------|
| Fan 1 | GPIO13 | **Pin 33** | GPIO6 | **Pin 31** | Adjacent odd pins ✓ |
| Fan 2 | GPIO19 | **Pin 35** | GPIO26 | **Pin 37** | Adjacent odd pins ✓ |

### Group 1 Fans (Heat Sink - OPTIONAL)

| Fan | PWM GPIO | PWM Pin | Tach GPIO | Tach Pin | Layout |
|-----|----------|---------|-----------|----------|--------|
| Fan 1 | GPIO18 | **Pin 12** | GPIO23 | **Pin 16** | Adjacent even pins ✓ |
| Fan 2 | GPIO12 | **Pin 32** | GPIO16 | **Pin 36** | Adjacent even pins ✓ |

## 4-Pin PWM Fan Wiring

Each 4-pin PWM fan has the following wires:

1. **Yellow**: +5V power (connect to external 5V power supply)
2. **Black**: Ground (connect to external 5V GND **AND** Pi GND for common reference)
3. **Blue**: PWM control signal (connect to PWM GPIO pin)
4. **Green**: Tachometer output (connect to Tach GPIO pin)

### Tachometer Signal Characteristics

- **Output Type**: Open-collector (requires pull-up resistor)
- **Pull-up**: Use Raspberry Pi internal pull-up (enabled in software)
- **Pulses**: 2 pulses per revolution (standard for PC fans)
- **Voltage**: Typically 5V when pulled high, but safe with Pi's 3.3V pull-up
- **Frequency Range**:
  - ~25 Hz at 1500 RPM
  - ~200 Hz at 12000 RPM

### RPM Calculation

```
RPM = (pulses_per_second × 60) / 2
```

Example: At 3000 RPM, the tachometer outputs 100 pulses/second (3000 × 2 / 60)

## Physical Wiring Diagram

```
Group 2 (Air Sampling) - Left Column (Odd Pins):
┌────────────────────────────────┐
│ Pin 31 (GPIO6)   → Tach Fan 1  │ ← Adjacent
│ Pin 33 (GPIO13)  → PWM Fan 1   │
│                                 │
│ Pin 35 (GPIO19)  → PWM Fan 2   │ ← Adjacent
│ Pin 37 (GPIO26)  → Tach Fan 2  │
└────────────────────────────────┘

Group 1 (Heat Sink) - Right Column (Even Pins):
┌────────────────────────────────┐
│ Pin 12 (GPIO18)  → PWM Fan 1   │ ← Adjacent
│ Pin 16 (GPIO23)  → Tach Fan 1  │
│                                 │
│ Pin 32 (GPIO12)  → PWM Fan 2   │ ← Adjacent
│ Pin 36 (GPIO16)  → Tach Fan 2  │
└────────────────────────────────┘
```

## Software Setup

### Install Dependencies

```bash
# Install lgpio library for tachometer reading (Pi 5 compatible)
sudo pip3 install lgpio

# rpi-hardware-pwm should already be installed for PWM control
```

### Using the Fan Controller with Tachometer

```python
from dual_fan_controller_with_tach import DualFanControllerWithTach

# Initialize controller with tachometer support
fans = DualFanControllerWithTach(enable_tach=True)

# Set Group 2 speed
fans.set_group2_speed(50)  # 50% speed

# Wait for fans to stabilize
import time
time.sleep(3)

# Update and read RPM
fans.update_tachometers()
group2_rpm = fans.get_group2_rpm()

print(f"GPIO13 RPM: {group2_rpm[13]}")
print(f"GPIO19 RPM: {group2_rpm[19]}")

# Clean up
fans.cleanup()
```

## Testing Tachometer Setup

### Quick Test (Group 2 Only)

```bash
cd /home/octa/octa/src/fan
sudo /home/octa/.octa/bin/python3 test_tachometer.py
```

### Test Group 1 (Optional)

```bash
cd /home/octa/octa/src/fan
sudo /home/octa/.octa/bin/python3 test_tachometer.py --group1
```

### Demo with All Features

```bash
cd /home/octa/octa/src/fan
sudo /home/octa/.octa/bin/python3 dual_fan_controller_with_tach.py
```

## Troubleshooting

### No RPM Reading (RPM = 0)

**Possible Causes:**
1. **Tachometer wire not connected** - Check green wire from fan to GPIO pin
2. **Wrong GPIO pin** - Verify you're using the correct tach GPIO for each fan
3. **Fan not spinning** - Check PWM control and power connections
4. **Common ground missing** - Ensure 5V power supply GND is connected to Pi GND

**Debug Steps:**
```bash
# Check GPIO configuration
pinctrl get 6   # Should show input with pull-up
pinctrl get 26  # Should show input with pull-up

# Manually test GPIO input
sudo python3 -c "import lgpio; h=lgpio.gpiochip_open(0); lgpio.gpio_claim_input(h,6,lgpio.SET_PULL_UP); print('GPIO6:', lgpio.gpio_read(h,6))"
```

### Erratic RPM Readings

**Possible Causes:**
1. **Loose connection** - Check all wire connections
2. **Electrical noise** - Ensure wires are not too long or near interference sources
3. **Missing pull-up** - Verify internal pull-up is enabled in code

### RPM Reading Too High/Low

**Check:**
1. **Pulses per revolution** - Should be 2 for standard PC fans (verify in datasheet)
2. **Update interval** - Call `update_tachometers()` regularly (every 1 second recommended)

## Pin Conflict Check

The following pins are **already in use** and unavailable:

| Purpose | GPIOs | Pins |
|---------|-------|------|
| I2C (SEN66, GPS) | GPIO2, GPIO3 | 3, 5 |
| UART0 (CO sensor) | GPIO14, GPIO15 | 8, 10 |
| UART1 (O3 sensor) | GPIO0, GPIO1 | 27, 28 |
| UART3 (NO2 sensor) | GPIO8, GPIO9 | 21, 24 |
| PWM (Fans) | GPIO12, GPIO13, GPIO18, GPIO19 | 12, 32, 33, 35 |
| **Tachometers** | **GPIO6, GPIO16, GPIO23, GPIO26** | **16, 31, 36, 37** |

**Verified**: No conflicts with existing hardware.

## Integration with Existing Code

The tachometer functionality is **optional** and can be added to existing fan control code:

### MAQM Logger Integration (Group 2 Priority)

To add RPM monitoring to the MAQM data logger:

```python
# In MAQM_main.py, replace:
from dual_fan_controller import DualFanController

# With:
from dual_fan_controller_with_tach import DualFanControllerWithTach as DualFanController

# Then add RPM logging in the data collection loop:
fans.update_tachometers()
group2_rpm = fans.get_group2_rpm()

# Add to CSV output:
row["fan1_rpm"] = group2_rpm.get(13, None)
row["fan2_rpm"] = group2_rpm.get(19, None)
```

### Thermal Controller Integration (Group 1 Optional)

The thermal fan controller currently only manages Group 1. To add tachometer support, replace the `Group1FanController` class with calls to `DualFanControllerWithTach`.

## References

- [Raspberry Pi 5 Pinout](https://pinout.xyz/)
- [lgpio Documentation](https://abyz.me.uk/lg/py_lgpio.html)
- [PC Fan PWM Specification](https://www.intel.com/content/dam/support/us/en/documents/intel-nuc/4-Wire_PWM_Spec.pdf)

## Hardware Requirements

- Raspberry Pi 5
- 4-pin PWM fans (standard PC fans)
- 5V power supply for fans (minimum 1A per fan)
- Common ground connection between Pi and fan power supply
- lgpio library installed

## Safety Notes

- **Always** connect external 5V power supply ground to Raspberry Pi ground
- Do **NOT** power fans from Pi's 5V pins (insufficient current)
- Tachometer signals are 5V tolerant when using 3.3V pull-up
- GPIO pins can handle max 16mA - tachometer signals are low current (< 1mA)
