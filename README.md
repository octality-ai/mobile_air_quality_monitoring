# Mobile Air Quality Monitor (MAQM)

A Raspberry Pi-based environmental sensor integration system that combines GPS location tracking with comprehensive air quality monitoring. This project integrates multiple sensors to provide real-time data logging of environmental conditions with precise geolocation.

## Features

- **GPS/GNSS Tracking**: u-blox NEO-M8U GNSS module via I2C for position, speed, altitude, and precision metrics (PDOP/HDOP/VDOP)
- **Air Quality Monitoring**: Sensirion SEN66 sensor measuring:
  - Particulate Matter (PM1.0, PM2.5, PM4.0, PM10.0)
  - Volatile Organic Compounds (VOC) index
  - Nitrogen Oxides (NOx) index
  - CO2 equivalent
  - Temperature and humidity
- **Gas Sensing**: SpecSensor DGS2-970 sensors for CO, NO2, and O3 detection via UART
- **Active Air Sampling**: Automated PWM fan control (Group 2) during data collection for consistent air flow
- **Thermal Management**: Independent heat sink fan control (Group 1) based on CPU temperature
- **Data Logging**: Buffered CSV output with 1-second sampling and 60-second writes
- **Production Ready**: systemd service integration for auto-start, optimized for long-term operation with minimal SD card wear

## Hardware Requirements

### Platform
- Raspberry Pi (tested on Pi 5)
- I2C, UART, and hardware PWM interfaces enabled

### Sensors
- **Sensirion SEN66**: Air quality sensor (I2C address `0x6B`)
- **u-blox NEO-M8U GNSS**: GPS module with active antenna (I2C address `0x42`)
- **SpecSensor DGS2-970** (×3): Gas sensors for CO, NO2, and O3 (UART)

### Connections
- **I2C Bus**: Bus 1 (`/dev/i2c-1`)
  - SEN66 at address `0x6B`
  - u-blox GNSS at address `0x42`
- **Serial Ports**:
  - CO sensor: `/dev/ttyAMA0` (9600 baud)
  - O3 sensor: `/dev/ttyAMA1` (9600 baud)
  - NO2 sensor: `/dev/ttyAMA3` (9600 baud)
- **PWM Fans** (25 kHz hardware PWM):
  - **Group 1** (Heat Sink): GPIO12 (Pin 32), GPIO18 (Pin 12) - Controlled by `thermal-fan-control.service`
  - **Group 2** (Air Sampling): GPIO13 (Pin 33), GPIO19 (Pin 35) - Controlled by `maqm-logger.service`

## Installation

### 1. System Prerequisites

Enable I2C and UART on your Raspberry Pi:

```bash
# Enable I2C interface
sudo raspi-config
# Navigate to: Interface Options → I2C → Enable

# Add user to i2c group
sudo usermod -a -G i2c $USER
sudo reboot
```

### 2. Clone Repository

```bash
git clone <repository-url>
cd octa
```

### 3. Install Python Dependencies

```bash
# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate

# Install required packages
pip install -r requirements.txt
```

### 4. Verify Hardware

```bash
# Scan I2C bus for connected devices
i2cdetect -y 1

# Expected output should show:
# 0x42 (u-blox GNSS)
# 0x6B (SEN66)

# Check serial ports
ls -l /dev/ttyAMA*
```

## Quick Start

For daily operation commands, see **[QUICKSTART.md](QUICKSTART.md)** for service management, GPS debugging, and emergency controls.

## Usage

### Production Deployment (Recommended)

The MAQM system runs as a systemd service for automatic startup and reliability:

```bash
# Install and enable the service
cd /home/octa/octa/src
sudo ./install_maqm_service.sh

# Service management
sudo systemctl start maqm-logger.service     # Start logging
sudo systemctl stop maqm-logger.service      # Stop logging
sudo systemctl status maqm-logger.service    # Check status
sudo journalctl -u maqm-logger.service -f    # View live logs

# Enable auto-start at boot
sudo systemctl enable maqm-logger.service
```

### Manual Execution

For testing or development, run the logger manually:

```bash
cd /home/octa/octa/src
sudo /home/octa/.octa/bin/python3 MAQM_main.py
```

**Features:**
- 1-second sampling interval
- 60-second buffered writes to CSV
- Real-time console output with GPS fix status, air quality, and gas measurements
- Graceful shutdown with Ctrl+C (flushes buffer before exit)
- Automatic Group 2 fan control at 40% speed for air sampling

**Output Format:**
- CSV files saved to `/home/octa/octa/data/`
- Filename: `MAQM_data_YYYYMMDD_HHMMSS.csv`
- Includes timestamp, GPS coordinates (with PDOP/HDOP/VDOP), air quality metrics, and gas concentrations

### Individual Sensor Scripts

For standalone sensor testing and development:

#### SEN66 Air Quality Sensor

```bash
# Python implementation (recommended)
cd /home/octa/octa/src/sen66
python3 Sensirion_sen66.py

# C implementation (embedded/performance)
cd /home/octa/octa/raspberry-pi-i2c-sen66/example-usage
make
./sen66_i2c_example_usage
```

#### SpecSensor Gas Sensors

```bash
cd /home/octa/octa/src/spec_sensors

# Single measurement
python3 SpecSensor_Single.py

# Continuous logging (10-minute buffered writes)
python3 SpecSensor_ContinuousLogging.py
```

#### u-blox GPS Module

```bash
cd /home/octa/octa/src/gps

# Quick coordinate reader with Google Maps link (RECOMMENDED)
python3 read_gps_coordinates.py

# Comprehensive GPS diagnostic tool
sudo python3 gps_diagnostic.py

# Configure active antenna
python3 configure_antenna.py

# Enable multi-GNSS constellations
python3 enable_multi_gnss.py
```

#### Thermal Fan Control

```bash
cd /home/octa/octa/src/fan

# Install thermal fan control service (auto-start at boot)
./install_thermal_service.sh

# Manual test (Group 1 heat sink fans only)
sudo /home/octa/.octa/bin/python3 thermal_fan_controller.py

# Test both fan groups independently
sudo /home/octa/.octa/bin/python3 dual_fan_controller.py
```

## Project Structure

```
/home/octa/octa/
├── CLAUDE.md                        # AI assistant documentation
├── README.md                        # This file
├── QUICKSTART.md                    # Daily operation quick reference
├── requirements.txt                 # Python dependencies
├── data/                            # CSV data output directory
├── src/                            # Main source code
│   ├── MAQM_main.py                # Main integrated data logger
│   ├── maqm-logger.service         # systemd service for MAQM
│   ├── install_maqm_service.sh     # Service installer script
│   ├── start_maqm_logger.sh        # Service startup wrapper
│   ├── fan/                        # Fan control modules
│   │   ├── thermal_fan_controller.py    # Group 1 thermal control
│   │   ├── dual_fan_controller.py       # Dual-group PWM controller
│   │   ├── thermal-fan-control.service  # systemd service for thermal control
│   │   ├── install_thermal_service.sh   # Thermal service installer
│   │   ├── THERMAL_CONTROL.md           # Thermal control documentation
│   │   └── QUAD_FAN_SETUP.md            # Hardware setup guide
│   ├── gps/                        # GPS/GNSS modules
│   │   ├── read_gps_coordinates.py      # Quick coordinate reader
│   │   ├── gps_diagnostic.py            # Comprehensive diagnostics
│   │   ├── configure_antenna.py         # Active antenna setup
│   │   └── enable_multi_gnss.py         # Multi-constellation config
│   ├── sen66/                      # SEN66 air quality sensor
│   │   └── Sensirion_sen66.py           # Standalone SEN66 reader
│   ├── spec_sensors/               # SpecSensor gas modules
│   │   ├── SpecSensor_Single.py         # Single measurement
│   │   └── SpecSensor_ContinuousLogging.py  # Continuous logging
│   └── others/                     # Archive/experimental code
└── raspberry-pi-i2c-sen66/         # C driver for SEN66 (vendor SDK)
    └── example-usage/
        ├── Makefile
        └── sen66_i2c_example_usage.c
```

## Configuration

Key configuration parameters in `src/MAQM_main.py`:

```python
# GNSS Configuration
GNSS_I2C_BUS = 1
GNSS_I2C_ADDR = 0x42
GNSS_MAX_CHUNK = 32

# SEN66 Configuration
SEN66_I2C_PORT = '/dev/i2c-1'
SEN66_I2C_ADDR = 0x6B

# SpecSensor Configuration
SPEC_CO_SERIAL_PORT = "/dev/ttyAMA0"
SPEC_O3_SERIAL_PORT = "/dev/ttyAMA1"
SPEC_NO2_SERIAL_PORT = "/dev/ttyAMA3"
SPEC_BAUDRATE = 9600

# Logging Configuration
CSV_BUFFER_INTERVAL = 60  # Write to CSV every 60 seconds
SAMPLE_INTERVAL = 1.0     # Sample every 1 second

# Fan Configuration
FAN_SPEED_PERCENT = 40    # Air sampling fan speed (Group 2)
```

## Troubleshooting

### I2C Device Not Found

```bash
# Check I2C devices
i2cdetect -y 1

# Verify user permissions
groups  # Should include 'i2c'

# Add user to i2c group if missing
sudo usermod -a -G i2c $USER
sudo reboot
```

### Serial Port Permission Denied

```bash
# Add user to dialout group
sudo usermod -a -G dialout $USER
sudo reboot
```

### GPS Not Getting Fix

- Ensure clear sky view (30-60 second cold start time)
- Check antenna connection
- Verify I2C communication with `i2cdetect -y 1`

### Long I2C Cable Runs

For cable lengths >30cm, adjust chunk size in GPS reader:

```python
GNSS_MAX_CHUNK = 16  # Reduce from 32 for stability
```

## Development

### Running Tests (SEN66 Driver)

```bash
cd python-i2c-sen66
pip install -e .[test]
pytest tests/
```

### Code Linting

```bash
cd python-i2c-sen66
flake8
editorconfig-checker
```

### Building C Driver

```bash
cd raspberry-pi-i2c-sen66/example-usage
make clean
make
```

## Data Format

CSV output (`/home/octa/octa/data/MAQM_data_YYYYMMDD_HHMMSS.csv`) includes the following fields:

| Category | Fields |
|----------|--------|
| **Timestamp** | ISO 8601 format |
| **GNSS** | Latitude, longitude, altitude, speed, fix status (A/V), quality, satellite count, PDOP, HDOP, VDOP |
| **SEN66** | PM1.0, PM2.5, PM4.0, PM10.0, temperature, humidity, VOC index, NOx index, CO2 equivalent |
| **SpecSensor CO** | Sensor SN, PPB, PPM, temperature, humidity, ADC values (G, T, H) |
| **SpecSensor NO2** | Sensor SN, PPB, PPM, temperature, humidity, ADC values (G, T, H) |
| **SpecSensor O3** | Sensor SN, PPB, PPM, temperature, humidity, ADC values (G, T, H) |

**GPS Precision Metrics:**
- **PDOP** (Position Dilution of Precision): Overall 3D position accuracy
- **HDOP** (Horizontal Dilution of Precision): Horizontal (lat/lon) accuracy
- **VDOP** (Vertical Dilution of Precision): Altitude accuracy
- Lower values indicate better precision (< 2 excellent, 2-5 good, 5-10 moderate, > 10 poor)

## System Services

The MAQM platform uses two independent systemd services that run simultaneously without conflict:

### 1. MAQM Data Logger Service (`maqm-logger.service`)
- **Controls**: Group 2 fans (GPIO13, GPIO19) for air sampling at 40% speed
- **Purpose**: Continuous environmental data logging
- **Auto-restart**: On failure
- **Location**: `/home/octa/octa/src/`

### 2. Thermal Fan Control Service (`thermal-fan-control.service`)
- **Controls**: Group 1 fans (GPIO12, GPIO18) for heat sink cooling
- **Purpose**: CPU temperature-based thermal management
- **Auto-restart**: On failure
- **Location**: `/home/octa/octa/src/fan/`

**Key Design Feature**: The services are designed with strict GPIO separation—thermal control never touches Group 2 GPIOs, and MAQM logger never touches Group 1 GPIOs, ensuring zero conflict.

See **[QUICKSTART.md](QUICKSTART.md)** for service management commands.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

**Note**: The vendor-provided SDKs (`python-i2c-sen66/` and `raspberry-pi-i2c-sen66/`) are licensed under BSD 3-Clause License by Sensirion AG.

## Credits

- **Sensirion AG**: SEN66 sensor drivers (BSD-3-Clause)
- **u-blox**: GNSS module protocol documentation
- **Spec Sensors**: DGS2-970 gas sensor specifications

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## Documentation

- **[QUICKSTART.md](QUICKSTART.md)**: Daily operation commands and service management
- **[CLAUDE.md](CLAUDE.md)**: Developer documentation and AI assistant guidance
- **[src/fan/THERMAL_CONTROL.md](src/fan/THERMAL_CONTROL.md)**: Thermal fan control setup
- **[src/fan/QUAD_FAN_SETUP.md](src/fan/QUAD_FAN_SETUP.md)**: Hardware wiring and PWM configuration

## Support

For issues related to:
- **Daily operations**: See [QUICKSTART.md](QUICKSTART.md) for common commands
- **Hardware connections**: Check wiring diagrams in `src/fan/QUAD_FAN_SETUP.md`
- **GPS troubleshooting**: Use `gps_diagnostic.py` for comprehensive diagnostics
- **Software bugs**: Open an issue on GitHub
- **Sensor specifications**: Refer to manufacturer datasheets

---

**Project maintained by Octality Technologies Limited**
