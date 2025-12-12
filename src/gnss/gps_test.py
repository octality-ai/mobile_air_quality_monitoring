#!/usr/bin/env python3
"""
GPS Test - Full GNSS Display
Shows parsed GPS data similar to MAQM_main.py output

Usage: python3 gps_test.py
"""
import time
from smbus2 import SMBus, i2c_msg
from pynmeagps import NMEAReader
from datetime import datetime

# Configuration
I2C_BUS = 1
GPS_ADDR = 0x42
REG_AVAIL_HIGH = 0xFD
REG_DATA = 0xFF
MAX_CHUNK = 32


class UbloxGNSS:
    """Interface to u-blox GNSS module via I2C/DDC"""

    def __init__(self):
        self.bus = SMBus(I2C_BUS)
        self.addr = GPS_ADDR
        self.max_chunk = MAX_CHUNK
        self.buffer = bytearray()
        self.nmr = NMEAReader(None)
        self.last_position = {
            "lat": None, "lon": None, "alt": None,
            "speed": None, "quality": None,
            "num_sv": None, "hdop": None, "pdop": None, "vdop": None,
            "fix_status": None
        }

    def read_available_bytes(self):
        """Check how many bytes are available in the GNSS receive buffer"""
        try:
            w = i2c_msg.write(self.addr, bytes([REG_AVAIL_HIGH]))
            r = i2c_msg.read(self.addr, 2)
            self.bus.i2c_rdwr(w, r)
            data = bytes(r)
            return data[0] | (data[1] << 8)
        except OSError:
            return 0

    def read_data(self, nbytes):
        """Read data from GNSS module via I2C stream register"""
        out = bytearray()
        while nbytes > 0:
            chunk_size = min(nbytes, self.max_chunk)
            try:
                w = i2c_msg.write(self.addr, bytes([REG_DATA]))
                r = i2c_msg.read(self.addr, chunk_size)
                self.bus.i2c_rdwr(w, r)
                out.extend(bytes(r))
                nbytes -= chunk_size
            except OSError:
                break
        return bytes(out)

    def poll(self):
        """Poll for new GNSS data and update last_position"""
        available = self.read_available_bytes()
        if available > 0:
            read_size = min(available, 512)
            data = self.read_data(read_size)
            self.buffer.extend(data)

            while b'\n' in self.buffer:
                line_end = self.buffer.index(b'\n')
                line = self.buffer[:line_end+1]
                self.buffer = self.buffer[line_end+1:]

                try:
                    line_str = line.decode('ascii').strip()
                    if line_str.startswith('$'):
                        msg = self.nmr.parse(line_str)

                        if msg.msgID == "RMC":
                            # Always update fix status, update position only if valid
                            self.last_position["fix_status"] = msg.status
                            if msg.status == "A":  # A = Active (valid fix), V = Void (no fix)
                                self.last_position.update({
                                    "lat": msg.lat,
                                    "lon": msg.lon,
                                    "speed": float(msg.spd) if msg.spd else None
                                })

                        elif msg.msgID == "GGA" and int(msg.quality) > 0:
                            self.last_position.update({
                                "lat": msg.lat,
                                "lon": msg.lon,
                                "alt": float(msg.alt) if msg.alt not in ("", None) else None,
                                "quality": int(msg.quality),
                                "num_sv": int(msg.numSV) if msg.numSV else None,
                                "hdop": float(msg.HDOP) if msg.HDOP else None
                            })

                        elif msg.msgID == "GSA":
                            # GSA: DOP and active satellites - contains PDOP, HDOP, VDOP
                            if hasattr(msg, 'PDOP') and msg.PDOP:
                                self.last_position.update({
                                    "pdop": float(msg.PDOP) if msg.PDOP else None,
                                    "hdop": float(msg.HDOP) if msg.HDOP else None,
                                    "vdop": float(msg.VDOP) if msg.VDOP else None
                                })
                except Exception:
                    pass

    def get_position_data(self):
        """Return current position data"""
        return self.last_position.copy()

    def close(self):
        """Close I2C bus"""
        self.bus.close()


def format_status_line(data):
    """Format GPS data similar to MAQM_main.py output"""
    fix_status = data['fix_status'] if data['fix_status'] is not None else '?'
    lat_str = f"{data['lat']:.6f}" if data['lat'] is not None else 'N/A'
    lon_str = f"{data['lon']:.6f}" if data['lon'] is not None else 'N/A'
    alt_str = f"{data['alt']:.1f}m" if data['alt'] is not None else 'N/A'
    speed_str = f"{data['speed']:.1f}kn" if data['speed'] is not None else 'N/A'
    pdop_str = f"{data['pdop']:.1f}" if data['pdop'] is not None else 'N/A'
    hdop_str = f"{data['hdop']:.1f}" if data['hdop'] is not None else 'N/A'
    vdop_str = f"{data['vdop']:.1f}" if data['vdop'] is not None else 'N/A'
    num_sv_str = f"{data['num_sv']}" if data['num_sv'] is not None else 'N/A'
    quality_str = f"{data['quality']}" if data['quality'] is not None else 'N/A'

    return (f"[{datetime.now().strftime('%H:%M:%S')}] "
            f"GPS:{fix_status} {lat_str}°,{lon_str}° Alt:{alt_str} {speed_str} "
            f"Q:{quality_str} SV:{num_sv_str} P/H/V:{pdop_str}/{hdop_str}/{vdop_str}")


def main():
    print("=" * 80)
    print("GPS TEST - Full GNSS Display")
    print("=" * 80)
    print(f"I2C Bus: {I2C_BUS}")
    print(f"I2C Address: 0x{GPS_ADDR:02X}")
    print("=" * 80)
    print()
    print("Status indicators:")
    print("  GPS:A = Active (valid fix)")
    print("  GPS:V = Void (no fix, searching)")
    print("  Q     = Fix quality (1=GPS, 2=DGPS)")
    print("  SV    = Number of satellites in use")
    print("  P/H/V = PDOP/HDOP/VDOP (lower is better)")
    print()
    print("Press Ctrl+C to stop")
    print("-" * 80)
    print()

    gnss = UbloxGNSS()
    poll_count = 0
    last_display_time = time.time()

    try:
        while True:
            poll_count += 1

            # Poll GPS data
            gnss.poll()

            # Display every second
            if time.time() - last_display_time >= 1.0:
                data = gnss.get_position_data()
                print(format_status_line(data))
                last_display_time = time.time()

            time.sleep(0.1)  # 10Hz polling

    except KeyboardInterrupt:
        print()
        print("=" * 80)
        print("Final GPS Status:")
        print("-" * 80)
        data = gnss.get_position_data()
        print(f"  Fix Status: {data['fix_status']}")
        if data['lat'] is not None:
            print(f"  Position:   {data['lat']:.7f}°, {data['lon']:.7f}°")
            print(f"  Altitude:   {data['alt']:.1f} m" if data['alt'] else "  Altitude:   N/A")
        else:
            print(f"  Position:   No fix")
        print(f"  Quality:    {data['quality']}" if data['quality'] else "  Quality:    N/A")
        print(f"  Satellites: {data['num_sv']}" if data['num_sv'] else "  Satellites: N/A")
        print(f"  PDOP:       {data['pdop']:.2f}" if data['pdop'] else "  PDOP:       N/A")
        print(f"  HDOP:       {data['hdop']:.2f}" if data['hdop'] else "  HDOP:       N/A")
        print(f"  VDOP:       {data['vdop']:.2f}" if data['vdop'] else "  VDOP:       N/A")
        print("=" * 80)
    finally:
        gnss.close()


if __name__ == "__main__":
    main()
