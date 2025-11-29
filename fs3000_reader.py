#!/usr/bin/env python3
"""
FS3000-1005 Air Velocity Sensor Reader
Reads velocity measurements via I2C from a Renesas FS3000-1005 sensor.

Based on SparkFun Arduino Library:
https://github.com/sparkfun/SparkFun_FS3000_Arduino_Library
"""

import smbus2
import time
import sys

# I2C Configuration
FS3000_ADDRESS = 0x28
I2C_BUS = 1

# FS3000-1005 Lookup Table (0-7.23 m/s range)
# Raw ADC values from datasheet
RAW_DATA_POINTS = [409, 915, 1522, 2066, 2523, 2908, 3256, 3572, 3686]
# Corresponding velocities in m/s
MPS_DATA_POINTS = [0, 1.07, 2.01, 3.00, 3.97, 4.96, 5.98, 6.99, 7.23]


def read_raw_value(bus):
    """
    Read 5 bytes from FS3000 and extract 12-bit raw value.

    Data format: [checksum, data_high, data_low, generic1, generic2]
    Only the least significant 4 bits of data_high are valid.
    """
    # Read 5 bytes from the sensor
    data = bus.read_i2c_block_data(FS3000_ADDRESS, 0x00, 5)

    # Extract 12-bit value from bytes 1 and 2
    # High byte: only lower 4 bits are valid
    data_high = data[1] & 0x0F
    data_low = data[2]

    raw_value = (data_high << 8) | data_low
    return raw_value


def raw_to_velocity(raw_value):
    """
    Convert raw ADC value to velocity in m/s using linear interpolation.

    Uses the FS3000-1005 lookup table for conversion.
    """
    # Handle boundary cases
    if raw_value <= RAW_DATA_POINTS[0]:
        return MPS_DATA_POINTS[0]
    if raw_value >= RAW_DATA_POINTS[-1]:
        return MPS_DATA_POINTS[-1]

    # Find which interval the raw value falls into
    for i in range(len(RAW_DATA_POINTS) - 1):
        if raw_value < RAW_DATA_POINTS[i + 1]:
            # Linear interpolation between points i and i+1
            raw_window = RAW_DATA_POINTS[i + 1] - RAW_DATA_POINTS[i]
            mps_window = MPS_DATA_POINTS[i + 1] - MPS_DATA_POINTS[i]

            # Calculate position within window
            raw_offset = raw_value - RAW_DATA_POINTS[i]
            ratio = raw_offset / raw_window

            velocity = MPS_DATA_POINTS[i] + (ratio * mps_window)
            return velocity

    return MPS_DATA_POINTS[-1]


def main():
    """Continuously read and display velocity measurements."""
    print("FS3000-1005 Air Velocity Sensor Reader")
    print("=" * 40)
    print(f"I2C Bus: {I2C_BUS}, Address: 0x{FS3000_ADDRESS:02X}")
    print("Press Ctrl+C to stop\n")

    try:
        bus = smbus2.SMBus(I2C_BUS)
    except Exception as e:
        print(f"Error opening I2C bus: {e}")
        print("Make sure I2C is enabled and you have proper permissions.")
        print("Run: sudo adduser $USER i2c && sudo reboot")
        sys.exit(1)

    try:
        while True:
            try:
                raw_value = read_raw_value(bus)
                velocity_mps = raw_to_velocity(raw_value)
                velocity_mph = velocity_mps * 2.23694  # Convert to mph

                print(f"Raw: {raw_value:4d} | "
                      f"Velocity: {velocity_mps:5.2f} m/s | "
                      f"{velocity_mph:5.2f} mph")

            except IOError as e:
                print(f"I2C read error: {e}")
            except ValueError as e:
                print(f"Data error: {e}")

            time.sleep(0.5)  # Read every 500ms

    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        bus.close()
        print("Done.")


if __name__ == "__main__":
    main()
