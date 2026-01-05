#!/usr/bin/env python3
"""
u-blox NEO-M8U Antenna Configuration Tool
Configures antenna supervisor settings for different active antenna types
"""

import smbus2
import time
import struct
import sys

# I2C configuration
I2C_BUS = 1
UBLOX_ADDR = 0x42

# UBX registers
REG_DATA_AVAILABLE_HIGH = 0xFD
REG_DATA_AVAILABLE_LOW = 0xFE
REG_DATA_STREAM = 0xFF

# UBX protocol constants
UBX_SYNC1 = 0xB5
UBX_SYNC2 = 0x62
UBX_CLASS_CFG = 0x06
UBX_ID_CFG_ANT = 0x13
UBX_ID_CFG_CFG = 0x09

# Antenna configurations (flags field in CFG-ANT)
# Bit 0: svcs (SV Configuration - active antenna control)
# Bit 1: scd (Short Circuit Detection)
# Bit 2: ocd (Open Circuit Detection)
# Bit 3: pdwnOnSCD (Power Down on Short Circuit)
# Bit 4: recovery (Automatic Recovery from short)

ANTENNA_PRESETS = {
    'sparkfun': {
        'name': 'SparkFun GPS/GNSS Magnetic Mount (3m SMA)',
        'description': 'Standard active antenna with proven performance',
        'flags': 0b00011111,  # All protections enabled
        'pins': 0x001F,       # Default pin configuration
    },
    'amazon': {
        'name': 'Cirocomm 32dB High Gain Active Antenna',
        'description': 'High-gain ceramic antenna, may need adjusted supervision',
        'flags': 0b00010111,  # Disable recovery, keep other protections
        'pins': 0x001F,       # Default pin configuration
    },
    'safe': {
        'name': 'Safe Mode - Maximum Protection',
        'description': 'All antenna supervisor features enabled',
        'flags': 0b00011111,  # All features on
        'pins': 0x001F,
    },
    'minimal': {
        'name': 'Minimal Supervision',
        'description': 'Only basic active antenna control (use if having detection issues)',
        'flags': 0b00000001,  # Only svcs enabled
        'pins': 0x001F,
    }
}


class UBloxConfig:
    def __init__(self, bus_num=I2C_BUS, address=UBLOX_ADDR):
        self.bus = smbus2.SMBus(bus_num)
        self.address = address
        self.max_chunk = 32

    def calculate_checksum(self, msg_class, msg_id, payload):
        """Calculate UBX checksum (Fletcher-8)"""
        ck_a = 0
        ck_b = 0

        # Add class, ID, and length
        ck_a = (ck_a + msg_class) & 0xFF
        ck_b = (ck_b + ck_a) & 0xFF

        ck_a = (ck_a + msg_id) & 0xFF
        ck_b = (ck_b + ck_a) & 0xFF

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

    def create_ubx_message(self, msg_class, msg_id, payload):
        """Create a UBX protocol message"""
        length = len(payload)
        ck_a, ck_b = self.calculate_checksum(msg_class, msg_id, payload)

        msg = bytearray()
        msg.append(UBX_SYNC1)
        msg.append(UBX_SYNC2)
        msg.append(msg_class)
        msg.append(msg_id)
        msg.append(length & 0xFF)
        msg.append((length >> 8) & 0xFF)
        msg.extend(payload)
        msg.append(ck_a)
        msg.append(ck_b)

        return bytes(msg)

    def send_ubx_message(self, msg):
        """Send UBX message via I2C"""
        try:
            # Send in chunks to avoid I2C buffer issues
            for offset in range(0, len(msg), self.max_chunk):
                chunk = msg[offset:offset + self.max_chunk]
                self.bus.write_i2c_block_data(self.address, REG_DATA_STREAM, list(chunk))
                time.sleep(0.01)  # Small delay between chunks
            return True
        except Exception as e:
            print(f"Error sending message: {e}")
            return False

    def read_response(self, timeout=2.0):
        """Read UBX response from module"""
        start_time = time.time()
        data_buffer = bytearray()

        while time.time() - start_time < timeout:
            try:
                # Check bytes available
                high_byte = self.bus.read_byte_data(self.address, REG_DATA_AVAILABLE_HIGH)
                low_byte = self.bus.read_byte_data(self.address, REG_DATA_AVAILABLE_LOW)
                bytes_available = (high_byte << 8) | low_byte

                if bytes_available > 0 and bytes_available != 0xFFFF:
                    # Read available data
                    bytes_to_read = min(bytes_available, 255)
                    for offset in range(0, bytes_to_read, self.max_chunk):
                        chunk_size = min(self.max_chunk, bytes_to_read - offset)
                        chunk = self.bus.read_i2c_block_data(self.address, REG_DATA_STREAM, chunk_size)
                        data_buffer.extend(chunk)

                    # Look for UBX ACK (0xB5 0x62 0x05 0x01) or NAK (0xB5 0x62 0x05 0x00)
                    if len(data_buffer) >= 10:
                        for i in range(len(data_buffer) - 9):
                            if data_buffer[i] == 0xB5 and data_buffer[i+1] == 0x62:
                                if data_buffer[i+2] == 0x05:  # ACK/NAK class
                                    if data_buffer[i+3] == 0x01:  # ACK
                                        return ('ACK', data_buffer[i:i+10])
                                    elif data_buffer[i+3] == 0x00:  # NAK
                                        return ('NAK', data_buffer[i:i+10])
                                elif data_buffer[i+2] == 0x06 and data_buffer[i+3] == 0x13:  # CFG-ANT response
                                    msg_len = data_buffer[i+4] + (data_buffer[i+5] << 8)
                                    total_len = 8 + msg_len  # Header + length + payload + checksum
                                    if len(data_buffer) >= i + total_len:
                                        return ('CFG-ANT', data_buffer[i:i+total_len])

                time.sleep(0.05)
            except Exception as e:
                print(f"Error reading response: {e}")
                time.sleep(0.05)

        return (None, data_buffer)

    def configure_antenna(self, flags, pins):
        """Configure antenna supervisor via UBX-CFG-ANT"""
        # CFG-ANT payload: flags (U2) + pins (U2)
        payload = struct.pack('<HH', flags, pins)

        # Create and send message
        msg = self.create_ubx_message(UBX_CLASS_CFG, UBX_ID_CFG_ANT, payload)

        print(f"Sending CFG-ANT configuration...")
        print(f"  Flags: 0x{flags:04X} (binary: {flags:016b})")
        print(f"  Pins:  0x{pins:04X}")

        if not self.send_ubx_message(msg):
            return False

        # Wait for ACK/NAK
        response_type, response_data = self.read_response(timeout=2.0)

        if response_type == 'ACK':
            print("✓ Configuration acknowledged by module")
            return True
        elif response_type == 'NAK':
            print("✗ Configuration rejected by module")
            return False
        else:
            print("⚠ No acknowledgment received (timeout)")
            return False

    def save_configuration(self):
        """Save current configuration to non-volatile memory (BBR/Flash)"""
        # CFG-CFG message to save current config
        # clearMask (4 bytes) | saveMask (4 bytes) | loadMask (4 bytes) | deviceMask (1 byte)
        # saveMask bits: 0=ioPort, 1=msgConf, 2=infMsg, 3=navConf, 4=rxmConf, 8=rinvConf, 9=antConf

        # Save antenna configuration (bit 9 = antConf = 0x200)
        save_mask = 0x00000200  # Save only antenna config
        clear_mask = 0x00000000  # Don't clear anything
        load_mask = 0x00000000   # Don't load
        device_mask = 0x17       # BBR + Flash + EEPROM

        payload = struct.pack('<IIIB', clear_mask, save_mask, load_mask, device_mask)
        msg = self.create_ubx_message(UBX_CLASS_CFG, UBX_ID_CFG_CFG, payload)

        print("\nSaving configuration to non-volatile memory...")
        if not self.send_ubx_message(msg):
            return False

        response_type, response_data = self.read_response(timeout=2.0)

        if response_type == 'ACK':
            print("✓ Configuration saved successfully")
            print("  Settings will persist across power cycles")
            return True
        elif response_type == 'NAK':
            print("✗ Failed to save configuration")
            return False
        else:
            print("⚠ Save status unknown (no response)")
            return False

    def read_antenna_config(self):
        """Poll current antenna configuration"""
        # Send CFG-ANT poll (empty payload)
        msg = self.create_ubx_message(UBX_CLASS_CFG, UBX_ID_CFG_ANT, b'')

        print("Reading current antenna configuration...")
        if not self.send_ubx_message(msg):
            return None

        response_type, response_data = self.read_response(timeout=2.0)

        if response_type == 'CFG-ANT':
            # Parse response: header (6 bytes) + flags (2) + pins (2) + checksum (2)
            if len(response_data) >= 12:
                flags = response_data[6] + (response_data[7] << 8)
                pins = response_data[8] + (response_data[9] << 8)
                print(f"✓ Current configuration:")
                print(f"  Flags: 0x{flags:04X} (binary: {flags:016b})")
                print(f"  Pins:  0x{pins:04X}")
                self.decode_flags(flags)
                return (flags, pins)

        print("✗ Failed to read configuration")
        return None

    def decode_flags(self, flags):
        """Decode antenna supervisor flags"""
        print("\n  Active features:")
        print(f"    {'✓' if flags & 0x01 else '✗'} Active Antenna Control (svcs)")
        print(f"    {'✓' if flags & 0x02 else '✗'} Short Circuit Detection (scd)")
        print(f"    {'✓' if flags & 0x04 else '✗'} Open Circuit Detection (ocd)")
        print(f"    {'✓' if flags & 0x08 else '✗'} Power Down on Short (pdwnOnSCD)")
        print(f"    {'✓' if flags & 0x10 else '✗'} Automatic Recovery (recovery)")

    def close(self):
        """Close I2C bus"""
        self.bus.close()


def print_header():
    print("\n" + "=" * 70)
    print("u-blox NEO-M8U Antenna Configuration Tool")
    print("=" * 70)


def print_presets():
    print("\nAvailable antenna presets:\n")
    for i, (key, preset) in enumerate(ANTENNA_PRESETS.items(), 1):
        print(f"{i}. {key.upper()}")
        print(f"   {preset['name']}")
        print(f"   {preset['description']}")
        config = UBloxConfig()
        config.decode_flags(preset['flags'])
        print()


def main():
    print_header()

    if len(sys.argv) > 1:
        # Command line argument provided
        preset_key = sys.argv[1].lower()
        if preset_key not in ANTENNA_PRESETS:
            print(f"\n✗ Unknown preset: {preset_key}")
            print(f"Available presets: {', '.join(ANTENNA_PRESETS.keys())}")
            sys.exit(1)
    else:
        # Interactive mode
        print("\nThis tool configures the antenna supervisor on your NEO-M8U module.")
        print("Different antennas may require different supervision settings.")

        print_presets()

        print("Options:")
        print("  r - Read current configuration")
        print("  q - Quit without changes")
        print("")

        choice = input("Enter preset number or option [r/q]: ").strip().lower()

        if choice == 'q':
            print("Exiting without changes.")
            sys.exit(0)
        elif choice == 'r':
            # Read mode
            config = UBloxConfig()
            try:
                config.read_antenna_config()
            finally:
                config.close()
            sys.exit(0)
        else:
            try:
                choice_num = int(choice)
                if choice_num < 1 or choice_num > len(ANTENNA_PRESETS):
                    print("Invalid choice")
                    sys.exit(1)
                preset_key = list(ANTENNA_PRESETS.keys())[choice_num - 1]
            except ValueError:
                print("Invalid input")
                sys.exit(1)

    # Configure the selected preset
    preset = ANTENNA_PRESETS[preset_key]

    print(f"\n{'=' * 70}")
    print(f"Selected: {preset['name']}")
    print(f"{'=' * 70}")
    print(f"\n{preset['description']}\n")

    config = UBloxConfig()
    config.decode_flags(preset['flags'])

    print()
    confirm = input("Apply this configuration? [y/N]: ").strip().lower()

    if confirm != 'y':
        print("Configuration cancelled.")
        config.close()
        sys.exit(0)

    try:
        # Apply configuration
        success = config.configure_antenna(preset['flags'], preset['pins'])

        if success:
            print("\n" + "=" * 70)
            save = input("Save to non-volatile memory? [y/N]: ").strip().lower()

            if save == 'y':
                config.save_configuration()
                print("\n✓ Antenna configuration complete and saved!")
                print("  Settings will persist across reboots.")
            else:
                print("\n✓ Antenna configuration applied (RAM only)")
                print("  Settings will reset on power cycle.")
        else:
            print("\n✗ Configuration failed")
            sys.exit(1)

    finally:
        config.close()

    print("\n" + "=" * 70)
    print("IMPORTANT: Test your GPS fix time with the new settings:")
    print("  python3 read_gps_coordinates.py")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
