#!/usr/bin/env python3
"""
GPS Configuration - Enable Active Antenna Power
Configures u-blox NEO-M8U to provide power for active antennas

Usage: python3 gps_config.py

This only needs to be run once - configuration is saved to GPS non-volatile memory.
Run this if:
  - You're using an active antenna (with built-in LNA)
  - GPS can see satellites but not getting a fix
  - After GPS firmware updates
"""
import time
from smbus2 import SMBus, i2c_msg

# Configuration
I2C_BUS = 1
GPS_ADDR = 0x42
REG_AVAIL_HIGH = 0xFD
REG_DATA = 0xFF


def read_available(bus):
    """Check bytes available in GPS buffer"""
    try:
        w = i2c_msg.write(GPS_ADDR, bytes([REG_AVAIL_HIGH]))
        r = i2c_msg.read(GPS_ADDR, 2)
        bus.i2c_rdwr(w, r)
        data = bytes(r)
        return data[0] | (data[1] << 8)
    except:
        return 0


def drain_buffer(bus):
    """Drain any pending data from GPS buffer"""
    try:
        avail = read_available(bus)
        if avail > 0:
            chunk_size = min(avail, 255)
            w = i2c_msg.write(GPS_ADDR, bytes([REG_DATA]))
            r = i2c_msg.read(GPS_ADDR, chunk_size)
            bus.i2c_rdwr(w, r)
            return avail
    except:
        pass
    return 0


def calculate_checksum(msg_class, msg_id, payload):
    """Calculate UBX checksum"""
    ck_a = 0
    ck_b = 0

    # Add class and ID
    ck_a = (ck_a + msg_class) & 0xFF
    ck_b = (ck_b + ck_a) & 0xFF
    ck_a = (ck_a + msg_id) & 0xFF
    ck_b = (ck_b + ck_a) & 0xFF

    # Add length (little-endian)
    length = len(payload)
    ck_a = (ck_a + (length & 0xFF)) & 0xFF
    ck_b = (ck_b + ck_a) & 0xFF
    ck_a = (ck_a + ((length >> 8) & 0xFF)) & 0xFF
    ck_b = (ck_b + ck_a) & 0xFF

    # Add payload
    for byte in payload:
        ck_a = (ck_a + byte) & 0xFF
        ck_b = (ck_b + ck_a) & 0xFF

    return ck_a, ck_b


def send_ubx_command(bus, msg_class, msg_id, payload, description=""):
    """Send UBX command with proper checksum"""
    try:
        # Build UBX message
        length = len(payload)
        ck_a, ck_b = calculate_checksum(msg_class, msg_id, payload)

        msg = bytes([
            0xB5, 0x62,           # UBX sync chars
            msg_class, msg_id,    # Message class and ID
            length & 0xFF,        # Length low byte
            (length >> 8) & 0xFF, # Length high byte
        ]) + payload + bytes([ck_a, ck_b])

        # Send in chunks
        chunk_size = 32
        for i in range(0, len(msg), chunk_size):
            chunk = msg[i:i+chunk_size]
            data = bytes([REG_DATA]) + chunk
            bus.write_i2c_block_data(GPS_ADDR, data[0], list(data[1:]))
            time.sleep(0.05)

        time.sleep(0.5)

        # Check for ACK/NAK
        avail = read_available(bus)
        if avail > 0:
            w = i2c_msg.write(GPS_ADDR, bytes([REG_DATA]))
            r = i2c_msg.read(GPS_ADDR, min(avail, 100))
            bus.i2c_rdwr(w, r)
            response = bytes(r)

            # Look for UBX-ACK-ACK (0x05 0x01)
            if b'\xb5\x62\x05\x01' in response:
                print(f"  ✓ {description} - ACK received")
                return True
            elif b'\xb5\x62\x05\x00' in response:
                print(f"  ✗ {description} - NAK received")
                return False

        # No ACK/NAK found, but command may still work
        drain_buffer(bus)
        print(f"  • {description} - Sent (no ACK)")
        return True

    except Exception as e:
        print(f"  ✗ {description} - ERROR: {e}")
        return False


def configure_antenna_power(bus):
    """Enable active antenna LNA power"""
    print("\n1. Configuring antenna supervisor (CFG-ANT)...")
    print("   - Enabling antenna power supply")
    print("   - Enabling short/open circuit detection")

    # CFG-ANT payload:
    # flags (2 bytes): 0x0011 = enable basic protections + power
    # pins (2 bytes):  0x0000 = default pin configuration
    payload_ant = bytes([
        0x11, 0x00,  # flags
        0x00, 0x00   # pins
    ])

    success1 = send_ubx_command(bus, 0x06, 0x13, payload_ant, "Enable antenna power")

    # Try alternative configuration if first attempt failed
    if not success1:
        print("\n   Trying alternative configuration...")
        payload_ant2 = bytes([
            0x93, 0x0B,  # flags (more permissive)
            0x91, 0xF0   # pins
        ])
        send_ubx_command(bus, 0x06, 0x13, payload_ant2, "Enable antenna power (alt)")

    time.sleep(0.5)


def configure_nmea_messages(bus):
    """Enable NMEA messages on I2C (optional - already enabled by default)"""
    print("\n2. Verifying NMEA message output (CFG-MSG)...")

    # Enable NMEA GGA on I2C
    payload_gga = bytes([
        0xF0, 0x00,  # NMEA GGA
        0x01,        # DDC (I2C) rate = 1
        0x00, 0x00, 0x00,  # UART1, UART2, USB = 0
        0x00, 0x00   # SPI, reserved = 0
    ])
    send_ubx_command(bus, 0x06, 0x01, payload_gga, "Enable NMEA GGA")

    # Enable NMEA RMC on I2C
    payload_rmc = bytes([
        0xF0, 0x04,  # NMEA RMC
        0x01,        # DDC (I2C) rate = 1
        0x00, 0x00, 0x00,
        0x00, 0x00
    ])
    send_ubx_command(bus, 0x06, 0x01, payload_rmc, "Enable NMEA RMC")

    # Enable NMEA GSA on I2C (for DOP values)
    payload_gsa = bytes([
        0xF0, 0x02,  # NMEA GSA
        0x01,        # DDC (I2C) rate = 1
        0x00, 0x00, 0x00,
        0x00, 0x00
    ])
    send_ubx_command(bus, 0x06, 0x01, payload_gsa, "Enable NMEA GSA")


def save_configuration(bus):
    """Save configuration to GPS non-volatile memory"""
    print("\n3. Saving configuration to non-volatile memory (CFG-CFG)...")

    # CFG-CFG payload: Save current config to all storage
    # clearMask (4 bytes): 0x00000000 (don't clear anything)
    # saveMask (4 bytes):  0x0000FFFF (save all settings)
    # loadMask (4 bytes):  0x00000000 (don't load)
    # deviceMask (1 byte): 0x17 (all storage types)
    payload_cfg = bytes([
        0x00, 0x00, 0x00, 0x00,  # clearMask
        0xFF, 0xFF, 0x00, 0x00,  # saveMask (save all)
        0x00, 0x00, 0x00, 0x00,  # loadMask
        0x17                      # deviceMask (all storage)
    ])

    send_ubx_command(bus, 0x06, 0x09, payload_cfg, "Save configuration")
    time.sleep(1)


def test_gps_fix(bus):
    """Quick test to see if GPS gets a fix"""
    print("\n4. Testing GPS fix (15 second test)...")
    buffer = bytearray()
    fix_found = False

    for i in range(150):  # 15 seconds
        try:
            avail = read_available(bus)
            if avail > 0:
                read_size = min(avail, 255)
                w = i2c_msg.write(GPS_ADDR, bytes([REG_DATA]))
                r = i2c_msg.read(GPS_ADDR, read_size)
                bus.i2c_rdwr(w, r)
                chunk = bytes(r)
                buffer.extend(chunk)

                while b'\n' in buffer:
                    line_end = buffer.index(b'\n')
                    line = buffer[:line_end+1]
                    buffer = buffer[line_end+1:]

                    try:
                        line_str = line.decode('ascii').strip()
                        if 'GNRMC' in line_str:
                            parts = line_str.split(',')
                            if len(parts) > 2:
                                status = parts[2]
                                if status == 'A':
                                    print(f"\n  ✓ GPS FIX ACQUIRED!")
                                    print(f"    {line_str[:80]}")
                                    fix_found = True
                                    break
                                elif i % 30 == 0:
                                    print(f"    [{i//10}s] Status: {status} (waiting for 'A'...)")
                    except:
                        pass

                if fix_found:
                    break

        except:
            pass

        time.sleep(0.1)

    if not fix_found:
        print("\n  ⚠ No GPS fix yet")
        print("    This is normal for:")
        print("    - Cold start (can take 30-60 seconds)")
        print("    - Indoor/window placement (poor satellite visibility)")
        print("    - Active antenna needs time to stabilize")
        print("\n    Continue monitoring with: python3 gps_test.py")


def main():
    print("=" * 70)
    print("GPS CONFIGURATION - Active Antenna Setup")
    print("=" * 70)
    print(f"I2C Bus: {I2C_BUS}")
    print(f"I2C Address: 0x{GPS_ADDR:02X}")
    print("=" * 70)
    print()
    print("This will:")
    print("  • Enable power to active antenna (VCC_RF)")
    print("  • Configure antenna supervisor (short/open detection)")
    print("  • Enable NMEA output messages")
    print("  • Save configuration permanently")
    print()

    bus = SMBus(I2C_BUS)

    try:
        # Wait for GPS to be ready
        print("Initializing GPS connection...")
        time.sleep(2)
        drained = drain_buffer(bus)
        if drained > 0:
            print(f"  Cleared {drained} bytes from buffer")

        # Configure antenna power
        configure_antenna_power(bus)

        # Configure NMEA messages
        configure_nmea_messages(bus)

        # Save configuration
        save_configuration(bus)

        # Test GPS fix
        test_gps_fix(bus)

        print()
        print("=" * 70)
        print("CONFIGURATION COMPLETE!")
        print("=" * 70)
        print()
        print("Next steps:")
        print("  1. Move antenna to location with clear sky view")
        print("  2. Wait 30-60 seconds for cold start")
        print("  3. Run: python3 gps_test.py")
        print("  4. Look for 'GPS:A' status (A = Active fix)")
        print()
        print("If still no fix after 2 minutes:")
        print("  - Move antenna outdoors")
        print("  - Check antenna connector is fully seated")
        print("  - Verify antenna is correct type (passive or active)")
        print("=" * 70)

    except Exception as e:
        print()
        print("=" * 70)
        print(f"ERROR: {e}")
        print("=" * 70)
        print()
        print("Troubleshooting:")
        print("  1. Check I2C connection: i2cdetect -y 1")
        print("     (GPS should appear at address 0x42)")
        print("  2. Check user permissions: groups")
        print("     (should include 'i2c' group)")
        print("  3. Check GPS power supply")
        print("=" * 70)
    finally:
        bus.close()


if __name__ == "__main__":
    main()
