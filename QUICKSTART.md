# Quick Start Guide - Daily Operation Commands

## Overview

This Raspberry Pi system runs two main services for autonomous monitoring. **Both services can run simultaneously without conflict.**

### 1. Thermal Fan Control Service
**Service**: `thermal-fan-control.service`
**Purpose**: Automatically controls **Group 1 heat-sink fans only** (GPIO12, GPIO18) based on CPU temperature to maintain optimal operating conditions. Uses hardware PWM at 25 kHz. **Does NOT touch Group 2 fans** - those are reserved for the MAQM logger.

### 2. MAQM Data Logger Service
**Service**: `maqm-logger.service`
**Purpose**: Mobile Air Quality Monitor that continuously logs environmental data from multiple sensors:
- **GNSS** (u-blox NEO-M8U): GPS location and time
- **SEN66** (Sensirion): PM, VOC, NOx, CO2, temperature, humidity
- **SpecSensor** (DGS2-970): Gas measurements (CO, O3, NO2)

Samples data every 1 second and writes to CSV every 60 seconds with buffering. Controls **Group 2 air sampling fans** (GPIO13, GPIO19) during data collection.

---

## Service Management Commands

### Thermal Fan Control Service

```bash
# Start the service
sudo systemctl start thermal-fan-control.service

# Stop the service
sudo systemctl stop thermal-fan-control.service

# Restart the service
sudo systemctl restart thermal-fan-control.service

# Check service status
sudo systemctl status thermal-fan-control.service

# View live logs (Ctrl+C to exit)
sudo journalctl -u thermal-fan-control.service -f

# View recent logs (last 50 lines)
sudo journalctl -u thermal-fan-control.service -n 50

# Enable auto-start at boot
sudo systemctl enable thermal-fan-control.service

# Disable auto-start at boot
sudo systemctl disable thermal-fan-control.service
```

### MAQM Data Logger Service

```bash
# Start the service
sudo systemctl start maqm-logger.service

# Stop the service
sudo systemctl stop maqm-logger.service

# Restart the service
sudo systemctl restart maqm-logger.service

# Check service status
sudo systemctl status maqm-logger.service

# View live logs (Ctrl+C to exit)
sudo journalctl -u maqm-logger.service -f

# View recent logs (last 50 lines)
sudo journalctl -u maqm-logger.service -n 50

# Enable auto-start at boot
sudo systemctl enable maqm-logger.service

# Disable auto-start at boot
sudo systemctl disable maqm-logger.service
```

---

## GPS/GNSS Debugging Commands

### Quick I2C Check

```bash
# Scan I2C bus for connected devices
# Should show 0x42 (u-blox GNSS) and 0x6B (SEN66)
i2cdetect -y 1
```

### GPS Diagnostic Tool

```bash
# Run comprehensive GPS diagnostic
# Shows satellite visibility, signal strength, antenna status, fix quality
cd /home/octa/octa/src/gps
sudo python3 gps_diagnostic.py
```

### Quick GPS Test

```bash
# Read GPS coordinates with formatted display (RECOMMENDED)
# Shows lat/lon, altitude, fix status, and Google Maps link
cd /home/octa/octa/src/gps
python3 read_gps_coordinates.py

# Test GPS with simplified reader
# Shows NMEA messages and parsed position data
cd /home/octa/octa/src/gps
python3 test_ublox_gps.py
```

### GPS Configuration Tools

```bash
# Configure external/active antenna (if applicable)
cd /home/octa/octa/src/gps
python3 configure_antenna.py

# Enable multi-GNSS support (GPS + GLONASS + Galileo + BeiDou)
cd /home/octa/octa/src/gps
python3 enable_multi_gnss.py
```

### Common GPS Troubleshooting

```bash
# Check if GPS is responding on I2C
i2cdetect -y 1 | grep 42

# Verify user has I2C permissions
groups | grep i2c

# Add user to i2c group if missing
sudo adduser $USER i2c
sudo reboot

# Monitor GPS fix status in real-time
watch -n 1 'sudo journalctl -u maqm-logger.service -n 5 | grep -E "(GPS|GNSS|Fix)"'
```

---

## Emergency Manual Control

### Stop Specific Fan Groups

```bash
# Stop Group 1 (heat sink) fans controlled by thermal-fan-control service
for gpio in 12 18; do sudo pinctrl set $gpio op dl; done

# Stop Group 2 (air sampling) fans controlled by maqm-logger service
for gpio in 13 19; do sudo pinctrl set $gpio op dl; done

# Emergency stop ALL fans (both groups)
for gpio in 12 13 18 19; do sudo pinctrl set $gpio op dl; done
```

### Manual Fan Test

```bash
# Test thermal controller manually (Group 1 only, outside of service)
cd /home/octa/octa/src/fan
sudo /home/octa/.octa/bin/python3 thermal_fan_controller.py

# Test both fan groups independently
cd /home/octa/octa/src/fan
sudo /home/octa/.octa/bin/python3 dual_fan_controller.py

# Test fan tachometer (RPM reading) - Group 2 priority
cd /home/octa/octa/src/fan
sudo /home/octa/.octa/bin/python3 test_tachometer.py

# Test Group 1 tachometer (optional)
sudo /home/octa/.octa/bin/python3 test_tachometer.py --group1

# Full demo with PWM control and RPM monitoring
sudo /home/octa/.octa/bin/python3 dual_fan_controller_with_tach.py
```

### Check CSV Data Output

```bash
# View latest logged data (adjust date as needed)
cd /home/octa/octa/src
ls -lh data_*.csv
tail -n 20 data_YYYYMMDD.csv
```

---

## System Status at a Glance

```bash
# Check both services at once
sudo systemctl status thermal-fan-control.service maqm-logger.service

# Quick health check
echo "=== I2C Devices ===" && i2cdetect -y 1 && \
echo -e "\n=== Service Status ===" && \
sudo systemctl is-active thermal-fan-control.service maqm-logger.service && \
echo -e "\n=== CPU Temperature ===" && \
cat /sys/class/thermal/thermal_zone0/temp | awk '{printf "%.1f°C\n", $1/1000}'
```

---

## Fan Group Assignment (No Conflict Design)

The system uses **4 PWM fans in 2 independent groups** with clear separation of control:

### PWM Control Pins

| Group | PWM GPIOs | Physical Pins | Purpose | Controlled By |
|-------|-----------|---------------|---------|---------------|
| **Group 1** | GPIO12, GPIO18 | 32, 12 | Heat sink cooling | `thermal-fan-control.service` |
| **Group 2** | GPIO13, GPIO19 | 33, 35 | Air sampling | `maqm-logger.service` |

### Tachometer (RPM Reading) Pins

| Group | Fan | PWM Pin | Tach GPIO | Tach Pin | Layout |
|-------|-----|---------|-----------|----------|--------|
| **Group 2** | Fan 1 | 33 (GPIO13) | GPIO6 | 31 | Adjacent odd pins ✓ |
| **Group 2** | Fan 2 | 35 (GPIO19) | GPIO26 | 37 | Adjacent odd pins ✓ |
| **Group 1** | Fan 1 | 12 (GPIO18) | GPIO23 | 16 | Adjacent even pins ✓ |
| **Group 1** | Fan 2 | 32 (GPIO12) | GPIO16 | 36 | Adjacent even pins ✓ |

**Key Design Features**:
- The thermal fan controller has been specifically designed to **only initialize and control Group 1 GPIOs**. It never touches Group 2 GPIOs, ensuring both services can run simultaneously without any GPIO conflicts or interference.
- Tachometer pins are **adjacent** to their PWM pairs for clean wiring (odd pins in left column, even pins in right column).
- See **[src/fan/TACHOMETER_SETUP.md](src/fan/TACHOMETER_SETUP.md)** for complete tachometer wiring and setup instructions.

---

## Additional Resources

- **Detailed thermal control setup**: [src/fan/THERMAL_CONTROL.md](src/fan/THERMAL_CONTROL.md)
- **Fan configuration guide**: [src/fan/QUAD_FAN_SETUP.md](src/fan/QUAD_FAN_SETUP.md)
- **Project documentation**: [CLAUDE.md](CLAUDE.md)
- **Full README**: [README.md](README.md)
