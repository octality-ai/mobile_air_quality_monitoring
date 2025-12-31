# NEO-M8U Active Antenna Setup - Reference

## Hardware: SparkFun GPS Dead Reckoning Breakout - NEO-M8U (Qwiic)
**Product:** GPS-16329
**Module:** u-blox NEO-M8U
**Interface:** I2C address 0x42

## Active Antenna Support - CONFIRMED ✓

### Voltage Test Results
- **Measured voltage on u.FL connector:** 3.13V DC
- **VCC_RF pin:** Connected and providing power for active antennas
- **Expected current draw:** 5-20mA (typical for active GPS antennas)

### Key Finding
The NEO-M8U module **lacks internal LNA/filter** and is designed primarily for **active antennas**. Passive antennas require external amplification/filtering circuitry on the board.

## Antenna Used
**SparkFun GPS-14986: GPS/GNSS Magnetic Mount Antenna - 3m (SMA)**
- Type: **ACTIVE**
- LNA Gain: 28dB
- LNA Current: 10mA
- Frequency: 1575-1610MHz
- Supports: GPS + GLONASS

## Software Configuration

### Antenna Supervisor Status
```
Flags: 0x0000 (Factory Default)
- Antenna Supervisor: Disabled
- Short Circuit Detection: Disabled
- Open Circuit Detection: Disabled
- Power: Always ON (no supervisor control needed)
```

**Note:** Antenna power is provided regardless of supervisor settings. The supervisor features are optional safety mechanisms for fault detection.

## Scripts Created

### 1. test_antenna_power.py
Tests I2C communication and queries CFG-ANT configuration
```bash
python3 test_antenna_power.py
```

### 2. read_gps_coordinates.py
Real-time GPS coordinate reader with live display
```bash
python3 read_gps_coordinates.py
```
**Features:**
- Displays lat/lon in decimal degrees
- Shows satellite count and fix quality
- Provides Google Maps link
- HDOP and altitude data
- Works with NMEA GGA messages

## Testing Results
- ✓ Active antenna power confirmed (3.13V)
- ✓ I2C communication working at 0x42
- ✓ GPS coordinates successfully acquired
- ✓ SparkFun GPS-14986 antenna working correctly

## Recommendations

### Active Antennas (Recommended)
- SparkFun GPS-14986 (current - working)
- SparkFun GPS-15192 (multi-band L1/L2)

### Passive Antennas
- SparkFun GPS-15246 (Molex flexible)
- **Note:** Requires external LNA - not ideal for NEO-M8U

## Important Notes
- Cold start GPS acquisition: 30-60 seconds
- Warm start (with battery backup): 1-2 seconds
- Antenna needs clear sky view for best performance
- No software configuration required for basic active antenna use

## References
- [SparkFun NEO-M8U Hookup Guide](https://learn.sparkfun.com/tutorials/sparkfun-gps-dead-reckoning-neo-m8u-hookup-guide/all)
- [u-blox NEO-M8U Hardware Integration Manual](https://cdn.sparkfun.com/assets/7/0/f/5/d/NEO-M8U_HardwareIntegrationManual__UBX-15016700_.pdf)
- [SparkFun GPS-14986 Product Page](https://www.sparkfun.com/products/14986)

---
*Last Updated: 2025-12-31*
