# Fan GPIO12 Initialization Setup

This document describes how to ensure GPIO12 (fan PWM pin) is always set to LOW (0% PWM) when the fan controller program is not running.

## Why This Matters

The Noctua fan uses normal PWM logic:
- **HIGH (3.3V) = fan runs at full speed**
- **LOW (0V) = fan stopped**

If GPIO12 is left floating or high when the fan controller isn't running, the fan may run unexpectedly. Setting it to LOW ensures the fan stays off by default.

---

## Option 1: Systemd Service (Recommended)

This method ensures GPIO12 is set to LOW on boot and shutdown.

### Installation

```bash
cd /home/mover/octa
./install_fan_gpio_init.sh
```

### What It Does

- Creates a systemd service that runs at boot and shutdown
- Sets GPIO12 to output mode, drive LOW (`pinctrl set 12 op dl`)
- Automatically enables the service to run on every boot

### Management Commands

```bash
# Check service status
sudo systemctl status fan-gpio-init.service

# Manually trigger (if needed)
sudo systemctl start fan-gpio-init.service

# Disable service
sudo systemctl disable fan-gpio-init.service

# Re-enable service
sudo systemctl enable fan-gpio-init.service

# Uninstall completely
sudo systemctl stop fan-gpio-init.service
sudo systemctl disable fan-gpio-init.service
sudo rm /etc/systemd/system/fan-gpio-init.service
sudo systemctl daemon-reload
```

---

## Option 2: Boot Config (Alternative)

Edit `/boot/firmware/config.txt` to set GPIO12 state at boot time using device tree overlays.

### Add to config.txt

```bash
sudo nano /boot/firmware/config.txt
```

Add this line at the end:

```
# Set GPIO12 to output LOW for fan control (fan off by default)
gpio=12=op,dl
```

### Explanation

- `gpio=12` - Target GPIO12
- `op` - Set as output
- `dl` - Drive low (0V)

### Apply Changes

```bash
sudo reboot
```

### Verify After Reboot

```bash
sudo pinctrl get 12
# Should show: 12: op dl pn | lo // GPIO12 = output
```

---

## Option 3: Manual Command (For Testing)

To manually set GPIO12 to LOW anytime:

```bash
sudo pinctrl set 12 op dl
```

This is useful for:
- Testing before installing systemd service
- Emergency fan stop
- One-time setup

---

## Verification

After installing either option, verify GPIO12 is LOW:

```bash
# Check GPIO state
sudo pinctrl get 12

# Should output:
# 12: op dl pn | lo // GPIO12 = output
#
# Key indicators:
# - "op" = output mode
# - "dl" = drive low
# - "lo" = currently low
```

---

## Fan Controller Integration

The fan controller programs ([fan_control.py](fan_control.py) and [fan_demo.py](fan_demo.py)) automatically:

1. **On startup**: Configure GPIO12 for PWM (changes to ALT0 mode)
2. **During operation**: Control fan speed via PWM
3. **On cleanup**: Set GPIO12 back to output LOW

This means:
- ✅ Systemd service sets GPIO12 LOW at boot
- ✅ Fan controller takes over when running
- ✅ Fan controller returns GPIO12 to LOW on exit
- ✅ GPIO12 stays LOW between runs

---

## Troubleshooting

### Fan Runs at Boot (Before Service Starts)

If the fan briefly runs during boot, the systemd service may be starting too late. Use **Option 2** (boot config) instead, which applies earlier in the boot process.

### GPIO12 Not LOW After Reboot

Check if service is enabled and running:

```bash
sudo systemctl status fan-gpio-init.service
sudo systemctl is-enabled fan-gpio-init.service
```

If disabled, re-enable:

```bash
sudo systemctl enable fan-gpio-init.service
sudo systemctl start fan-gpio-init.service
```

### Both Options Active

It's safe to use both Option 1 and Option 2 together. They both set the same state (GPIO12 LOW), so there's no conflict.

---

## Summary

**Quick Setup (Choose One):**

```bash
# Method 1: Systemd service (runs on boot + shutdown)
./install_fan_gpio_init.sh

# Method 2: Boot config (runs earliest at boot)
echo 'gpio=12=op,dl' | sudo tee -a /boot/firmware/config.txt
sudo reboot
```

**Current GPIO12 State (as of now):**
```bash
sudo pinctrl get 12
# Output: 12: op dl pn | lo // GPIO12 = output
```

✅ GPIO12 is already correctly configured to LOW!
