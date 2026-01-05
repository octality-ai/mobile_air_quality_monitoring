#!/usr/bin/env python3
"""
Comprehensive GPS diagnostic tool for NEO-M8U
Checks satellite visibility, signal strength, antenna status, and fix issues
"""

import smbus2
import time
import struct
from datetime import datetime

I2C_BUS = 1
UBLOX_ADDR = 0x42
REG_DATA_STREAM = 0xFF
REG_DATA_AVAILABLE_HIGH = 0xFD
REG_DATA_AVAILABLE_LOW = 0xFE

class GPSDiagnostic:
    def __init__(self):
        self.bus = smbus2.SMBus(I2C_BUS)
        self.satellites = {}
        self.fix_status = "No Fix"
        self.num_sats_used = 0
        self.antenna_status = "Unknown"

    def calculate_checksum(self, msg_class, msg_id, payload):
        ck_a = 0
        ck_b = 0
        for byte in [msg_class, msg_id, len(payload) & 0xFF, (len(payload) >> 8) & 0xFF]:
            ck_a = (ck_a + byte) & 0xFF
            ck_b = (ck_b + ck_a) & 0xFF
        for byte in payload:
            ck_a = (ck_a + byte) & 0xFF
            ck_b = (ck_b + ck_a) & 0xFF
        return ck_a, ck_b

    def create_ubx_message(self, msg_class, msg_id, payload):
        ck_a, ck_b = self.calculate_checksum(msg_class, msg_id, payload)
        msg = bytearray([0xB5, 0x62, msg_class, msg_id, len(payload) & 0xFF, (len(payload) >> 8) & 0xFF])
        msg.extend(payload)
        msg.extend([ck_a, ck_b])
        return bytes(msg)

    def send_ubx(self, msg):
        max_chunk = 32
        try:
            for offset in range(0, len(msg), max_chunk):
                chunk = msg[offset:offset + max_chunk]
                self.bus.write_i2c_block_data(UBLOX_ADDR, REG_DATA_STREAM, list(chunk))
                time.sleep(0.01)
            return True
        except Exception as e:
            print(f"Send error: {e}")
            return False

    def read_data(self, max_bytes=512):
        """Read available data from GPS module"""
        try:
            high = self.bus.read_byte_data(UBLOX_ADDR, REG_DATA_AVAILABLE_HIGH)
            low = self.bus.read_byte_data(UBLOX_ADDR, REG_DATA_AVAILABLE_LOW)
            avail = (high << 8) | low

            if avail == 0 or avail == 0xFFFF:
                return None

            bytes_to_read = min(avail, max_bytes)
            data = []

            for offset in range(0, bytes_to_read, 32):
                chunk_size = min(32, bytes_to_read - offset)
                chunk = self.bus.read_i2c_block_data(UBLOX_ADDR, REG_DATA_STREAM, chunk_size)
                data.extend(chunk)

            return bytes(data)
        except Exception as e:
            return None

    def parse_ubx_nav_sat(self, payload):
        """Parse UBX-NAV-SAT message (satellite information)"""
        if len(payload) < 8:
            return

        iTOW = struct.unpack('<I', payload[0:4])[0]
        version = payload[4]
        numSvs = payload[5]

        self.satellites.clear()

        offset = 8
        for i in range(numSvs):
            if offset + 12 > len(payload):
                break

            gnssId = payload[offset]
            svId = payload[offset + 1]
            cno = payload[offset + 2]  # Signal strength (dBHz)
            elev = struct.unpack('b', bytes([payload[offset + 3]]))[0]  # Elevation (signed)
            azim = struct.unpack('<h', payload[offset + 4:offset + 6])[0]  # Azimuth
            prRes = struct.unpack('<h', payload[offset + 6:offset + 8])[0]
            flags = struct.unpack('<I', payload[offset + 8:offset + 12])[0]

            quality = (flags >> 0) & 0x07
            svUsed = (flags >> 3) & 0x01
            health = (flags >> 4) & 0x03

            gnss_names = {0: "GPS", 1: "SBAS", 2: "Galileo", 3: "BeiDou", 5: "QZSS", 6: "GLONASS"}
            gnss_name = gnss_names.get(gnssId, f"GNSS{gnssId}")

            self.satellites[f"{gnss_name}-{svId}"] = {
                'cno': cno,
                'elev': elev,
                'azim': azim,
                'used': svUsed,
                'quality': quality,
                'health': health,
                'gnss': gnss_name
            }

            offset += 12

    def parse_ubx_nav_status(self, payload):
        """Parse UBX-NAV-STATUS message (navigation status)"""
        if len(payload) < 16:
            return

        gpsFix = payload[4]
        flags = payload[5]

        fix_types = {0: "No Fix", 1: "Dead Reckoning", 2: "2D Fix", 3: "3D Fix",
                     4: "GPS+DR", 5: "Time Only"}
        self.fix_status = fix_types.get(gpsFix, f"Unknown ({gpsFix})")

        gpsFixOk = flags & 0x01
        diffSoln = (flags >> 1) & 0x01

        if not gpsFixOk:
            self.fix_status = "No Fix (not OK)"

    def parse_ubx_mon_hw(self, payload):
        """Parse UBX-MON-HW message (hardware status)"""
        if len(payload) < 60:
            return

        aStatus = payload[20]
        aPower = payload[21]

        # Antenna status
        status_map = {0: "INIT", 1: "UNKNOWN", 2: "OK", 3: "SHORT", 4: "OPEN"}
        self.antenna_status = status_map.get(aStatus, f"Code {aStatus}")

        # Antenna power
        power_map = {0: "OFF", 1: "ON", 2: "UNKNOWN"}
        antenna_power = power_map.get(aPower, f"Code {aPower}")

        return {
            'status': self.antenna_status,
            'power': antenna_power
        }

    def parse_nmea_gga(self, line):
        """Parse NMEA GGA for basic fix info"""
        try:
            if not line.startswith('$GNGGA') and not line.startswith('$GPGGA'):
                return

            parts = line.split(',')
            if len(parts) < 15:
                return

            fix_quality = int(parts[6]) if parts[6] else 0
            num_sats = int(parts[7]) if parts[7] else 0

            fix_desc = {0: "No Fix", 1: "GPS Fix", 2: "DGPS", 4: "RTK Fixed", 5: "RTK Float"}
            self.fix_status = fix_desc.get(fix_quality, f"Quality {fix_quality}")
            self.num_sats_used = num_sats

        except:
            pass

    def process_data(self, data):
        """Process incoming data and extract UBX/NMEA messages"""
        if not data:
            return

        # Try NMEA first
        try:
            text = data.decode('ascii', errors='ignore')
            for line in text.split('\n'):
                line = line.strip()
                if line.startswith('$'):
                    self.parse_nmea_gga(line)
        except:
            pass

        # Parse UBX messages
        i = 0
        while i < len(data) - 8:
            if data[i] == 0xB5 and data[i+1] == 0x62:
                msg_class = data[i+2]
                msg_id = data[i+3]
                payload_len = data[i+4] + (data[i+5] << 8)

                if i + 8 + payload_len <= len(data):
                    payload = data[i+6:i+6+payload_len]

                    # NAV-SAT (0x01 0x35)
                    if msg_class == 0x01 and msg_id == 0x35:
                        self.parse_ubx_nav_sat(payload)
                    # NAV-STATUS (0x01 0x03)
                    elif msg_class == 0x01 and msg_id == 0x03:
                        self.parse_ubx_nav_status(payload)
                    # MON-HW (0x0A 0x09)
                    elif msg_class == 0x0A and msg_id == 0x09:
                        self.parse_ubx_mon_hw(payload)

                    i += 8 + payload_len
                else:
                    i += 1
            else:
                i += 1

    def request_satellite_info(self):
        """Request satellite information"""
        # Poll NAV-SAT
        msg = self.create_ubx_message(0x01, 0x35, b'')
        self.send_ubx(msg)

    def request_nav_status(self):
        """Request navigation status"""
        msg = self.create_ubx_message(0x01, 0x03, b'')
        self.send_ubx(msg)

    def request_hw_status(self):
        """Request hardware status"""
        msg = self.create_ubx_message(0x0A, 0x09, b'')
        self.send_ubx(msg)

    def print_status(self):
        """Print current diagnostic status"""
        print("\033[2J\033[H")  # Clear screen
        print("=" * 80)
        print(f"GPS Diagnostic Tool - {datetime.now().strftime('%H:%M:%S')}")
        print("=" * 80)

        # Fix status
        fix_icon = "✓" if "Fix" in self.fix_status and "No" not in self.fix_status else "✗"
        print(f"\n{fix_icon} Fix Status: {self.fix_status}")
        print(f"  Satellites in use: {self.num_sats_used}")
        print(f"  Antenna status: {self.antenna_status}")

        # Satellite summary
        total_sats = len(self.satellites)
        used_sats = sum(1 for s in self.satellites.values() if s['used'])
        avg_cno = sum(s['cno'] for s in self.satellites.values()) / total_sats if total_sats > 0 else 0

        if self.satellites:

            print(f"\n📡 Satellites:")
            print(f"  Total visible: {total_sats}")
            print(f"  Used in solution: {used_sats}")
            print(f"  Average signal: {avg_cno:.1f} dBHz")

            # Group by GNSS
            by_gnss = {}
            for sat_id, sat_data in self.satellites.items():
                gnss = sat_data['gnss']
                if gnss not in by_gnss:
                    by_gnss[gnss] = []
                by_gnss[gnss].append(sat_data)

            print(f"\n  By constellation:")
            for gnss, sats in sorted(by_gnss.items()):
                used = sum(1 for s in sats if s['used'])
                print(f"    {gnss}: {len(sats)} visible, {used} used")

            # Show detailed satellite list
            print(f"\n  Satellite Details (Top 15 by signal strength):")
            print(f"  {'ID':<12} {'Signal':<10} {'Elev':<8} {'Azim':<8} {'Used':<6} {'Quality'}")
            print(f"  {'-'*70}")

            sorted_sats = sorted(self.satellites.items(), key=lambda x: x[1]['cno'], reverse=True)[:15]
            for sat_id, sat_data in sorted_sats:
                used_mark = "✓" if sat_data['used'] else "✗"
                quality_stars = "★" * min(sat_data['quality'], 7)
                signal_bar = "█" * (sat_data['cno'] // 5)

                print(f"  {sat_id:<12} {sat_data['cno']:2d} dBHz {signal_bar:<10} {sat_data['elev']:3d}° {sat_data['azim']:4d}° {used_mark:<6} {quality_stars}")
        else:
            print(f"\n⚠ No satellite data available")
            print(f"  Module may be initializing or not receiving signals")

        # Diagnostic hints
        print(f"\n💡 Diagnostics:")
        if total_sats == 0:
            print(f"  ⚠ NO SATELLITES VISIBLE!")
            print(f"    - Check antenna connection (should be tight)")
            print(f"    - Verify antenna has clear sky view")
            print(f"    - Make sure antenna is outdoors or near window")
            print(f"    - Check for antenna cable damage")
        elif used_sats == 0:
            print(f"  ⚠ Satellites visible but none used in solution")
            print(f"    - Signal quality may be too low")
            print(f"    - Module is still acquiring (wait 30-60s)")
            print(f"    - Check for nearby interference (WiFi, metal structures)")
        elif avg_cno < 30:
            print(f"  ⚠ Low signal strength (avg {avg_cno:.1f} dBHz)")
            print(f"    - Improve antenna placement (higher, clearer view)")
            print(f"    - Check for obstructions (buildings, trees)")
            print(f"    - Signal >35 dBHz is good, >40 dBHz is excellent")
        else:
            print(f"  ✓ Signal strength looks good!")
            if used_sats < 4:
                print(f"  ⏳ Waiting for lock (need 4+ satellites for 3D fix)")

        print(f"\nPress Ctrl+C to exit")

    def close(self):
        self.bus.close()


def main():
    diag = GPSDiagnostic()

    try:
        print("GPS Diagnostic Tool Starting...")
        print("Requesting satellite information...\n")
        time.sleep(2)

        iteration = 0
        while True:
            # Request info every 5 seconds
            if iteration % 10 == 0:
                diag.request_satellite_info()
                diag.request_nav_status()
                diag.request_hw_status()

            # Read available data
            data = diag.read_data(max_bytes=1024)
            if data:
                diag.process_data(data)

            # Update display every second
            if iteration % 2 == 0:
                diag.print_status()

            time.sleep(0.5)
            iteration += 1

    except KeyboardInterrupt:
        print("\n\nDiagnostic stopped by user")
    finally:
        diag.close()


if __name__ == "__main__":
    main()
