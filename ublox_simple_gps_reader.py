#!/usr/bin/env python3
"""
Simple GPS reader - just show raw NMEA lines
"""
import time
from smbus2 import SMBus, i2c_msg

ADDR = 0x42
REG_AVAIL_HIGH = 0xFD
REG_DATA = 0xFF

bus = SMBus(1)
buffer = bytearray()

print("Reading u-blox GNSS via I2C...")
print("Waiting for data...")
print()

try:
    poll_count = 0
    last_data_time = time.time()

    while True:
        poll_count += 1

        try:
            # Check available bytes
            w = i2c_msg.write(ADDR, bytes([REG_AVAIL_HIGH]))
            r = i2c_msg.read(ADDR, 2)
            bus.i2c_rdwr(w, r)
            data = bytes(r)
            avail = data[0] | (data[1] << 8)

            if avail > 0:
                # Read data
                read_size = min(avail, 255)
                w = i2c_msg.write(ADDR, bytes([REG_DATA]))
                r = i2c_msg.read(ADDR, read_size)
                bus.i2c_rdwr(w, r)
                chunk = bytes(r)
                buffer.extend(chunk)
                last_data_time = time.time()

                # Process complete lines
                while b'\n' in buffer:
                    line_end = buffer.index(b'\n')
                    line = buffer[:line_end+1]
                    buffer = buffer[line_end+1:]

                    try:
                        line_str = line.decode('ascii').strip()
                        if line_str.startswith('$'):
                            # Print NMEA sentences
                            print(line_str)
                    except:
                        pass

            # Show periodic status
            if poll_count % 100 == 0:
                elapsed = time.time() - last_data_time
                print(f"[Status] Poll {poll_count}, Available: {avail}, Last data: {elapsed:.1f}s ago")

        except OSError as e:
            print(f"I2C Error: {e}")
            time.sleep(1)

        time.sleep(0.1)

except KeyboardInterrupt:
    print("\nStopped")
finally:
    bus.close()
