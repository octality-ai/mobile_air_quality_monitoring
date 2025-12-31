#!/usr/bin/env python3
"""
Force Antenna Power - Direct UBX Command Injection
Tries different methods to force send CFG-ANT command
"""
import time
from smbus2 import SMBus

I2C_BUS = 1
GPS_ADDR = 0x42
REG_DATA = 0xFF

def send_ubx_direct(bus, payload_bytes):
    """Send raw UBX bytes directly to I2C"""
    try:
        # Method 1: Write entire message at once
        print(f"  Method 1: Single write ({len(payload_bytes)} bytes)")
        bus.write_i2c_block_data(GPS_ADDR, REG_DATA, list(payload_bytes))
        time.sleep(0.5)
        return True
    except Exception as e:
        print(f"    Failed: {e}")
        return False

def send_ubx_chunked(bus, payload_bytes, chunk_size=16):
    """Send UBX in small chunks"""
    try:
        print(f"  Method 2: Chunked write ({chunk_size} bytes/chunk)")
        for i in range(0, len(payload_bytes), chunk_size):
            chunk = payload_bytes[i:i+chunk_size]
            bus.write_i2c_block_data(GPS_ADDR, REG_DATA, list(chunk))
            time.sleep(0.02)
        time.sleep(0.5)
        return True
    except Exception as e:
        print(f"    Failed: {e}")
        return False

def send_ubx_byte_by_byte(bus, payload_bytes):
    """Send one byte at a time"""
    try:
        print(f"  Method 3: Byte-by-byte write")
        for byte in payload_bytes:
            bus.write_byte_data(GPS_ADDR, REG_DATA, byte)
            time.sleep(0.005)
        time.sleep(0.5)
        return True
    except Exception as e:
        print(f"    Failed: {e}")
        return False

def main():
    print("=" * 70)
    print("FORCE ANTENNA POWER - Direct UBX Injection")
    print("=" * 70)

    # Pre-calculated CFG-ANT UBX message
    # Header: 0xB5 0x62
    # Class: 0x06 (CFG)
    # ID: 0x13 (ANT)
    # Length: 0x04 0x00 (4 bytes payload)
    # Payload: 0x1B 0x00 0x00 0x00 (flags=0x001B, pins=0x0000)
    # Checksum: calculated for above

    cfgant_msg = bytes([
        0xB5, 0x62,        # Sync chars
        0x06, 0x13,        # CFG-ANT
        0x04, 0x00,        # Length = 4
        0x1B, 0x00,        # flags = 0x001B (enable power + protections)
        0x00, 0x00,        # pins = 0x0000 (default)
        0x42, 0x42         # Checksum (will calculate properly)
    ])

    # Calculate proper checksum
    ck_a = ck_b = 0
    for byte in cfgant_msg[2:8]:  # Class through end of payload
        ck_a = (ck_a + byte) & 0xFF
        ck_b = (ck_b + ck_a) & 0xFF

    cfgant_msg = cfgant_msg[:8] + bytes([ck_a, ck_b])

    print(f"\nUBX-CFG-ANT message: {cfgant_msg.hex()}")
    print(f"Message length: {len(cfgant_msg)} bytes")
    print()

    bus = SMBus(I2C_BUS)

    try:
        # Try different sending methods
        print("Attempting to send CFG-ANT command:\n")

        success = send_ubx_direct(bus, cfgant_msg)
        if not success:
            success = send_ubx_chunked(bus, cfgant_msg)
        if not success:
            success = send_ubx_byte_by_byte(bus, cfgant_msg)

        if success:
            print("\n✓ Command sent successfully (may or may not be acknowledged)")
        else:
            print("\n✗ All send methods failed")

        # Also try minimal power-only configuration
        print("\n" + "-" * 70)
        print("Trying minimal configuration (power only):\n")

        minimal_msg = bytes([
            0xB5, 0x62,
            0x06, 0x13,
            0x04, 0x00,
            0x01, 0x00,  # flags = 0x0001 (only power bit)
            0x00, 0x00,
            0x00, 0x00   # checksum placeholder
        ])

        # Calculate checksum
        ck_a = ck_b = 0
        for byte in minimal_msg[2:8]:
            ck_a = (ck_a + byte) & 0xFF
            ck_b = (ck_b + ck_a) & 0xFF

        minimal_msg = minimal_msg[:8] + bytes([ck_a, ck_b])
        print(f"UBX-CFG-ANT (minimal): {minimal_msg.hex()}")

        send_ubx_chunked(bus, minimal_msg, chunk_size=10)

        print("\n" + "=" * 70)
        print("Commands sent. Testing for satellites...")
        print("=" * 70)

        # Wait and check for satellites
        time.sleep(3)

        # Quick satellite check
        from smbus2 import i2c_msg
        buffer = bytearray()

        for i in range(100):  # 10 seconds
            try:
                w = i2c_msg.write(GPS_ADDR, bytes([0xFD]))
                r = i2c_msg.read(GPS_ADDR, 2)
                bus.i2c_rdwr(w, r)
                avail = (bytes(r)[1] << 8) | bytes(r)[0]

                if avail > 0:
                    w = i2c_msg.write(GPS_ADDR, bytes([REG_DATA]))
                    r = i2c_msg.read(GPS_ADDR, min(avail, 255))
                    bus.i2c_rdwr(w, r)
                    buffer.extend(bytes(r))

                    while b'\n' in buffer:
                        line_end = buffer.index(b'\n')
                        line = buffer[:line_end+1]
                        buffer = buffer[line_end+1:]

                        try:
                            line_str = line.decode('ascii').strip()
                            if '$GNGGA' in line_str or '$GPGGA' in line_str:
                                parts = line_str.split(',')
                                if len(parts) > 7:
                                    num_sv = parts[7]
                                    if num_sv and num_sv.isdigit() and int(num_sv) > 0:
                                        print(f"\n✓✓✓ SATELLITES DETECTED: {num_sv} ✓✓✓")
                                        print(f"    Antenna power is likely working!")
                                        return
                                    elif i % 20 == 0:
                                        print(f"  [{i//10}s] Satellites: {num_sv}")
                        except:
                            pass
            except:
                pass

            time.sleep(0.1)

        print("\n⚠ No satellites detected after 10 seconds")
        print("\nPossible reasons:")
        print("  1. Commands didn't enable antenna power (module not responding to UBX)")
        print("  2. Antenna power already enabled but antenna has hardware issue")
        print("  3. Need more time (cold start can take 30-60 seconds)")
        print("\nNext step: Check physical antenna connection and wait longer")

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        bus.close()

if __name__ == "__main__":
    main()
