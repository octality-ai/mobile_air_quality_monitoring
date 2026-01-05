#!/usr/bin/env python3
"""
Enable multi-GNSS support on NEO-M8U
Enables GPS + GLONASS + Galileo + BeiDou for maximum satellite visibility
"""

import smbus2
import time
import struct

I2C_BUS = 1
UBLOX_ADDR = 0x42
REG_DATA_STREAM = 0xFF
REG_DATA_AVAILABLE_HIGH = 0xFD
REG_DATA_AVAILABLE_LOW = 0xFE


def calculate_checksum(msg_class, msg_id, payload):
    ck_a = 0
    ck_b = 0
    for byte in [msg_class, msg_id, len(payload) & 0xFF, (len(payload) >> 8) & 0xFF]:
        ck_a = (ck_a + byte) & 0xFF
        ck_b = (ck_b + ck_a) & 0xFF
    for byte in payload:
        ck_a = (ck_a + byte) & 0xFF
        ck_b = (ck_b + ck_a) & 0xFF
    return ck_a, ck_b


def create_ubx_message(msg_class, msg_id, payload):
    ck_a, ck_b = calculate_checksum(msg_class, msg_id, payload)
    msg = bytearray([0xB5, 0x62, msg_class, msg_id, len(payload) & 0xFF, (len(payload) >> 8) & 0xFF])
    msg.extend(payload)
    msg.extend([ck_a, ck_b])
    return bytes(msg)


def send_ubx(bus, msg):
    max_chunk = 32
    try:
        for offset in range(0, len(msg), max_chunk):
            chunk = msg[offset:offset + max_chunk]
            bus.write_i2c_block_data(UBLOX_ADDR, REG_DATA_STREAM, list(chunk))
            time.sleep(0.01)
        return True
    except Exception as e:
        print(f"Send error: {e}")
        return False


def read_response(bus, timeout=2.0):
    start = time.time()
    buffer = bytearray()
    while time.time() - start < timeout:
        try:
            high = bus.read_byte_data(UBLOX_ADDR, REG_DATA_AVAILABLE_HIGH)
            low = bus.read_byte_data(UBLOX_ADDR, REG_DATA_AVAILABLE_LOW)
            avail = (high << 8) | low
            if avail > 0 and avail != 0xFFFF:
                avail = min(avail, 255)
                for offset in range(0, avail, 32):
                    chunk_size = min(32, avail - offset)
                    chunk = bus.read_i2c_block_data(UBLOX_ADDR, REG_DATA_STREAM, chunk_size)
                    buffer.extend(chunk)
                for i in range(len(buffer) - 3):
                    if buffer[i:i+4] == b'\xB5\x62\x05\x01':
                        return 'ACK'
                    if buffer[i:i+4] == b'\xB5\x62\x05\x00':
                        return 'NAK'
            time.sleep(0.05)
        except:
            time.sleep(0.05)
    return None


def enable_gnss(bus, gnss_id, enable, name):
    """
    Configure GNSS system via UBX-CFG-GNSS
    gnssId: 0=GPS, 1=SBAS, 2=Galileo, 3=BeiDou, 5=QZSS, 6=GLONASS
    """
    print(f"\n{'Enabling' if enable else 'Disabling'} {name} (GNSS ID {gnss_id})...")

    # UBX-CFG-GNSS payload for M8 series
    # msgVer (1) + numTrkChHw (1) + numTrkChUse (1) + numConfigBlocks (1) + repeated blocks

    # For setting one GNSS at a time, we use a single config block
    # Each block: gnssId(1) + resTrkCh(1) + maxTrkCh(1) + reserved1(1) + flags(4)

    num_channels = 16  # Typical for M8U
    max_channels = 16 if enable else 0

    # Flags: bit 0 = enable, bits 16-23 = sigCfgMask (0x01 for default signal)
    flags = 0x01000001 if enable else 0x01000000

    payload = bytearray([
        0x00,  # msgVer
        0xFF,  # numTrkChHw (read-only, will be ignored)
        0xFF,  # numTrkChUse (read-only, will be ignored)
        0x01,  # numConfigBlocks
        # Config block:
        gnss_id,
        0x00,  # resTrkCh (reserved tracking channels)
        max_channels,  # maxTrkCh
        0x00,  # reserved1
    ])
    payload.extend(struct.pack('<I', flags))

    msg = create_ubx_message(0x06, 0x3E, bytes(payload))

    if not send_ubx(bus, msg):
        print(f"  ✗ Failed to send")
        return False

    result = read_response(bus)
    if result == 'ACK':
        print(f"  ✓ {name} {'enabled' if enable else 'disabled'}")
        return True
    elif result == 'NAK':
        print(f"  ✗ Configuration rejected")
        return False
    else:
        print(f"  ⚠ No response")
        return False


def enable_nav_sat_messages(bus):
    """Enable NAV-SAT messages for satellite visibility"""
    print(f"\nEnabling satellite information messages...")

    # UBX-CFG-MSG to enable NAV-SAT on I2C port
    # Payload: msgClass(1) + msgID(1) + rate[6](1 each for DDC/UART1/UART2/USB/SPI/reserved)
    payload = bytes([
        0x01,  # NAV class
        0x35,  # SAT message
        0x01,  # Rate on DDC (I2C) - output every solution
        0x00,  # UART1
        0x00,  # UART2
        0x00,  # USB
        0x00,  # SPI
        0x00   # reserved
    ])

    msg = create_ubx_message(0x06, 0x01, payload)

    if send_ubx(bus, msg):
        if read_response(bus) == 'ACK':
            print(f"  ✓ NAV-SAT messages enabled")
            return True

    print(f"  ✗ Failed to enable NAV-SAT messages")
    return False


def save_config(bus):
    """Save configuration to non-volatile memory"""
    print(f"\nSaving configuration...")

    # CFG-CFG: save all settings
    # clearMask(4) + saveMask(4) + loadMask(4) + deviceMask(1)
    payload = struct.pack('<IIIB',
        0x00000000,  # clearMask (don't clear)
        0xFFFFFFFF,  # saveMask (save all)
        0x00000000,  # loadMask (don't load)
        0x17         # deviceMask (BBR + Flash + EEPROM)
    )

    msg = create_ubx_message(0x06, 0x09, payload)

    if send_ubx(bus, msg):
        if read_response(bus, timeout=3.0) == 'ACK':
            print(f"  ✓ Configuration saved to non-volatile memory")
            return True

    print(f"  ⚠ Save may have failed")
    return False


def main():
    print("=" * 70)
    print("Multi-GNSS Configuration for NEO-M8U")
    print("=" * 70)
    print("\nThis will enable multiple GNSS constellations for:")
    print("  • More visible satellites (typically 20-30+ instead of 8-12)")
    print("  • Faster time to first fix")
    print("  • Better position accuracy")
    print("  • More reliable fix in challenging environments")
    print("\n" + "=" * 70)

    bus = smbus2.SMBus(I2C_BUS)

    try:
        # Enable GNSS systems
        # GPS is typically enabled by default, but we'll ensure it
        enable_gnss(bus, 0, True, "GPS (USA)")
        time.sleep(0.5)

        enable_gnss(bus, 6, True, "GLONASS (Russia)")
        time.sleep(0.5)

        enable_gnss(bus, 2, True, "Galileo (Europe)")
        time.sleep(0.5)

        enable_gnss(bus, 3, True, "BeiDou (China)")
        time.sleep(0.5)

        # Enable satellite info messages
        enable_nav_sat_messages(bus)
        time.sleep(0.5)

        # Save to flash
        save_config(bus)

        print("\n" + "=" * 70)
        print("✓ Multi-GNSS configuration complete!")
        print("\nRecommended next steps:")
        print("  1. Wait 10 seconds for module to reinitialize")
        print("  2. Run: python3 gps_diagnostic.py")
        print("  3. You should see satellites from multiple constellations")
        print("=" * 70 + "\n")

    finally:
        bus.close()


if __name__ == "__main__":
    main()
