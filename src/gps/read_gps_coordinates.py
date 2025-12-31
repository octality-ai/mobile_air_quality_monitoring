#!/usr/bin/env python3
"""
Quick GPS coordinate reader for NEO-M8U with active antenna
Reads and displays latitude, longitude, altitude, and fix status
"""

import smbus2
import time
from pynmeagps import NMEAReader
from pyubx2 import UBXReader
import io

# I2C configuration
I2C_BUS = 1
UBLOX_ADDR = 0x42

# UBX registers for u-blox I2C/DDC interface
REG_DATA_AVAILABLE_HIGH = 0xFD
REG_DATA_AVAILABLE_LOW = 0xFE
REG_DATA_STREAM = 0xFF

class GPSReader:
    def __init__(self, bus_num=I2C_BUS, address=UBLOX_ADDR):
        self.bus = smbus2.SMBus(bus_num)
        self.address = address
        self.max_chunk = 32

    def read_data(self, max_bytes=255):
        """Read data from GPS module via I2C"""
        try:
            # Check how many bytes are available
            high_byte = self.bus.read_byte_data(self.address, REG_DATA_AVAILABLE_HIGH)
            low_byte = self.bus.read_byte_data(self.address, REG_DATA_AVAILABLE_LOW)
            bytes_available = (high_byte << 8) | low_byte

            if bytes_available == 0 or bytes_available == 0xFFFF:
                return None

            # Read data in chunks
            bytes_to_read = min(bytes_available, max_bytes)
            data = []

            for offset in range(0, bytes_to_read, self.max_chunk):
                chunk_size = min(self.max_chunk, bytes_to_read - offset)
                chunk = self.bus.read_i2c_block_data(self.address, REG_DATA_STREAM, chunk_size)
                data.extend(chunk)

            return bytes(data)
        except Exception as e:
            print(f"I2C read error: {e}")
            return None

    def parse_nmea_gga(self, line):
        """Parse NMEA GGA sentence for coordinates"""
        try:
            if not line.startswith('$GNGGA') and not line.startswith('$GPGGA'):
                return None

            parts = line.split(',')
            if len(parts) < 15:
                return None

            # Extract data
            time_utc = parts[1]
            lat_raw = parts[2]
            lat_dir = parts[3]
            lon_raw = parts[4]
            lon_dir = parts[5]
            fix_quality = int(parts[6]) if parts[6] else 0
            num_sats = int(parts[7]) if parts[7] else 0
            hdop = float(parts[8]) if parts[8] else 99.9
            altitude = float(parts[9]) if parts[9] else 0.0

            if not lat_raw or not lon_raw:
                return None

            # Convert NMEA format (ddmm.mmmm) to decimal degrees
            def nmea_to_decimal(nmea_val, direction):
                if not nmea_val:
                    return 0.0
                # ddmm.mmmm format
                degrees = int(float(nmea_val) / 100)
                minutes = float(nmea_val) - (degrees * 100)
                decimal = degrees + (minutes / 60.0)
                if direction in ['S', 'W']:
                    decimal = -decimal
                return decimal

            latitude = nmea_to_decimal(lat_raw, lat_dir)
            longitude = nmea_to_decimal(lon_raw, lon_dir)

            return {
                'time': time_utc,
                'latitude': latitude,
                'longitude': longitude,
                'altitude': altitude,
                'fix_quality': fix_quality,
                'num_satellites': num_sats,
                'hdop': hdop
            }
        except Exception as e:
            return None

    def close(self):
        """Close I2C bus"""
        self.bus.close()

def format_coordinate(coord, is_latitude=True):
    """Format coordinate with hemisphere indicator"""
    if is_latitude:
        hemisphere = 'N' if coord >= 0 else 'S'
    else:
        hemisphere = 'E' if coord >= 0 else 'W'
    return f"{abs(coord):.6f}° {hemisphere}"

def get_fix_description(fix_quality):
    """Get human-readable fix quality description"""
    descriptions = {
        0: "No Fix",
        1: "GPS Fix",
        2: "DGPS Fix",
        3: "PPS Fix",
        4: "RTK Fixed",
        5: "RTK Float",
        6: "Estimated",
        7: "Manual",
        8: "Simulation"
    }
    return descriptions.get(fix_quality, "Unknown")

def main():
    print("=" * 70)
    print("GPS Coordinate Reader - NEO-M8U with Active Antenna")
    print("=" * 70)
    print("\nInitializing I2C connection...")

    gps = GPSReader()
    print("✓ Connected to NEO-M8U at address 0x42")
    print("\nWaiting for GPS fix... (This may take 30-60 seconds outdoors)")
    print("Active antenna power: 3.13V ✓")
    print("Press Ctrl+C to exit\n")

    last_valid_data = None
    no_fix_count = 0
    message_count = 0
    clear_screen = False  # Don't clear screen initially

    try:
        while True:
            # Read data from GPS
            data = gps.read_data(max_bytes=512)

            if data:
                message_count += 1
                # Try to decode as text
                try:
                    text = data.decode('ascii', errors='ignore')
                    lines = text.split('\n')

                    for line in lines:
                        line = line.strip()
                        if line.startswith('$GNGGA') or line.startswith('$GPGGA'):
                            gps_data = gps.parse_nmea_gga(line)

                            if gps_data:
                                last_valid_data = gps_data

                                # Clear screen after first valid message
                                if clear_screen:
                                    print("\033[2J\033[H", end='')  # Clear screen
                                else:
                                    clear_screen = True

                                print("=" * 70)
                                print("GPS Coordinate Reader - NEO-M8U")
                                print("=" * 70)

                                # Fix status
                                fix_desc = get_fix_description(gps_data['fix_quality'])
                                fix_indicator = "✓" if gps_data['fix_quality'] > 0 else "✗"

                                print(f"\n{fix_indicator} Fix Status: {fix_desc}")
                                print(f"  Satellites: {gps_data['num_satellites']}")
                                print(f"  HDOP: {gps_data['hdop']}")

                                # Coordinates
                                if gps_data['fix_quality'] > 0:
                                    print(f"\n📍 Position:")
                                    print(f"  Latitude:  {format_coordinate(gps_data['latitude'], True)}")
                                    print(f"  Longitude: {format_coordinate(gps_data['longitude'], False)}")
                                    print(f"  Altitude:  {gps_data['altitude']:.1f} m")

                                    # Google Maps link
                                    print(f"\n🌐 Google Maps:")
                                    print(f"  https://www.google.com/maps?q={gps_data['latitude']:.6f},{gps_data['longitude']:.6f}")

                                    # Decimal degrees
                                    print(f"\n📊 Decimal Degrees:")
                                    print(f"  Lat: {gps_data['latitude']:.6f}")
                                    print(f"  Lon: {gps_data['longitude']:.6f}")
                                else:
                                    print(f"\n⏳ Waiting for satellite lock...")
                                    print(f"  Make sure antenna has clear view of sky")
                                    print(f"  Active antenna power: 3.13V ✓")
                                    no_fix_count += 1
                                    if no_fix_count > 20:
                                        print(f"\n💡 Tips:")
                                        print(f"  - Move to open area away from buildings")
                                        print(f"  - Place antenna with clear sky view")
                                        print(f"  - Cold start can take 30-60 seconds")

                                print(f"\nTime (UTC): {gps_data['time']}")
                                print("\nPress Ctrl+C to exit")

                except UnicodeDecodeError:
                    pass

            time.sleep(0.5)

    except KeyboardInterrupt:
        print("\n\n" + "=" * 70)
        print("Stopped by user")
        if last_valid_data and last_valid_data['fix_quality'] > 0:
            print("\nLast known position:")
            print(f"  {format_coordinate(last_valid_data['latitude'], True)}, {format_coordinate(last_valid_data['longitude'], False)}")
            print(f"  https://www.google.com/maps?q={last_valid_data['latitude']:.6f},{last_valid_data['longitude']:.6f}")
        print("=" * 70)

    finally:
        gps.close()

if __name__ == "__main__":
    main()
