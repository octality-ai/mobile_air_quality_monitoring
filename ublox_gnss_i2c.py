#!/usr/bin/env python3
"""
u-blox GNSS I2C Reader
Reads NMEA data from u-blox GPS module via I2C/DDC interface
"""

import time
from smbus2 import SMBus, i2c_msg
from pynmeagps import NMEAReader

# u-blox I2C/DDC Configuration
I2C_ADDR = 0x42          # Default u-blox GNSS I2C address
REG_AVAIL_HIGH = 0xFD    # Register for data available (high byte)
REG_AVAIL_LOW = 0xFE     # Register for data available (low byte)
REG_DATA_STREAM = 0xFF   # Register for data stream
MAX_CHUNK = 32           # Max bytes per I2C read (adjust based on cable length)
I2C_BUS = 1              # I2C bus number (usually 1 on Raspberry Pi)

class UbloxGNSS:
    """Interface to u-blox GNSS module via I2C/DDC"""

    def __init__(self, i2c_bus=I2C_BUS, addr=I2C_ADDR, max_chunk=MAX_CHUNK):
        self.bus = SMBus(i2c_bus)
        self.addr = addr
        self.max_chunk = max_chunk
        self.buffer = bytearray()
        self.nmr = NMEAReader(None)

    def read_available_bytes(self):
        """Check how many bytes are available in the GNSS receive buffer"""
        try:
            # Write register address, then read 2 bytes (little-endian)
            w = i2c_msg.write(self.addr, bytes([REG_AVAIL_HIGH]))
            r = i2c_msg.read(self.addr, 2)
            self.bus.i2c_rdwr(w, r)
            data = bytes(r)
            # Combine low and high byte
            return data[0] | (data[1] << 8)
        except OSError as e:
            print(f"I2C read error: {e}")
            return 0

    def read_data(self, nbytes):
        """Read data from GNSS module via I2C stream register"""
        out = bytearray()
        while nbytes > 0:
            # Read in chunks to avoid I2C buffer issues
            chunk_size = min(nbytes, self.max_chunk)
            try:
                w = i2c_msg.write(self.addr, bytes([REG_DATA_STREAM]))
                r = i2c_msg.read(self.addr, chunk_size)
                self.bus.i2c_rdwr(w, r)
                out.extend(bytes(r))
                nbytes -= chunk_size
            except OSError as e:
                print(f"I2C data read error: {e}")
                break
        return bytes(out)

    def poll(self):
        """Poll for new GNSS data and yield parsed NMEA messages"""
        available = self.read_available_bytes()
        if available > 0:
            # Read data in manageable chunks
            read_size = min(available, 512)
            data = self.read_data(read_size)
            self.buffer.extend(data)

            # Process complete lines
            while b'\n' in self.buffer:
                line_end = self.buffer.index(b'\n')
                line = self.buffer[:line_end+1]
                self.buffer = self.buffer[line_end+1:]

                try:
                    line_str = line.decode('ascii').strip()
                    if line_str.startswith('$'):
                        # Parse NMEA sentence
                        msg = self.nmr.parse(line_str)
                        yield msg
                except Exception:
                    # Skip malformed messages
                    pass

def dm_to_decimal(dm_value, hemisphere):
    """Convert NMEA ddmm.mmmm format to decimal degrees"""
    if not dm_value or dm_value == "":
        return None
    try:
        dm = float(dm_value)
        degrees = int(dm // 100)
        minutes = dm - degrees * 100
        decimal = degrees + minutes / 60.0
        if hemisphere in ("S", "W"):
            decimal = -decimal
        return decimal
    except (ValueError, TypeError):
        return None

def main():
    """Main loop to read and display GNSS data"""
    print("=" * 60)
    print("u-blox GNSS I2C Reader")
    print("=" * 60)
    print(f"I2C Address: 0x{I2C_ADDR:02X}")
    print(f"I2C Bus: {I2C_BUS}")
    print(f"Protocol: NMEA")
    print(f"Max chunk size: {MAX_CHUNK} bytes")
    print("=" * 60)
    print()

    gnss = UbloxGNSS()
    print("Reading GNSS data...")
    print()

    last_position = {"lat": None, "lon": None, "alt": None, "time": None}

    try:
        poll_count = 0
        while True:
            poll_count += 1
            msg_count = 0

            for msg in gnss.poll():
                msg_count += 1

                if msg.msgID == "RMC" and msg.status == "A":
                    # RMC: Recommended Minimum Navigation Information
                    # pynmeagps already returns decimal degrees
                    lat = msg.lat
                    lon = msg.lon
                    speed = float(msg.spd) if msg.spd else 0
                    course = float(msg.cog) if msg.cog else 0

                    print(f"RMC | Lat: {lat:.7f}° | Lon: {lon:.7f}° | "
                          f"Speed: {speed:.1f}kn | Course: {course:.1f}°")

                    last_position.update({"lat": lat, "lon": lon})

                elif msg.msgID == "GGA" and int(msg.quality) > 0:
                    # GGA: Global Positioning System Fix Data
                    # pynmeagps already returns decimal degrees
                    lat = msg.lat
                    lon = msg.lon
                    alt = float(msg.alt) if msg.alt not in ("", None) else None
                    num_sv = int(msg.numSV) if msg.numSV else 0
                    hdop = float(msg.HDOP) if msg.HDOP else 0

                    quality_map = {"1": "GPS", "2": "DGPS", "4": "RTK Fixed",
                                   "5": "RTK Float", "6": "Estimated"}
                    qual_str = quality_map.get(msg.quality, f"Q{msg.quality}")

                    print(f"GGA | {qual_str} | Lat: {lat:.7f}° | Lon: {lon:.7f}° | "
                          f"Alt: {alt}m | SV: {num_sv} | HDOP: {hdop}")

                    last_position.update({"lat": lat, "lon": lon, "alt": alt})

                elif msg.msgID == "GSA":
                    # GSA: DOP and active satellites
                    if hasattr(msg, 'PDOP') and msg.PDOP:
                        print(f"GSA | Mode: {msg.navMode} | "
                              f"PDOP: {msg.PDOP} | HDOP: {msg.HDOP} | VDOP: {msg.VDOP}")

                elif msg.msgID == "GSV":
                    # GSV: Satellites in view - show first message only
                    if hasattr(msg, 'msgNum') and msg.msgNum == '1':
                        print(f"GSV | {msg.numSV} satellites in view")

            # Status update every 10 seconds if no messages
            if poll_count % 100 == 0 and msg_count == 0:
                avail = gnss.read_available_bytes()
                print(f"[Poll {poll_count}] Available: {avail} bytes")

            time.sleep(0.1)  # 10Hz polling

    except KeyboardInterrupt:
        print("\n" + "=" * 60)
        print("Shutting down...")
        if last_position["lat"] is not None:
            print(f"Last position: {last_position['lat']:.7f}°, {last_position['lon']:.7f}°")
            if last_position["alt"]:
                print(f"Last altitude: {last_position['alt']:.2f}m")
        print("=" * 60)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        gnss.bus.close()

if __name__ == "__main__":
    main()
