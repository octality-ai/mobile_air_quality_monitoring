# Quad PWM Fan Setup Guide

This guide covers setup for 4 PWM fans divided into two independent groups.

## Hardware Configuration

### Group 1: Heat Sink Fans
- **Fan 1**: GPIO12 (Physical Pin 32) - PWM control
- **Fan 2**: GPIO18 (Physical Pin 12) - PWM control

### Group 2: Air Sampling Fans
- **Fan 3**: GPIO13 (Physical Pin 33) - PWM control
- **Fan 4**: GPIO19 (Physical Pin 35) - PWM control

### Wiring (All Fans)
- Yellow wire → +5V power supply
- Black wire → Common ground (5V supply GND + Pi GND)
- Blue wire → GPIO PWM control
- Green wire → Tachometer (optional, not currently used)

---

## Step 1: Remove UART4 Overlay (COMPLETED ✓)

GPIO 12 and 13 were conflicting with UART4. You've already removed:
```
dtoverlay=uart4  # ← REMOVED from /boot/firmware/config.txt
```

**Status**: ✓ Done - requires reboot to take effect

---

## Step 2: Set All GPIOs to LOW at Boot

Choose **ONE** of these methods:

### Option A: Systemd Service (Recommended)

Install the service that sets all 4 GPIOs LOW at boot and shutdown:

```bash
cd /home/mover/octa/src/fan
./install_quad_fan_gpio.sh
```

This creates a service that:
- Sets GPIO 12, 13, 18, 19 to OUTPUT LOW at boot
- Ensures fans stay off until controller starts
- Resets GPIOs LOW at shutdown

### Option B: Boot Config

Add to `/boot/firmware/config.txt`:

```bash
# Set all 4 fan GPIOs to output LOW (fans stopped by default)
gpio=12,13,18,19=op,dl
```

Then reboot.

---

## Step 3: Reboot

**You must reboot now** for the uart4 removal to take effect:

```bash
sudo reboot
```

After reboot, verify GPIOs:

```bash
for gpio in 12 13 18 19; do sudo pinctrl get $gpio; done
```

Expected output (all should show `op dl | lo`):
```
12: op dl pn | lo // GPIO12 = output
13: op dl pn | lo // GPIO13 = output
18: op dl pn | lo // GPIO18 = output
19: op dl pn | lo // GPIO19 = output
```

---

## Step 4: Test the Dual-Group Controller

### Basic Test

Test both groups independently:

```bash
cd /home/mover/octa/src/fan
sudo /home/mover/.octa/bin/python3 dual_fan_controller.py
```

This will:
1. Ramp Group 1 (Heat Sink) through 0%, 30%, 60%, 100%
2. Ramp Group 2 (Air Sampling) through 0%, 30%, 60%, 100%
3. Run both groups together at different speeds
4. Stop all fans

### Interactive Demo

Control both groups independently with keyboard:

```bash
sudo /home/mover/.octa/bin/python3 dual_fan_demo.py
```

**Display:**
```
Group 1 (Heat Sink):    50.0%
Group 2 (Air Sampling):  75.0%

Keys: 1-9 (G1) | Q-P (G2) | A/Z (G1 100/0) | L/. (G2 100/0) | X (stop) | ESC
```

**Controls:**

| Key | Action |
|-----|--------|
| **1-9** | Set Group 1 to 10%-90% |
| **A** | Group 1 to 100% (full speed) |
| **Z** | Group 1 to 0% (stop) |
| **Q-P** | Set Group 2 (Q=10%, W=20%, E=30%, R=40%, T=50%, Y=60%, U=70%, I=80%, O=90%, P=100%) |
| **L** | Group 2 to 100% (full speed) |
| **.** | Group 2 to 0% (stop) |
| **X** | Stop all fans |
| **ESC** | Quit |

---

## Using the Controller in Your Code

```python
from dual_fan_controller import DualFanController

# Initialize controller
with DualFanController() as fans:
    # Control heat sink fans (Group 1)
    fans.set_group1_speed(50)  # 50% speed

    # Control air sampling fans (Group 2)
    fans.set_group2_speed(75)  # 75% speed

    # Check current speeds
    print(f"Group 1: {fans.get_group1_speed()}%")
    print(f"Group 2: {fans.get_group2_speed()}%")

    # Stop all
    fans.stop_all()
```

---

## Troubleshooting

### Problem: Fans running at boot before controller starts

**Solution**: Install the GPIO init service (Option A above)

### Problem: GPIO still shows UART mode after reboot

Check that uart4 overlay is really removed:
```bash
grep uart4 /boot/firmware/config.txt
```

Should return nothing. If it shows the overlay, remove it and reboot again.

### Problem: "GPIO does not support hardware PWM"

Verify you're using the correct GPIOs (12, 13, 18, 19 only):
```bash
sudo pinctrl get 12 13 18 19
```

### Problem: Fans won't start

1. Check power supply (5V) is connected
2. Verify ground is common between Pi and power supply
3. Test with high speed first:
   ```python
   fans.set_group1_speed(100)
   fans.set_group2_speed(100)
   ```

---

## Files

- [dual_fan_controller.py](dual_fan_controller.py) - Dual-group controller library
- [dual_fan_demo.py](dual_fan_demo.py) - Interactive keyboard control demo
- [quad-fan-gpio-init.service](quad-fan-gpio-init.service) - Systemd service for GPIO init
- [install_quad_fan_gpio.sh](install_quad_fan_gpio.sh) - Service installation script

---

## Quick Reference

```bash
# After reboot, install GPIO init service
cd /home/mover/octa/src/fan
./install_quad_fan_gpio.sh

# Test fans
sudo /home/mover/.octa/bin/python3 dual_fan_controller.py

# Interactive control
sudo /home/mover/.octa/bin/python3 dual_fan_demo.py

# Emergency stop all fans
for gpio in 12 13 18 19; do sudo pinctrl set $gpio op dl; done
```
