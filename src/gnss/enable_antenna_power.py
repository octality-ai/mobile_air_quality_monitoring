#!/usr/bin/env python3
"""
Enable Active Antenna Power - Based on Previously Working Configuration
This replicates the successful ublox_enable_lna_power.py configuration
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
        return (data[1] << 8) | data[0]
    except:
        return 0

def drain_buffer(bus, max_drain=2000):
    """Drain GPS buffer"""
    total = 0
    while max_drain > 0:
        avail = read_available(bus)
        if avail == 0:
            break
        chunk = min(avail, 255, max_drain)
        try:
            w = i2c_msg.write(GPS_ADDR, bytes([REG_DATA]))
            r = i2c_msg.read(GPS_ADDR, chunk)
            bus.i2c_rdwr(w, r)
            total += chunk
            max_drain -= chunk
        except:
            break
        time.sleep(0.01)
    return total

def ubx_checksum(msg_class, msg_id, payload):
    """Calculate UBX Fletcher checksum"""
    ck_a = ck_b = 0
    for byte in [msg_class, msg_id, len(payload) & 0xFF, (len(payload) >> 8) & 0xFF] + list(payload):
        ck_a = (ck_a + byte) & 0xFF
        ck_b = (ck_b + ck_a) & 0xFF
    return ck_a, ck_b

def send_ubx(bus, msg_class, msg_id, payload):
    """Send UBX message via I2C"""
    ck_a, ck_b = ubx_checksum(msg_class, msg_id, payload)
    msg = bytes([0xB5, 0x62, msg_class, msg_id,
                 len(payload) & 0xFF, (len(payload) >> 8) & 0xFF]) + payload + bytes([ck_a, ck_b])

    # Send via I2C in small chunks (I2C has write limits)
    chunk_size = 16
    for i in range(0, len(msg), chunk_size):
        chunk = msg[i:i+chunk_size]
        try:
            # Write to stream register
            bus.write_i2c_block_data(GPS_ADDR, REG_DATA, list(chunk))
            time.sleep(0.02)
        except Exception as e:
            print(f"  Warning: I2C write error: {e}")
            return False

    time.sleep(0.2)
    return True

def wait_for_ack(bus, timeout=2.0):
    """Wait for UBX-ACK-ACK or UBX-ACK-NAK"""
    start = time.time()
    buffer = bytearray()

    while (time.time() - start) < timeout:
        avail = read_available(bus)
        if avail > 0:
            try:
                w = i2c_msg.write(GPS_ADDR, bytes([REG_DATA]))
                r = i2c_msg.read(GPS_ADDR, min(avail, 255))
                bus.i2c_rdwr(w, r)
                buffer.extend(bytes(r))

                # Look for ACK (0xB5 0x62 0x05 0x01) or NAK (0xB5 0x62 0x05 0x00)
                if b'\xb5\x62\x05\x01' in buffer:
                    return "ACK"
                if b'\xb5\x62\x05\x00' in buffer:
                    return "NAK"
            except:
                pass

        time.sleep(0.05)

    return "TIMEOUT"

def configure_antenna_power(bus):
    """Configure CFG-ANT to enable active antenna power"""
    print("\n1. Configuring Antenna Power (CFG-ANT)")
    print("   Enabling VCC_RF output for active antenna LNA")

    # CFG-ANT (0x06 0x13) payload - Based on successful configuration from GPS_FIX_SUMMARY.md
    # This configuration successfully enabled antenna power before
    #
    # flags (2 bytes little-endian):
    #   bit 0: svcs enable (1 = enabled)
    #   bit 1: scd enable (short circuit detection)
    #   bit 2: ocd enable (open circuit detection)
    #   bit 3: pdwn on scd (power down on short circuit)
    #   bit 4: recovery (auto-recovery from short/open)
    # pins (2 bytes little-endian):
    #   pin configuration for VCC_RF control

    # Try the standard working configuration
    payload = bytes([
        0x1B, 0x00,  # flags: 0x001B (enable antenna power + protections)
        0x00, 0x00   # pins: default
    ])

    print(f"   Sending UBX-CFG-ANT: flags=0x{payload[1]:02X}{payload[0]:02X}, pins=0x{payload[3]:02X}{payload[2]:02X}")

    if not send_ubx(bus, 0x06, 0x13, payload):
        print("   ✗ Failed to send command")
        return False

    result = wait_for_ack(bus)
    print(f"   Response: {result}")

    if result == "ACK":
        print("   ✓ Antenna power configuration accepted")
        return True
    elif result == "NAK":
        print("   ⚠ Configuration rejected (trying alternative)")

        # Try alternative configuration
        payload2 = bytes([
            0x01, 0x00,  # flags: 0x0001 (only enable power, no protections)
            0x00, 0x00   # pins: default
        ])
        print(f"   Sending UBX-CFG-ANT (alt): flags=0x{payload2[1]:02X}{payload2[0]:02X}")

        if send_ubx(bus, 0x06, 0x13, payload2):
            result2 = wait_for_ack(bus)
            print(f"   Response: {result2}")
            if result2 == "ACK":
                print("   ✓ Alternative configuration accepted")
                return True

        return False
    else:
        print("   ⚠ No acknowledgment received (command may still work)")
        return None

def save_config(bus):
    """Save configuration to non-volatile memory"""
    print("\n2. Saving Configuration (CFG-CFG)")
    print("   Saving to non-volatile memory (persists after reboot)")

    # CFG-CFG (0x06 0x09) - Save current config
    payload = bytes([
        0x00, 0x00, 0x00, 0x00,  # clearMask: don't clear anything
        0xFF, 0xFF, 0x00, 0x00,  # saveMask: save all settings
        0x00, 0x00, 0x00, 0x00,  # loadMask: don't load
        0x17                      # deviceMask: save to all storage types
    ])

    if not send_ubx(bus, 0x06, 0x09, payload):
        print("   ✗ Failed to send save command")
        return False

    result = wait_for_ack(bus, timeout=3.0)  # Save can take longer
    print(f"   Response: {result}")

    if result == "ACK":
        print("   ✓ Configuration saved successfully")
        return True
    else:
        print("   ⚠ Save status unclear (configuration may be volatile)")
        return None

def test_satellites(bus, duration=20):
    """Test if satellites become visible"""
    print(f"\n3. Testing for Satellites ({duration} seconds)")
    print("   Monitoring NMEA messages for satellite visibility...")

    buffer = bytearray()
    satellites_seen = False
    fix_acquired = False

    for i in range(duration * 10):  # 10 Hz polling
        avail = read_available(bus)
        if avail > 0:
            try:
                w = i2c_msg.write(GPS_ADDR, bytes([REG_DATA]))
                r = i2c_msg.read(GPS_ADDR, min(avail, 512))
                bus.i2c_rdwr(w, r)
                buffer.extend(bytes(r))

                while b'\n' in buffer:
                    line_end = buffer.index(b'\n')
                    line = buffer[:line_end+1]
                    buffer = buffer[line_end+1:]

                    try:
                        line_str = line.decode('ascii').strip()

                        # Check for satellite count in GGA
                        if '$GNGGA' in line_str or '$GPGGA' in line_str:
                            parts = line_str.split(',')
                            if len(parts) > 7:
                                num_sv = parts[7]
                                if num_sv and num_sv.isdigit() and int(num_sv) > 0:
                                    if not satellites_seen:
                                        print(f"   ✓ Satellites detected: {num_sv}")
                                        satellites_seen = True

                        # Check for fix in RMC
                        if '$GNRMC' in line_str or '$GPRMC' in line_str:
                            parts = line_str.split(',')
                            if len(parts) > 2 and parts[2] == 'A':
                                if not fix_acquired:
                                    print(f"   ✓ GPS FIX ACQUIRED!")
                                    print(f"      {line_str[:80]}")
                                    fix_acquired = True
                                    return True

                    except:
                        pass
            except:
                pass

        # Print progress every 5 seconds
        if i % 50 == 0 and i > 0:
            status = "Satellites visible" if satellites_seen else "Searching..."
            print(f"   [{i//10:02d}s] {status}")

        time.sleep(0.1)

    if satellites_seen and not fix_acquired:
        print("   ⚠ Satellites visible but no fix yet (normal for cold start)")
        print("      Continue monitoring with: python3 gps_test.py")
        return None
    elif not satellites_seen:
        print("   ✗ No satellites detected")
        return False

    return fix_acquired

def main():
    print("=" * 70)
    print("ENABLE ACTIVE ANTENNA POWER")
    print("=" * 70)
    print("Hardware: SparkFun NEO-M8U GPS with CIROCOMM Active Antenna")
    print("=" * 70)

    bus = SMBus(I2C_BUS)

    try:
        # Initialize
        print("\nInitializing GPS connection...")
        time.sleep(1)
        drained = drain_buffer(bus)
        print(f"Cleared {drained} bytes from buffer\n")

        # Configure antenna power
        ant_result = configure_antenna_power(bus)

        if ant_result == False:
            print("\n✗ FAILED: Could not configure antenna power")
            print("  The GPS module may:")
            print("  - Already have antenna power enabled")
            print("  - Use a passive antenna (doesn't need power)")
            print("  - Have antenna power controlled by hardware jumper")
            return

        # Save configuration
        save_result = save_config(bus)

        # Wait for settings to take effect
        print("\nWaiting for antenna to stabilize...")
        time.sleep(2)
        drain_buffer(bus)

        # Test for satellites
        fix_result = test_satellites(bus)

        # Summary
        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)

        if fix_result == True:
            print("✓ SUCCESS: GPS is working!")
            print("  - Antenna power enabled")
            print("  - Configuration saved")
            print("  - GPS fix acquired")
        elif fix_result == None:
            print("⚠ PARTIAL SUCCESS: Satellites visible, waiting for fix")
            print("  - Antenna power likely enabled")
            print("  - Continue monitoring: python3 gps_test.py")
        else:
            print("⚠ NO SATELLITES DETECTED")
            print("\nPossible issues:")
            print("  1. Antenna placement - needs clear sky view")
            print("  2. Antenna disconnected or faulty")
            print("  3. Module may have passive antenna (doesn't need VCC_RF)")
            print("\nNext steps:")
            print("  - Move antenna outdoors with clear sky view")
            print("  - Wait 30-60 seconds for cold start")
            print("  - Run: python3 gps_test.py")

        print("=" * 70)

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        bus.close()

if __name__ == "__main__":
    main()
