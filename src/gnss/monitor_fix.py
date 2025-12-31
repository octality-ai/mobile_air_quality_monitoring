#!/usr/bin/env python3
"""
Simple GPS Fix Monitor - Watch for satellites to lock
"""
import time
from smbus2 import SMBus, i2c_msg

I2C_BUS = 1
GPS_ADDR = 0x42

bus = SMBus(I2C_BUS)
buffer = bytearray()

print("=" * 80)
print("GPS FIX MONITOR - Watching for satellite lock")
print("=" * 80)
print("Satellites in view mean antenna is working!")
print("Waiting for GPS to decode navigation messages and get fix...")
print("This can take 30-120 seconds for cold start.")
print()
print("Press Ctrl+C to stop")
print("-" * 80)
print()

last_print = 0
start_time = time.time()

try:
    while True:
        # Read data
        w = i2c_msg.write(GPS_ADDR, bytes([0xFD]))
        r = i2c_msg.read(GPS_ADDR, 2)
        bus.i2c_rdwr(w, r)
        avail = (bytes(r)[1] << 8) | bytes(r)[0]

        if avail > 0:
            w = i2c_msg.write(GPS_ADDR, bytes([0xFF]))
            r = i2c_msg.read(GPS_ADDR, min(avail, 512))
            bus.i2c_rdwr(w, r)
            buffer.extend(bytes(r))

            while b'\n' in buffer:
                line_end = buffer.index(b'\n')
                line = buffer[:line_end+1]
                buffer = buffer[line_end+1:]

                try:
                    line_str = line.decode('ascii').strip()
                    now = time.time()

                    # RMC - Check for fix
                    if '$GNRMC' in line_str or '$GPRMC' in line_str:
                        parts = line_str.split(',')
                        if len(parts) > 2:
                            status = parts[2]
                            if status == 'A':
                                elapsed = int(now - start_time)
                                print(f"\n{'='*80}")
                                print(f"✓✓✓ GPS FIX ACQUIRED after {elapsed} seconds! ✓✓✓")
                                print(f"{'='*80}")
                                print(f"\n{line_str}\n")
                                print("GPS is now working! Run: python3 gps_test.py")
                                print(f"{'='*80}")
                                exit(0)

                    # GGA - Satellites in use
                    if '$GNGGA' in line_str or '$GPGGA' in line_str:
                        parts = line_str.split(',')
                        if len(parts) > 7:
                            sats = parts[7] if parts[7] else '0'
                            quality = parts[6] if parts[6] else '0'

                            if now - last_print >= 2.0:  # Print every 2 seconds
                                elapsed = int(now - start_time)
                                print(f"[{elapsed:3d}s] Quality:{quality} Sats in use:{sats}")
                                last_print = now

                except:
                    pass

        time.sleep(0.1)

except KeyboardInterrupt:
    print("\n\nStopped by user")
    print(f"Total time: {int(time.time() - start_time)} seconds")
    print("\nNo fix acquired yet. This could mean:")
    print("  1. Need more time (cold start can take up to 12 minutes in poor conditions)")
    print("  2. Signal strength too weak (need better antenna placement)")
    print("  3. Active antenna not getting power (despite satellites being visible)")
finally:
    bus.close()
