#!/usr/bin/env python3
"""
Quick GPS Diagnostic - Check satellite visibility
"""
import time
from smbus2 import SMBus, i2c_msg

# Configuration
I2C_BUS = 1
GPS_ADDR = 0x42
REG_AVAIL_HIGH = 0xFD
REG_DATA = 0xFF

def read_available(bus):
    """Check bytes available"""
    try:
        w = i2c_msg.write(GPS_ADDR, bytes([REG_AVAIL_HIGH]))
        r = i2c_msg.read(GPS_ADDR, 2)
        bus.i2c_rdwr(w, r)
        data = bytes(r)
        return data[0] | (data[1] << 8)
    except:
        return 0

def read_data(bus, nbytes):
    """Read data"""
    try:
        w = i2c_msg.write(GPS_ADDR, bytes([REG_DATA]))
        r = i2c_msg.read(GPS_ADDR, min(nbytes, 255))
        bus.i2c_rdwr(w, r)
        return bytes(r)
    except:
        return b''

print("=" * 70)
print("GPS DIAGNOSTIC - Satellite Visibility Check")
print("=" * 70)
print("Monitoring for 30 seconds...")
print("Looking for satellite count in NMEA messages")
print("-" * 70)

bus = SMBus(I2C_BUS)
buffer = bytearray()
satellites_seen = set()
fix_status = "?"
gga_quality = "0"

try:
    for i in range(300):  # 30 seconds
        avail = read_available(bus)
        if avail > 0:
            data = read_data(bus, avail)
            buffer.extend(data)

            while b'\n' in buffer:
                line_end = buffer.index(b'\n')
                line = buffer[:line_end+1]
                buffer = buffer[line_end+1:]

                try:
                    line_str = line.decode('ascii').strip()

                    # Parse RMC for fix status
                    if 'GNRMC' in line_str:
                        parts = line_str.split(',')
                        if len(parts) > 2:
                            fix_status = parts[2]

                    # Parse GGA for quality and satellite count
                    elif 'GNGGA' in line_str:
                        parts = line_str.split(',')
                        if len(parts) > 7:
                            gga_quality = parts[6] if parts[6] else "0"
                            num_sv = parts[7] if parts[7] else "00"
                            if i % 20 == 0:  # Print every 2 seconds
                                print(f"[{i//10:02d}s] Fix:{fix_status} Quality:{gga_quality} Satellites:{num_sv}")

                    # Parse GSV for satellite visibility
                    elif 'GSV' in line_str:
                        parts = line_str.split(',')
                        if len(parts) > 3:
                            num_satellites = parts[3]
                            if num_satellites and num_satellites.isdigit() and int(num_satellites) > 0:
                                satellites_seen.add(line_str[:7])  # e.g., "$GPGSV" or "$GLGSV"

                except:
                    pass

        time.sleep(0.1)

    print("-" * 70)
    print("\nDIAGNOSTIC RESULTS:")
    print(f"  Final Fix Status: {fix_status} (A=Active fix, V=No fix)")
    print(f"  GGA Quality: {gga_quality} (0=no fix, 1=GPS, 2=DGPS)")
    print(f"  Satellite constellations seen: {', '.join(satellites_seen) if satellites_seen else 'NONE'}")
    print()

    if not satellites_seen:
        print("⚠️  PROBLEM: NO SATELLITES VISIBLE")
        print()
        print("Possible causes:")
        print("  1. Antenna placement - needs clear sky view")
        print("  2. Active antenna not powered - antenna may need external power")
        print("  3. Antenna disconnected or faulty")
        print("  4. Indoor location - GPS requires outdoor/window placement")
        print()
        print("Recommendations:")
        print("  • Move antenna outdoors with clear sky view")
        print("  • Check antenna type (active vs passive)")
        print("  • Verify antenna connector is fully seated")
        print("  • If using active antenna, verify it's receiving power")
    else:
        print("✓ Satellites detected!")
        if fix_status == 'V':
            print("  Status: Satellites visible but no fix yet (normal during cold start)")
            print("  Action: Continue waiting for fix (can take 30-60 seconds)")
        else:
            print(f"  Status: GPS fix acquired! (Status: {fix_status})")

    print("=" * 70)

except KeyboardInterrupt:
    print("\n\nStopped by user")
finally:
    bus.close()
