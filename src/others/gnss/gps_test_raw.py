#!/usr/bin/env python3
"""
GPS Raw Data Test - Quick Communication Check
Shows raw I2C buffer contents for troubleshooting

Usage: python3 gps_test_raw.py
"""
import time
from smbus2 import SMBus, i2c_msg

# Configuration
I2C_BUS = 1
GPS_ADDR = 0x42
REG_AVAIL_HIGH = 0xFD
REG_DATA = 0xFF

print("=" * 70)
print("GPS RAW DATA TEST")
print("=" * 70)
print("This shows raw I2C buffer data to verify GPS communication.")
print("Press Ctrl+C to exit")
print("=" * 70)
print()

bus = SMBus(I2C_BUS)

try:
    for i in range(20):
        try:
            # Check available bytes
            w = i2c_msg.write(GPS_ADDR, bytes([REG_AVAIL_HIGH]))
            r = i2c_msg.read(GPS_ADDR, 2)
            bus.i2c_rdwr(w, r)
            data = bytes(r)
            avail = data[0] | (data[1] << 8)

            print(f"[{i:02d}] Available: {avail:5d} bytes", end="")

            if avail > 0:
                # Read first 80 bytes to see what's there
                read_size = min(avail, 80)
                w = i2c_msg.write(GPS_ADDR, bytes([REG_DATA]))
                r = i2c_msg.read(GPS_ADDR, read_size)
                bus.i2c_rdwr(w, r)
                chunk = bytes(r)

                # Show as hex and ASCII
                print(f" | First {read_size} bytes:")
                print(f"    Hex:   {chunk[:40].hex()}")
                try:
                    ascii_data = chunk.decode('ascii', errors='replace')
                    # Clean up non-printable characters
                    ascii_clean = ''.join(c if c.isprintable() or c == '\n' else '.' for c in ascii_data)
                    print(f"    ASCII: {ascii_clean[:70]}")
                except:
                    print(f"    ASCII: [not decodable]")
            else:
                print()

        except OSError as e:
            print(f"[{i:02d}] I2C Error: {e}")

        time.sleep(0.5)

    print()
    print("=" * 70)
    print("Test complete!")
    print()
    print("What to look for:")
    print("  ✓ Available > 0         - GPS is sending data")
    print("  ✓ ASCII starts with $   - Valid NMEA sentences")
    print("  ✓ See GNRMC, GNGGA      - GPS message types")
    print("  ✗ Available = 0         - Check GPS power/wiring")
    print("  ✗ I2C Error             - Check I2C address (should be 0x42)")
    print("=" * 70)

except KeyboardInterrupt:
    print("\n\nStopped by user")
finally:
    bus.close()
