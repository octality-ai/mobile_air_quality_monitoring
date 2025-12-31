#!/usr/bin/env python3
"""
Test script to check and configure active antenna support on NEO-M8U
This script queries the antenna configuration and attempts to enable active antenna power if needed.
"""

import smbus2
import time
from pyubx2 import UBXMessage, SET, POLL

# I2C configuration
I2C_BUS = 1
UBLOX_ADDR = 0x42

# UBX registers for u-blox I2C/DDC interface
REG_DATA_AVAILABLE_HIGH = 0xFD
REG_DATA_AVAILABLE_LOW = 0xFE
REG_DATA_STREAM = 0xFF

def read_ubx_i2c(bus, max_bytes=255):
    """Read UBX data from I2C interface with chunked reading"""
    MAX_CHUNK = 32  # Safe I2C read chunk size
    try:
        # Check how many bytes are available
        high_byte = bus.read_byte_data(UBLOX_ADDR, REG_DATA_AVAILABLE_HIGH)
        low_byte = bus.read_byte_data(UBLOX_ADDR, REG_DATA_AVAILABLE_LOW)
        bytes_available = (high_byte << 8) | low_byte

        if bytes_available == 0 or bytes_available == 0xFFFF:
            return None

        # Read data from stream register in chunks
        bytes_to_read = min(bytes_available, max_bytes)
        data = []

        for offset in range(0, bytes_to_read, MAX_CHUNK):
            chunk_size = min(MAX_CHUNK, bytes_to_read - offset)
            chunk = bus.read_i2c_block_data(UBLOX_ADDR, REG_DATA_STREAM, chunk_size)
            data.extend(chunk)
            time.sleep(0.01)  # Small delay between chunks

        return bytes(data)
    except Exception as e:
        print(f"Error reading I2C: {e}")
        return None

def write_ubx_i2c(bus, ubx_message):
    """Write UBX message to I2C interface"""
    try:
        # Serialize UBX message to bytes
        data = ubx_message.serialize()

        # Write in chunks to I2C stream register
        chunk_size = 32  # Safe chunk size for I2C
        for i in range(0, len(data), chunk_size):
            chunk = list(data[i:i+chunk_size])
            bus.write_i2c_block_data(UBLOX_ADDR, REG_DATA_STREAM, chunk)
            time.sleep(0.01)  # Small delay between chunks

        return True
    except Exception as e:
        print(f"Error writing I2C: {e}")
        return False

def parse_cfg_ant_response(data):
    """Parse CFG-ANT response to show antenna configuration"""
    # UBX-CFG-ANT structure:
    # Header: 0xB5 0x62 0x06 0x13
    # Length: 0x04 0x00 (4 bytes)
    # Payload: flags (2 bytes) + pins (2 bytes)
    # Checksum: 2 bytes

    if len(data) < 10:
        return None

    # Find UBX-CFG-ANT message (0xB5 0x62 0x06 0x13)
    for i in range(len(data) - 10):
        if data[i:i+4] == b'\xb5\x62\x06\x13':
            # Extract payload (skip header and length)
            flags = (data[i+7] << 8) | data[i+6]
            pins = (data[i+9] << 8) | data[i+8]

            return {
                'flags': flags,
                'pins': pins,
                'svcs_enabled': bool(flags & 0x0001),
                'scd_enabled': bool(flags & 0x0002),
                'ocd_enabled': bool(flags & 0x0004),
                'pdwn_on_scd': bool(flags & 0x0008),
                'recovery_enabled': bool(flags & 0x0010)
            }

    return None

def poll_cfg_ant(bus):
    """Poll CFG-ANT configuration to check antenna settings"""
    print("\n=== Polling CFG-ANT Configuration ===")

    # Create UBX-CFG-ANT poll message
    msg = UBXMessage('CFG', 'CFG-ANT', POLL)
    print(f"Sending: {msg}")

    if write_ubx_i2c(bus, msg):
        print("Poll message sent, waiting for response...")
        time.sleep(0.5)

        # Try to read response
        for attempt in range(5):
            response = read_ubx_i2c(bus, max_bytes=255)
            if response:
                print(f"Received response: {response.hex()}")

                # Parse the response
                config = parse_cfg_ant_response(response)
                if config:
                    print("\n✓ Antenna Configuration Decoded:")
                    print(f"  • Antenna Supervisor Enabled: {config['svcs_enabled']}")
                    print(f"  • Short Circuit Detection: {config['scd_enabled']}")
                    print(f"  • Open Circuit Detection: {config['ocd_enabled']}")
                    print(f"  • Power Down on Short: {config['pdwn_on_scd']}")
                    print(f"  • Automatic Recovery: {config['recovery_enabled']}")
                    print(f"  • Flags: 0x{config['flags']:04X}")
                    print(f"  • Pins: 0x{config['pins']:04X}")
                else:
                    print("  Could not parse antenna configuration")

                return response
            time.sleep(0.2)

        print("No response received")

    return None

def check_antenna_power():
    """Main function to check antenna power configuration"""
    print("=" * 60)
    print("NEO-M8U Active Antenna Power Test")
    print("=" * 60)

    try:
        # Open I2C bus
        bus = smbus2.SMBus(I2C_BUS)
        print(f"\n✓ Opened I2C bus {I2C_BUS}")

        # Try to communicate with NEO-M8U
        print(f"✓ Attempting to communicate with NEO-M8U at address 0x{UBLOX_ADDR:02X}")

        # Check if device responds
        try:
            high_byte = bus.read_byte_data(UBLOX_ADDR, REG_DATA_AVAILABLE_HIGH)
            print(f"✓ NEO-M8U is responding on I2C bus")
        except Exception as e:
            print(f"✗ Failed to communicate with NEO-M8U: {e}")
            print("\nTroubleshooting:")
            print("  1. Run 'i2cdetect -y 1' to verify device is at 0x42")
            print("  2. Check power and connections")
            print("  3. Ensure user is in 'i2c' group")
            return

        # Poll antenna configuration
        response = poll_cfg_ant(bus)

        print("\n" + "=" * 60)
        print("Hardware Test Recommendation")
        print("=" * 60)
        print("""
To physically verify active antenna power on the u.FL connector:

1. Power the NEO-M8U board via USB-C or Qwiic
2. Set multimeter to DC voltage measurement
3. Carefully probe:
   - RED (+): Center pin of u.FL connector
   - BLACK (GND): Any GND pin on the board

Expected Results:
  • Active antenna supported: ~3.3V DC
  • Passive antenna only: ~0V DC

CAUTION: Be very careful not to short the u.FL pins!

Recommended Active Antennas:
  • SparkFun GPS-14986: GPS/GNSS Magnetic Mount (28dB LNA)
  • SparkFun GPS-15192: Multi-Band Magnetic Mount

Passive Option (if no power detected):
  • SparkFun GPS-15246: Molex Flexible GNSS (requires external LNA)
        """)

        bus.close()

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_antenna_power()
