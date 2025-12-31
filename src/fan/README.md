# Quad PWM Fan Controller

Independent control of 4 PWM fans organized into 2 groups on Raspberry Pi 5.

## Hardware Setup

### Fan Groups
- **Group 1 (Heat Sink)**: GPIO12 + GPIO18
- **Group 2 (Air Sampling)**: GPIO13 + GPIO19

### Wiring
All fans use standard 4-wire PWM pinout:
- Yellow: +5V power
- Black: Ground (common with Pi)
- Blue: PWM control (connect to GPIO)
- Green: Tachometer (optional, not currently used)

## Quick Start

### 1. Install GPIO Init Service (one-time setup)
```bash
cd /home/mover/octa/src/fan
./install_quad_fan_gpio.sh
```

This ensures all 4 fan GPIOs default to LOW (fans off) at boot.

### 2. Choose Your Control Method

#### Option A: Automatic Thermal Control (Recommended)
Group 1 fans automatically follow CPU temperature (like the Pi's cooler):
```bash
sudo /home/mover/.octa/bin/python3 thermal_fan_controller.py
```

See [THERMAL_CONTROL.md](THERMAL_CONTROL.md) for details.

#### Option B: Manual Control
Interactive keyboard control of both groups:
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
- **1-9**: Set Group 1 to 10-90%
- **A**: Group 1 to 100%
- **Z**: Group 1 to 0%
- **Q-P**: Set Group 2 (Q=10%, W=20%, E=30%, R=40%, T=50%, Y=60%, U=70%, I=80%, O=90%, P=100%)
- **L**: Group 2 to 100%
- **.**: Group 2 to 0%
- **X**: Stop all fans
- **ESC**: Quit

## Using in Your Code

```python
from dual_fan_controller import DualFanController

with DualFanController() as fans:
    # Control heat sink fans (Group 1)
    fans.set_group1_speed(60)  # 60% speed

    # Control air sampling fans (Group 2)
    fans.set_group2_speed(80)  # 80% speed

    # Check speeds
    print(f"Group 1: {fans.get_group1_speed()}%")
    print(f"Group 2: {fans.get_group2_speed()}%")

    # Stop all
    fans.stop_all()
```

## Files

| File | Purpose |
|------|---------|
| `dual_fan_controller.py` | Main controller library |
| `dual_fan_demo.py` | Interactive keyboard demo |
| `thermal_fan_controller.py` | **Automatic thermal control** (follows CPU temp) |
| `quad-fan-gpio-init.service` | Systemd service (sets GPIOs LOW at boot) |
| `install_quad_fan_gpio.sh` | Service installer |
| `QUAD_FAN_SETUP.md` | Detailed setup guide |
| `THERMAL_CONTROL.md` | **Thermal control documentation** |

## Troubleshooting

### Emergency Stop
```bash
for gpio in 12 13 18 19; do sudo pinctrl set $gpio op dl; done
```

### Check GPIO Status
```bash
for gpio in 12 13 18 19; do sudo pinctrl get $gpio; done
```

All should show: `op dl | lo` (output, drive low, currently low)

### Check Service Status
```bash
sudo systemctl status quad-fan-gpio-init.service
```

For detailed troubleshooting, see [QUAD_FAN_SETUP.md](QUAD_FAN_SETUP.md).
