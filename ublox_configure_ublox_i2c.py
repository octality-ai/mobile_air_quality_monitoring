#!/usr/bin/env python3
"""
Minimal u-blox GNSS I2C configuration
Enables NMEA output on I2C/DDC port only
"""
import time
from smbus2 import SMBus, i2c_msg

ADDR = 0x42
REG_AVAIL_HIGH = 0xFD
REG_DATA = 0xFF
I2C_BUS = 1

def read_available(bus):
    """Check bytes available"""
    try:
        w = i2c_msg.write(ADDR, bytes([REG_AVAIL_HIGH]))
        r = i2c_msg.read(ADDR, 2)
        bus.i2c_rdwr(w, r)
        data = bytes(r)
        return data[0] | (data[1] << 8)
    except:
        return 0

def drain_buffer(bus):
    """Drain any pending data"""
    try:
        avail = read_available(bus)
        if avail > 0:
            # Read and discard
            w = i2c_msg.write(ADDR, bytes([REG_DATA]))
            r = i2c_msg.read(ADDR, min(avail, 255))
            bus.i2c_rdwr(w, r)
            print(f"  Drained {avail} bytes")
    except:
        pass

def send_ubx_raw(bus, msg_bytes):
    """Send raw UBX command via I2C with chunking"""
    try:
        # Chunk the message into smaller writes
        chunk_size = 32
        for i in range(0, len(msg_bytes), chunk_size):
            chunk = msg_bytes[i:i+chunk_size]
            data = bytes([REG_DATA]) + chunk
            bus.write_i2c_block_data(ADDR, data[0], list(data[1:]))
            time.sleep(0.05)

        time.sleep(0.5)  # Wait for processing
        drain_buffer(bus)  # Clear ACK/NAK response
        return True
    except Exception as e:
        print(f"  ERROR: {e}")
        return False

print("Configuring u-blox GNSS for I2C/DDC output...")
print(f"Address: 0x{ADDR:02X}, Bus: {I2C_BUS}")
print()

bus = SMBus(I2C_BUS)

# Wait for module to be ready
print("Waiting for module to stabilize...")
time.sleep(3)
drain_buffer(bus)

# Hand-crafted UBX messages (avoiding pyubx2 parameter issues)

# CFG-MSG: Enable NMEA GGA on I2C (rateDDC=1)
# Header: b5 62, Class: 06, ID: 01, Length: 08 00
# Payload: F0 00 (NMEA-GGA), 01 (DDC rate), 00 00 00 00 00 (other ports disabled)
print("Enabling NMEA GGA on I2C...")
msg_gga = bytes([
    0xB5, 0x62,           # UBX header
    0x06, 0x01,           # CFG-MSG
    0x08, 0x00,           # Length = 8
    0xF0, 0x00,           # NMEA GGA
    0x01,                 # DDC rate = 1
    0x00, 0x00, 0x00,     # UART1, UART2, USB = 0
    0x00, 0x00,           # SPI, reserved = 0
    0x01, 0x3B            # Checksum (pre-calculated)
])
send_ubx_raw(bus, msg_gga)

# CFG-MSG: Enable NMEA RMC on I2C
print("Enabling NMEA RMC on I2C...")
msg_rmc = bytes([
    0xB5, 0x62,
    0x06, 0x01,
    0x08, 0x00,
    0xF0, 0x04,           # NMEA RMC
    0x01,                 # DDC rate = 1
    0x00, 0x00, 0x00,
    0x00, 0x00,
    0x05, 0x47            # Checksum
])
send_ubx_raw(bus, msg_rmc)

bus.close()

print()
print("Configuration complete!")
print("Run: python3 test_ublox_gps.py")
