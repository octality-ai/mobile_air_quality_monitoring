#!/usr/bin/env python3
"""
GPS Antenna Power Configuration - Force Enable Active Antenna
This script tries multiple methods to enable antenna power on u-blox modules
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

def send_ubx_command(bus, msg_class, msg_id, payload, description="", wait_ack=True):
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

        print(f"  Sending: {description}")
        print(f"    Message: {msg.hex()}")

        # Send in chunks
        chunk_size = 32
        for i in range(0, len(msg), chunk_size):
            chunk = msg[i:i+chunk_size]
            data = bytes([REG_DATA]) + chunk
            bus.write_i2c_block_data(GPS_ADDR, data[0], list(data[1:]))
            time.sleep(0.05)

        time.sleep(0.3)

        if not wait_ack:
            print(f"    Status: Sent (no ACK expected)")
            return True

        # Check for ACK/NAK
        avail = read_available(bus)
        if avail > 0:
            w = i2c_msg.write(GPS_ADDR, bytes([REG_DATA]))
            r = i2c_msg.read(GPS_ADDR, min(avail, 200))
            bus.i2c_rdwr(w, r)
            response = bytes(r)

            print(f"    Response ({len(response)} bytes): {response[:50].hex()}")

            # Look for UBX-ACK-ACK (0x05 0x01) or UBX-ACK-NAK (0x05 0x00)
            if b'\xb5\x62\x05\x01' in response:
                print(f"    Status: ✓ ACK - Command accepted")
                return True
            elif b'\xb5\x62\x05\x00' in response:
                print(f"    Status: ✗ NAK - Command rejected")
                return False

        print(f"    Status: • No ACK/NAK received")
        return None

    except Exception as e:
        print(f"    Status: ✗ ERROR: {e}")
        return False

def poll_antenna_status(bus):
    """Poll UBX-MON-HW to check antenna status"""
    print("\n" + "=" * 70)
    print("1. Checking current antenna status (UBX-MON-HW)")
    print("=" * 70)

    # UBX-MON-HW poll (empty payload)
    send_ubx_command(bus, 0x0A, 0x09, bytes([]), "Poll hardware status", wait_ack=False)

    time.sleep(0.5)
    avail = read_available(bus)
    if avail > 0:
        w = i2c_msg.write(GPS_ADDR, bytes([REG_DATA]))
        r = i2c_msg.read(GPS_ADDR, min(avail, 255))
        bus.i2c_rdwr(w, r)
        response = bytes(r)

        # Look for MON-HW response (0xB5 0x62 0x0A 0x09)
        if b'\xb5\x62\x0a\x09' in response:
            idx = response.index(b'\xb5\x62\x0a\x09')
            hw_data = response[idx:]
            if len(hw_data) >= 68:
                # Byte 20-21 contains antenna status
                flags = hw_data[20] | (hw_data[21] << 8)
                ant_status = (flags >> 8) & 0x03
                ant_power = (flags >> 10) & 0x03

                status_map = {0: "INIT", 1: "DONTKNOW", 2: "OK", 3: "SHORT"}
                power_map = {0: "OFF", 1: "ON", 2: "DONTKNOW"}

                print(f"\n  Antenna Status: {status_map.get(ant_status, 'UNKNOWN')} ({ant_status})")
                print(f"  Antenna Power:  {power_map.get(ant_power, 'UNKNOWN')} ({ant_power})")
                return ant_status, ant_power

    print("  ⚠ Could not read antenna status")
    return None, None

def configure_antenna_method1(bus):
    """Method 1: Standard CFG-ANT with power enable"""
    print("\n" + "=" * 70)
    print("2. Method 1: Standard CFG-ANT (flags=0xF93B, pins=0xF91D)")
    print("=" * 70)

    # Standard configuration with all features enabled
    payload = bytes([
        0x3B, 0xF9,  # flags: 0xF93B (all protections + power enabled)
        0x1D, 0xF9   # pins: 0xF91D (standard pin config)
    ])

    result = send_ubx_command(bus, 0x06, 0x13, payload, "CFG-ANT standard")
    time.sleep(0.5)
    return result

def configure_antenna_method2(bus):
    """Method 2: Minimal CFG-ANT - just enable power"""
    print("\n" + "=" * 70)
    print("3. Method 2: Minimal CFG-ANT (flags=0x0001, pins=0x0000)")
    print("=" * 70)

    # Minimal: just enable antenna power, no protections
    payload = bytes([
        0x01, 0x00,  # flags: 0x0001 (only power enable)
        0x00, 0x00   # pins: default
    ])

    result = send_ubx_command(bus, 0x06, 0x13, payload, "CFG-ANT minimal")
    time.sleep(0.5)
    return result

def configure_antenna_method3(bus):
    """Method 3: Maximum CFG-ANT - all bits set"""
    print("\n" + "=" * 70)
    print("4. Method 3: Maximum CFG-ANT (flags=0xFFFF, pins=0xFFFF)")
    print("=" * 70)

    # Maximum: everything enabled
    payload = bytes([
        0xFF, 0xFF,  # flags: all bits set
        0xFF, 0xFF   # pins: all bits set
    ])

    result = send_ubx_command(bus, 0x06, 0x13, payload, "CFG-ANT maximum")
    time.sleep(0.5)
    return result

def configure_antenna_method4(bus):
    """Method 4: Poll current config, modify, and send back"""
    print("\n" + "=" * 70)
    print("5. Method 4: Read current CFG-ANT and modify")
    print("=" * 70)

    # First poll current configuration
    print("  Polling current CFG-ANT configuration...")
    send_ubx_command(bus, 0x06, 0x13, bytes([]), "Poll CFG-ANT", wait_ack=False)

    time.sleep(0.5)
    avail = read_available(bus)
    if avail > 0:
        w = i2c_msg.write(GPS_ADDR, bytes([REG_DATA]))
        r = i2c_msg.read(GPS_ADDR, min(avail, 255))
        bus.i2c_rdwr(w, r)
        response = bytes(r)

        # Look for CFG-ANT response (0xB5 0x62 0x06 0x13)
        if b'\xb5\x62\x06\x13' in response:
            idx = response.index(b'\xb5\x62\x06\x13')
            if len(response) >= idx + 10:
                # Extract current flags and pins
                current_flags = response[idx+6] | (response[idx+7] << 8)
                current_pins = response[idx+8] | (response[idx+9] << 8)

                print(f"    Current flags: 0x{current_flags:04X}")
                print(f"    Current pins:  0x{current_pins:04X}")

                # Set bit 0 (antenna power enable)
                new_flags = current_flags | 0x0001

                payload = bytes([
                    new_flags & 0xFF,
                    (new_flags >> 8) & 0xFF,
                    current_pins & 0xFF,
                    (current_pins >> 8) & 0xFF
                ])

                print(f"    New flags:     0x{new_flags:04X} (bit 0 set)")
                result = send_ubx_command(bus, 0x06, 0x13, payload, "CFG-ANT modified")
                time.sleep(0.5)
                return result

    print("  ⚠ Could not read current configuration")
    return None

def save_configuration(bus):
    """Save configuration to GPS non-volatile memory"""
    print("\n" + "=" * 70)
    print("6. Saving configuration to non-volatile memory")
    print("=" * 70)

    payload = bytes([
        0x00, 0x00, 0x00, 0x00,  # clearMask
        0xFF, 0xFF, 0x00, 0x00,  # saveMask (save all)
        0x00, 0x00, 0x00, 0x00,  # loadMask
        0x17                      # deviceMask (all storage)
    ])

    send_ubx_command(bus, 0x06, 0x09, payload, "CFG-CFG save")
    time.sleep(1)

def main():
    print("=" * 70)
    print("GPS ACTIVE ANTENNA POWER CONFIGURATION")
    print("=" * 70)
    print("This script will try multiple methods to enable antenna power")
    print("=" * 70)

    bus = SMBus(I2C_BUS)

    try:
        # Clear buffer
        print("\nInitializing...")
        time.sleep(1)
        drained = drain_buffer(bus)
        print(f"Cleared {drained} bytes from buffer")
        time.sleep(1)

        # Check current status
        ant_status, ant_power = poll_antenna_status(bus)

        # Try different configuration methods
        methods_tried = []

        result1 = configure_antenna_method1(bus)
        methods_tried.append(("Method 1 (Standard)", result1))

        if result1 != True:
            result2 = configure_antenna_method2(bus)
            methods_tried.append(("Method 2 (Minimal)", result2))

        if result1 != True and result2 != True:
            result3 = configure_antenna_method3(bus)
            methods_tried.append(("Method 3 (Maximum)", result3))

        if all(r != True for _, r in methods_tried):
            result4 = configure_antenna_method4(bus)
            methods_tried.append(("Method 4 (Modify existing)", result4))

        # Save configuration
        save_configuration(bus)

        # Wait a bit for changes to take effect
        print("\nWaiting for antenna to stabilize...")
        time.sleep(2)

        # Check status again
        print("\n" + "=" * 70)
        print("7. Verifying antenna status after configuration")
        print("=" * 70)
        drain_buffer(bus)
        ant_status_new, ant_power_new = poll_antenna_status(bus)

        # Summary
        print("\n" + "=" * 70)
        print("CONFIGURATION SUMMARY")
        print("=" * 70)
        print("\nMethods attempted:")
        for method, result in methods_tried:
            status = "✓ ACK" if result == True else ("✗ NAK" if result == False else "• No response")
            print(f"  {method}: {status}")

        if ant_power_new == 1:
            print("\n✓ SUCCESS: Antenna power is now ON")
        elif ant_power_new == 0:
            print("\n⚠ WARNING: Antenna power still shows OFF")
            print("  This may be normal if:")
            print("  - You have a passive antenna (doesn't need power)")
            print("  - Module doesn't support antenna power control")

        print("\nNext step: Run gps_diagnose.py to check for satellites")
        print("=" * 70)

    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        bus.close()

if __name__ == "__main__":
    main()
