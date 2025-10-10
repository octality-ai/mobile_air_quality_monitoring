#!/usr/bin/env python3
"""
Raw I2C data check - see what's actually in the buffer
"""
import time
from smbus2 import SMBus, i2c_msg

ADDR = 0x42
REG_AVAIL_HIGH = 0xFD
REG_DATA = 0xFF

bus = SMBus(1)

print("Checking raw u-blox I2C buffer...")
print("Press Ctrl+C to exit")
print()

try:
    for i in range(20):  # Check 20 times over 10 seconds
        try:
            # Read available bytes
            w = i2c_msg.write(ADDR, bytes([REG_AVAIL_HIGH]))
            r = i2c_msg.read(ADDR, 2)
            bus.i2c_rdwr(w, r)
            data = bytes(r)
            avail = data[0] | (data[1] << 8)

            print(f"[{i}] Available: {avail} bytes", end="")

            if avail > 0:
                # Read first 64 bytes to see what's there
                read_size = min(avail, 64)
                w = i2c_msg.write(ADDR, bytes([REG_DATA]))
                r = i2c_msg.read(ADDR, read_size)
                bus.i2c_rdwr(w, r)
                chunk = bytes(r)

                # Show as hex and try to decode as ASCII
                print(f" | First {read_size} bytes:")
                print(f"    Hex: {chunk[:32].hex()}")
                try:
                    ascii_data = chunk.decode('ascii', errors='replace')
                    print(f"    ASCII: {ascii_data[:60]}")
                except:
                    print(f"    ASCII: [not decodable]")
            else:
                print()

        except OSError as e:
            print(f"[{i}] I2C Error: {e}")

        time.sleep(0.5)

except KeyboardInterrupt:
    print("\nDone")
finally:
    bus.close()
