#!/usr/bin/env python3
"""
Final GPS Diagnosis - Comprehensive Hardware and Software Check
"""
import time
from smbus2 import SMBus, i2c_msg

I2C_BUS = 1
GPS_ADDR = 0x42

print("=" * 80)
print("FINAL GPS DIAGNOSIS")
print("=" * 80)
print()

bus = SMBus(I2C_BUS)

try:
    # Test 1: I2C Communication
    print("TEST 1: I2C Communication")
    print("-" * 80)
    try:
        w = i2c_msg.write(GPS_ADDR, bytes([0xFD]))
        r = i2c_msg.read(GPS_ADDR, 2)
        bus.i2c_rdwr(w, r)
        print("✓ I2C communication: WORKING")
    except Exception as e:
        print(f"✗ I2C communication: FAILED - {e}")
        exit(1)

    # Test 2: NMEA Data Flow
    print("\nTEST 2: NMEA Data Flow")
    print("-" * 80)
    buffer = bytearray()
    nmea_found = False
    ubx_found = False

    for _ in range(50):  # 5 seconds
        w = i2c_msg.write(GPS_ADDR, bytes([0xFD]))
        r = i2c_msg.read(GPS_ADDR, 2)
        bus.i2c_rdwr(w, r)
        avail = (bytes(r)[1] << 8) | bytes(r)[0]

        if avail > 0:
            w = i2c_msg.write(GPS_ADDR, bytes([0xFF]))
            r = i2c_msg.read(GPS_ADDR, min(avail, 255))
            bus.i2c_rdwr(w, r)
            buffer.extend(bytes(r))

            # Check for NMEA
            if b'$GN' in buffer or b'$GP' in buffer:
                nmea_found = True

            # Check for UBX
            if b'\xb5\x62' in buffer:
                ubx_found = True

        time.sleep(0.1)

    if nmea_found:
        print("✓ NMEA data: RECEIVING")
    else:
        print("✗ NMEA data: NOT FOUND")

    if ubx_found:
        print("✓ UBX data: RECEIVING")
    else:
        print("⚠ UBX data: NOT FOUND (module in NMEA-only mode)")

    # Test 3: Satellite Count
    print("\nTEST 3: Satellite Visibility (30 second test)")
    print("-" * 80)
    print("Checking for satellites... (outdoor antenna with clear sky should see 4+ sats)")
    buffer = bytearray()
    max_sats = 0
    gsa_found = False
    gsv_constellations = set()

    for i in range(300):  # 30 seconds
        w = i2c_msg.write(GPS_ADDR, bytes([0xFD]))
        r = i2c_msg.read(GPS_ADDR, 2)
        bus.i2c_rdwr(w, r)
        avail = (bytes(r)[1] << 8) | bytes(r)[0]

        if avail > 0:
            w = i2c_msg.write(GPS_ADDR, bytes([0xFF]))
            r = i2c_msg.read(GPS_ADDR, min(avail, 255))
            bus.i2c_rdwr(w, r)
            buffer.extend(bytes(r))

            while b'\n' in buffer:
                line_end = buffer.index(b'\n')
                line = buffer[:line_end+1]
                buffer = buffer[line_end+1:]

                try:
                    line_str = line.decode('ascii').strip()

                    # GGA - satellites in use
                    if '$GNGGA' in line_str or '$GPGGA' in line_str:
                        parts = line_str.split(',')
                        if len(parts) > 7 and parts[7]:
                            sats = int(parts[7]) if parts[7].isdigit() else 0
                            if sats > max_sats:
                                max_sats = sats
                                if sats > 0:
                                    print(f"  ✓ Satellites in use: {sats}")

                    # GSA - DOP and satellites
                    if '$GNGSA' in line_str or '$GPGSA' in line_str:
                        gsa_found = True

                    # GSV - satellites in view
                    if 'GSV' in line_str:
                        parts = line_str.split(',')
                        if len(parts) > 3 and parts[3]:
                            try:
                                sats_in_view = int(parts[3])
                                if sats_in_view > 0:
                                    constellation = line_str[1:3]  # GP, GL, GA, etc.
                                    gsv_constellations.add(constellation)
                                    if constellation not in [c for c, _ in gsv_constellations]:
                                        print(f"  ✓ {constellation} constellation: {sats_in_view} satellites in view")
                            except:
                                pass
                except:
                    pass

        if i % 100 == 99:
            elapsed = (i + 1) // 10
            print(f"  [{elapsed}s] Max satellites seen: {max_sats}")

        time.sleep(0.1)

    print()
    if max_sats > 0:
        print(f"✓ SATELLITES DETECTED: {max_sats} satellites in use")
        print(f"  Constellations: {', '.join(gsv_constellations) if gsv_constellations else 'None'}")
    else:
        print("✗ NO SATELLITES DETECTED (0 satellites after 30 seconds)")

    # Final Report
    print()
    print("=" * 80)
    print("DIAGNOSIS SUMMARY")
    print("=" * 80)
    print()

    if max_sats > 0:
        print("✓✓✓ GPS IS WORKING! ✓✓✓")
        print()
        print(f"Satellites: {max_sats}")
        print("Status: Antenna is receiving signals")
        print("Next step: Wait for GPS fix (can take 30-60 seconds for cold start)")
        print()
        print("Run: python3 gps_test.py")
    else:
        print("✗✗✗ GPS PROBLEM DETECTED ✗✗✗")
        print()
        print("Issue: No satellites visible despite outdoor placement")
        print()
        print("HARDWARE CHECKS NEEDED:")
        print()
        print("1. ANTENNA CONNECTION")
        print("   □ Is u.FL connector fully seated at GPS module?")
        print("   □ Is cable intact (no kinks/damage)?")
        print("   □ Is antenna fully connected at other end?")
        print()
        print("2. ANTENNA POWER (Most Likely Issue)")
        print("   Active antennas need 3.3V power on center pin of u.FL")
        print()
        print("   Antenna power sources:")
        print("   • VCC_RF from GPS module (requires software enable)")
        print("   • Bias-tee/external power supply")
        print("   • Some antennas have built-in battery/power")
        print()
        print("   To check if antenna power is the issue:")
        print("   a) Try a different antenna (passive or known-working active)")
        print("   b) Measure voltage on u.FL center pin (should be 3.3V if enabled)")
        print("   c) Check if there's a hardware jumper/switch on GPS board")
        print()
        print("3. ANTENNA TYPE")
        print("   □ Confirm antenna is CIROCOMM active ceramic patch")
        print("   □ Verify antenna orientation (ceramic side facing up/sky)")
        print("   □ Check antenna is rated for GPS L1 frequency (1575.42 MHz)")
        print()
        print("4. GPS MODULE")
        print("   □ Check if module has been replaced/reflashed")
        print("   □ Verify it's SparkFun NEO-M8U board")
        print()
        print("SOFTWARE ALREADY ATTEMPTED:")
        print("  ✓ Multiple CFG-ANT configurations sent")
        print("  ✓ Different UBX command methods tried")
        print("  ⚠ Module not acknowledging UBX commands (may be NMEA-only mode)")
        print()
        print("RECOMMENDED NEXT STEPS:")
        print()
        print("1. Physical inspection of antenna and connections")
        print("2. Try different/passive antenna to isolate issue")
        print("3. Check GPS module documentation for hardware antenna power enable")
        print("4. If available, connect via USB and use u-blox u-center software")
        print("   to verify module configuration and enable VCC_RF")
        print()
        print("Based on your previous success (GPS_FIX_SUMMARY.md), this likely")
        print("a hardware issue (connector, cable, or power) rather than software.")

    print("=" * 80)

except Exception as e:
    print(f"\nERROR: {e}")
    import traceback
    traceback.print_exc()
finally:
    bus.close()
