# Mobile Air Quality Monitor (MAQM)

A Raspberry Pi-based environmental sensor integration system that combines GPS location tracking with comprehensive air quality monitoring. This project integrates multiple sensors to provide real-time data logging of environmental conditions with precise geolocation.

## Features

- **GPS/GNSS Tracking**: u-blox GNSS module via I2C for position, speed, and altitude
- **Air Quality Monitoring**: Sensirion SEN66 sensor measuring:
  - Particulate Matter (PM1.0, PM2.5, PM4.0, PM10.0)
  - Volatile Organic Compounds (VOC) index
  - Nitrogen Oxides (NOx) index
  - CO2 equivalent
  - Temperature and humidity
- **Gas Sensing**: SpecSensor DGS2-970 sensors for CO, NO2, and O3 detection
- **Data Logging**: Buffered CSV output with configurable sampling rates
- **Production Ready**: Optimized for long-term operation with minimal SD card wear

## Hardware Requirements

### Platform
- Raspberry Pi (tested on Pi 5)
- I2C and UART interfaces enabled

### Sensors
- **Sensirion SEN66**: Air quality sensor (I2C address `0x6B`)
- **u-blox GNSS**: GPS module (I2C address `0x42`)
- **SpecSensor DGS2-970** (×3): Gas sensors for CO, NO2, and O3 (UART)

### Connections
- **I2C Bus**: Bus 1 (`/dev/i2c-1`)
  - SEN66 at address `0x6B`
  - u-blox GNSS at address `0x42`
- **Serial Ports**:
  - CO sensor: `/dev/ttyAMA1` (9600 baud)
  - NO2 sensor: `/dev/ttyAMA3` (9600 baud)
  - O3 sensor: `/dev/ttyAMA4` (9600 baud)

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

## Usage

### Main Data Logger

The primary application integrates all sensors and logs unified data:

```bash
python3 MAQM_main.py
```

**Features:**
- 1-second sampling interval
- 60-second buffered writes to CSV
- Real-time console output
- Graceful shutdown with Ctrl+C (flushes buffer)

**Output Format:**
- CSV files saved to `/home/mover/octa/`
- Filename: `MAQM_data_YYYYMMDD_HHMMSS.csv`
- Includes timestamp, GPS coordinates, air quality metrics, and gas concentrations

### Individual Sensor Scripts

#### SEN66 Air Quality Sensor

```bash
# Python implementation (recommended)
python3 Sensirion_sen66.py

# C implementation (embedded/performance)
cd raspberry-pi-i2c-sen66/example-usage
make
./sen66_i2c_example_usage
```

#### SpecSensor Gas Sensors

```bash
# Single measurement
python3 SpecSensor_Single.py

# Continuous logging (10-minute buffered writes)
python3 SpecSensor_ContinuousLogging.py
```

#### u-blox GPS Module

```bash
# Simple GPS reader
python3 ublox_simple_gps_reader.py

# Full-featured reader with configuration
python3 ublox_gnss_i2c.py

# Configure u-blox NMEA messages
python3 ublox_configure_ublox_i2c.py
```

## Project Structure

```
.
├── MAQM_main.py                    # Main integrated data logger
├── Sensirion_sen66.py              # SEN66 standalone reader
├── SpecSensor_Single.py            # Single gas sensor reading
├── SpecSensor_ContinuousLogging.py # Continuous gas sensor logging
├── ublox_gnss_i2c.py               # Full-featured GPS reader
├── ublox_simple_gps_reader.py      # Simplified GPS reader
├── ublox_configure_ublox_i2c.py    # GPS configuration utility
├── ublox_check_ublox_raw.py        # GPS raw data checker
├── requirements.txt                 # Python dependencies
├── CLAUDE.md                        # AI assistant documentation
└── raspberry-pi-i2c-sen66/         # C driver for SEN66 (vendor SDK)
    └── example-usage/
        ├── Makefile
        └── sen66_i2c_example_usage.c
```

## Configuration

Key configuration parameters in `MAQM_main.py`:

```python
# I2C Configuration
GNSS_I2C_BUS = 1
GNSS_I2C_ADDR = 0x42
SEN66_I2C_ADDR = 0x6B

# Serial Configuration
SPEC_CO_SERIAL_PORT = "/dev/ttyAMA1"
SPEC_NO2_SERIAL_PORT = "/dev/ttyAMA3"
SPEC_O3_SERIAL_PORT = "/dev/ttyAMA4"
SPEC_BAUDRATE = 9600

# Logging Configuration
CSV_BUFFER_INTERVAL = 60  # Write to CSV every 60 seconds
SAMPLE_INTERVAL = 1.0     # Sample every 1 second
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

CSV output includes the following fields:

| Category | Fields |
|----------|--------|
| **Timestamp** | ISO 8601 format |
| **GPS** | Latitude, longitude, altitude, speed, course, quality, satellite count, HDOP |
| **SEN66** | PM1.0, PM2.5, PM4.0, PM10.0, temperature, humidity, VOC index, NOx index, CO2 |
| **SpecSensor CO** | PPB, PPM, temperature, humidity, ADC values |
| **SpecSensor NO2** | PPB, PPM, temperature, humidity, ADC values |
| **SpecSensor O3** | PPB, PPM, temperature, humidity, ADC values |

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

**Note**: The vendor-provided SDKs (`python-i2c-sen66/` and `raspberry-pi-i2c-sen66/`) are licensed under BSD 3-Clause License by Sensirion AG.

## Credits

- **Sensirion AG**: SEN66 sensor drivers (BSD-3-Clause)
- **u-blox**: GNSS module protocol documentation
- **Spec Sensors**: DGS2-970 gas sensor specifications

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## Support

For issues related to:
- **Hardware connections**: Check wiring diagrams in vendor documentation
- **Software bugs**: Open an issue on GitHub
- **Sensor specifications**: Refer to manufacturer datasheets

---

**Project maintained by Octality Technologies Limited**
