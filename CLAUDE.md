# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Raspberry Pi sensor integration project for reading environmental and GPS data via I2C and UART interfaces, with hardware PWM pump control. The codebase combines:
- **Sensirion SEN66** air quality sensor (PM, VOC, NOx, CO2, temperature, humidity) via I2C
- **DGS2-970** gas sensor via UART/serial
- **u-blox GNSS** GPS module via I2C/DDC interface
- **4-wire PWM pump** with speed control and tachometer feedback via hardware PWM

## Hardware Configuration

- **Platform**: Raspberry Pi (tested on Pi 5)
- **I2C Bus**: Bus 1 (default)
- **I2C Devices**:
  - SEN66: Address `0x6B` (default)
  - u-blox GNSS: Address `0x42` (default)
- **Serial**: `/dev/serial0` at 9600 baud (DGS2-970 sensor)
- **PWM Control**:
  - GPIO12 (Physical Pin 32): 4-wire pump PWM control OR Fan Group 1 at 25 kHz
  - GPIO13 (Physical Pin 33): Fan Group 2 at 25 kHz
  - GPIO18 (Physical Pin 12): Fan Group 1 at 25 kHz
  - GPIO19 (Physical Pin 35): Fan Group 2 at 25 kHz
  - GPIO23 (Physical Pin 16): Tachometer feedback input (pump only)

## Common Commands

### Python Environment
```bash
# Install SEN66 Python driver dependencies
cd python-i2c-sen66
pip install -e .[test]

# Run linting
flake8
editorconfig-checker
```

### C Driver (Raspberry Pi)
```bash
# Build the C driver for SEN66
cd raspberry-pi-i2c-sen66/example-usage
make

# Run the example
./sen66_i2c_example_usage
```

### Running Sensor Scripts
```bash
# Single DGS2-970 measurement (UART/serial)
python3 sensor_test.py

# Continuous logging with buffered CSV output
python3 continuous_logger.py

# u-blox GPS via I2C (simplified version)
python3 test_ublox_gps.py

# u-blox GPS via I2C (full-featured)
python3 ublox_gnss_i2c.py
```

### Running Pump Controller
```bash
# Basic pump test (ramps through speeds, displays RPM)
sudo /home/octa/.octa/bin/python3 pump_controller.py

# Interactive demo with keyboard controls
sudo /home/octa/.octa/bin/python3 pump_demo.py

# Emergency stop (if pump is running)
sudo pinctrl set 12 op dh
```

### Running Thermal Fan Controller
```bash
# Manual test (watch fans respond to CPU temperature)
cd /home/octa/octa/src/fan
sudo /home/octa/.octa/bin/python3 thermal_fan_controller.py

# Install as systemd service (auto-start at boot)
cd /home/octa/octa/src/fan
./install_thermal_service.sh

# Check service status
sudo systemctl status thermal-fan-control.service

# View live logs
sudo journalctl -u thermal-fan-control.service -f

# Emergency stop all fans
for gpio in 12 13 18 19; do sudo pinctrl set $gpio op dl; done
```

### I2C Troubleshooting
```bash
# Scan for I2C devices
i2cdetect -y 1

# Check user permissions
groups  # Should include 'i2c' group

# Add user to i2c group if missing
sudo adduser $USER i2c
sudo reboot
```

## Code Architecture

### Python SEN66 Driver (`python-i2c-sen66/`)
- **Core Module**: `sensirion_i2c_sen66/`
  - `device.py`: Main `Sen66DeviceBase` and `Sen66Device` classes for sensor interface
  - `commands.py`: I2C command definitions (start/stop measurement, read values, calibration, etc.)
  - `result_types.py`: Typed signal classes for sensor data (PM, VOC, NOx, CO2, temp, humidity)
- **Architecture**: Uses Sensirion's driver framework with adapters and transfer execution pattern
- **Dependencies**: `sensirion-i2c-driver`, `sensirion-driver-adapters`, `sensirion-driver-support-types`

### C SEN66 Driver (`raspberry-pi-i2c-sen66/`)
- **Driver**: `sen66_i2c.c/h` - Main sensor driver implementation
- **HAL**: `sensirion_i2c_hal.c/h` - Hardware abstraction for I2C on Raspberry Pi
- **Framework**: `sensirion_i2c.c/h`, `sensirion_common.c/h` - Sensirion I2C framework
- **Build**: Uses Makefile in `example-usage/` directory

### UART Sensor Scripts
- **`sensor_test.py`**: Simple single-shot reader for DGS2-970 gas sensor
  - Sends `\r` to trigger measurement
  - Parses CSV format: `SN, PPB, TEMP, RH, ADC_G, ADC_T, ADC_H`
  - Scales values: ppb→ppm, temp/100→°C, rh/100→%

- **`continuous_logger.py`**: Production logging script
  - Buffers measurements in memory
  - Writes to CSV every 10 minutes (configurable via `BUFFER_WRITE_INTERVAL`)
  - Gracefully handles Ctrl+C, flushing buffer before exit

### GPS/GNSS Scripts
- **`test_ublox_gps.py`**: Simplified u-blox reader
  - Reads NMEA and UBX protocols via I2C DDC interface
  - Uses `pyubx2` and `pynmeagps` for parsing
  - Handles RMC, GGA position messages

- **`ublox_gnss_i2c.py`**: Full-featured GPS reader
  - Configures u-blox module via UBX CFG-PRT and CFG-MSG commands
  - Enables NMEA GGA, RMC, GSA, GSV on I2C port
  - Supports both NMEA text and UBX binary protocols
  - Robust I2C chunking (`MAX_CHUNK=32`) for reliable cable lengths
  - Converts NMEA ddmm.mmmm → decimal degrees

### I2C Communication Pattern
All I2C communication uses registers:
- `0xFD/0xFE`: Data available (high/low bytes) - u-blox specific
- `0xFF`: Data stream register for read/write - u-blox specific
- SEN66 uses standard I2C without special registers

### Pump Controller Scripts
- **`pump_controller.py`**: 4-wire PWM pump controller library
  - Hardware PWM at 25 kHz for smooth speed control (10-30 kHz range)
  - Inverted logic handling (LOW=run, HIGH=stop) built-in
  - Tachometer feedback for real-time RPM monitoring
  - Automatic GPIO configuration (sets GPIO12 to PWM mode on startup)
  - Safe cleanup (sets GPIO12 HIGH on exit to ensure pump stops)
  - API: `set_speed_percent(0-100)`, `get_rpm()`, `ramp_speed()`

- **`pump_demo.py`**: Interactive keyboard-controlled demo
  - Real-time speed and RPM display
  - Arrow keys for speed adjustment
  - Smooth ramping and instant stop controls

### Thermal Fan Controller Scripts (`src/fan/`)
- **`thermal_fan_controller.py`**: Automatic CPU temperature-based fan control
  - Reads CPU temperature from `/sys/class/thermal/thermal_zone0/temp`
  - Two modes: smooth temperature curve (default) or follow Pi's fan states
  - Controls 4 PWM fans in 2 groups (heat sink + air sampling)
  - Smart logging: verbose in terminal, quiet when running as service
  - Auto-restart on failure via systemd
  - Resource usage: ~13MB RAM, 0.05% CPU

- **`dual_fan_controller.py`**: Dual-group PWM fan control library
  - Group 1 (GPIO12, GPIO18): Heat sink fans
  - Group 2 (GPIO13, GPIO19): Air sampling fans
  - Hardware PWM at 25 kHz
  - Independent speed control per group

- **`start_thermal_control.sh`**: Wrapper script for systemd service
  - Sets working directory and executes thermal controller
  - Allows easy parameter modification

- **`thermal-fan-control.service`**: systemd service definition
  - Auto-start at boot
  - Auto-restart on crash (10s delay)
  - Minimal configuration for maximum reliability

- **`install_thermal_service.sh`**: One-command service installer
  - Copies service file to /etc/systemd/system/
  - Enables and starts service
  - Shows status and useful commands

### Key Dependencies
- **smbus2**: Low-level I2C communication
- **pyserial**: UART/serial communication
- **pyubx2**: UBX protocol parsing
- **pynmeagps**: NMEA protocol parsing
- **sensirion-*** packages**: SEN66 driver framework
- **rpi-hardware-pwm**: Hardware PWM access for pump control (Pi 5 required)
- **gpiozero + lgpio**: GPIO input for tachometer (Pi 5 compatible)

## Development Notes

- All Python scripts are standalone and can run directly
- The SEN66 has both Python and C implementations (use Python for prototyping, C for embedded)
- I2C bus speed and chunk size may need tuning for longer cable runs
- The continuous logger buffers to minimize SD card writes (important for Pi longevity)
- GPS requires clear sky view; expect 30-60s cold start time for first fix
- **Pump controller requires sudo** due to `pinctrl` commands for GPIO configuration
- **Hardware PWM setup required**: Install `rpi-hardware-pwm` and enable `dtoverlay=pwm-2chan` in `/boot/firmware/config.txt`
- **Pump uses inverted logic**: LOW (0V) = full speed, HIGH (3.3V) = stopped (code handles this automatically)
- **See PUMP_CONTROLLER_GUIDE.md** for complete pump setup, wiring, and troubleshooting
- **Thermal fan controller runs as systemd service**: Auto-starts at boot, auto-restarts on crash
- **Fan PWM uses normal logic**: HIGH = run, LOW = stopped (opposite of pump)
- **Python is optimal for thermal control**: 13MB RAM overhead is negligible vs. maintainability benefits
- **See THERMAL_CONTROL.md** for complete thermal fan setup and service configuration
