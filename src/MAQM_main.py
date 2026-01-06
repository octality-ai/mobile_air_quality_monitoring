#!/usr/bin/env python3
"""
Mobile Air Quality Monitor (MAQM) - Main Data Logger
Integrates GNSS (u-blox), SEN66 (Sensirion), and SpecSensor (DGS2-970)
Logs unified data to CSV with 1-second sampling and 60-second buffered writes
Controls air sampling fans (Group 2) during data collection
"""

import time
import csv
import serial
import os
import sys
import signal
from datetime import datetime
from smbus2 import SMBus, i2c_msg
from pynmeagps import NMEAReader
from sensirion_i2c_driver import LinuxI2cTransceiver, I2cConnection, CrcCalculator
from sensirion_driver_adapters.i2c_adapter.i2c_channel import I2cChannel
from sensirion_i2c_sen66.device import Sen66Device

# Add parent directory to path for fan controller import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'fan'))
from dual_fan_controller import DualFanController

# Try to import tachometer monitoring (optional, fail gracefully if lgpio not available)
try:
    from read_group2_tachometer import TachometerReader
    import lgpio
    TACHOMETER_AVAILABLE = True
except ImportError:
    TACHOMETER_AVAILABLE = False
    print("WARNING: Tachometer monitoring disabled (lgpio not available)")

# ============================================================================
# Configuration
# ============================================================================

# GNSS Configuration
GNSS_I2C_BUS = 1
GNSS_I2C_ADDR = 0x42
GNSS_REG_AVAIL_HIGH = 0xFD
GNSS_REG_DATA_STREAM = 0xFF
GNSS_MAX_CHUNK = 32

# SEN66 Configuration
SEN66_I2C_PORT = '/dev/i2c-1'
SEN66_I2C_ADDR = 0x6B

# SpecSensor Configuration
SPEC_CO_SERIAL_PORT = "/dev/ttyAMA0"
SPEC_O3_SERIAL_PORT = "/dev/ttyAMA1"
SPEC_NO2_SERIAL_PORT = "/dev/ttyAMA3"
SPEC_BAUDRATE = 9600

# Logging Configuration
CSV_BUFFER_INTERVAL = 60  # Write to CSV every 60 seconds
SAMPLE_INTERVAL = 1.0     # Sample every 1 second

# Fan Configuration
FAN_SPEED_PERCENT = 40    # Default air sampling fan speed (Group 2)


# ============================================================================
# GNSS Reader Class
# ============================================================================

class UbloxGNSS:
    """Interface to u-blox GNSS module via I2C/DDC"""

    def __init__(self, i2c_bus=GNSS_I2C_BUS, addr=GNSS_I2C_ADDR, max_chunk=GNSS_MAX_CHUNK):
        self.bus = SMBus(i2c_bus)
        self.addr = addr
        self.max_chunk = max_chunk
        self.buffer = bytearray()
        self.nmr = NMEAReader(None)
        self.last_position = {"lat": None, "lon": None, "alt": None,
                             "speed": None, "quality": None,
                             "num_sv": None, "hdop": None, "pdop": None, "vdop": None,
                             "fix_status": None}

    def read_available_bytes(self):
        """Check how many bytes are available in the GNSS receive buffer"""
        try:
            w = i2c_msg.write(self.addr, bytes([GNSS_REG_AVAIL_HIGH]))
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
                w = i2c_msg.write(self.addr, bytes([GNSS_REG_DATA_STREAM]))
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


# ============================================================================
# SpecSensor Reader Class
# ============================================================================

class SpecSensor:
    """Interface to DGS2-970 gas sensor via UART"""

    def __init__(self, port, baudrate=SPEC_BAUDRATE):
        self.port = port
        self.baudrate = baudrate
        self.last_measurement = {
            "sensor_sn": None,
            "gas_ppb": None,
            "gas_ppm": None,
            "temperature_c": None,
            "humidity_pct": None,
            "adc_g": None,
            "adc_t": None,
            "adc_h": None
        }

    def read_measurement(self):
        """Read and parse a single measurement from the sensor"""
        try:
            with serial.Serial(self.port, self.baudrate, timeout=2) as ser:
                ser.reset_input_buffer()
                ser.write(b'\r')
                line = ser.readline().decode(errors="ignore").strip()

                if line:
                    fields = [f.strip() for f in line.split(",")]
                    if len(fields) >= 7:
                        ppb = int(fields[1])
                        temp_raw = int(fields[2])
                        rh_raw = int(fields[3])

                        self.last_measurement.update({
                            "sensor_sn": fields[0],
                            "gas_ppb": ppb,
                            "gas_ppm": ppb / 1000.0,
                            "temperature_c": temp_raw / 100.0,
                            "humidity_pct": rh_raw / 100.0,
                            "adc_g": int(fields[4]),
                            "adc_t": int(fields[5]),
                            "adc_h": int(fields[6])
                        })
        except Exception:
            pass

    def get_measurement_data(self):
        """Return current measurement data"""
        return self.last_measurement.copy()


# ============================================================================
# Main Logger
# ============================================================================

class MAQMLogger:
    """Main data logger integrating all sensors"""

    def __init__(self):
        # Save CSV to /home/octa/octa/data/ directory
        csv_dir = "/home/octa/octa/data"
        os.makedirs(csv_dir, exist_ok=True)  # Create directory if it doesn't exist
        csv_filename = f"MAQM_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        self.csv_file = os.path.join(csv_dir, csv_filename)
        self.buffer = []
        self.last_write_time = time.time()
        self.running = True

        # Initialize sensors
        print("Initializing sensors...")

        # GNSS
        self.gnss = UbloxGNSS()

        # SEN66
        self.sen66_transceiver = LinuxI2cTransceiver(SEN66_I2C_PORT)
        self.sen66_channel = I2cChannel(
            I2cConnection(self.sen66_transceiver),
            slave_address=SEN66_I2C_ADDR,
            crc=CrcCalculator(8, 0x31, 0xff, 0x0)
        )
        self.sen66 = Sen66Device(self.sen66_channel)
        self.sen66.device_reset()
        time.sleep(1.2)
        self.sen66.start_continuous_measurement()

        # SpecSensors
        self.spec_co = SpecSensor(port=SPEC_CO_SERIAL_PORT)
        self.spec_no2 = SpecSensor(port=SPEC_NO2_SERIAL_PORT)
        self.spec_o3 = SpecSensor(port=SPEC_O3_SERIAL_PORT)

        # Initialize fan controller
        print("Initializing air sampling fans...")
        self.fans = DualFanController()

        # Initialize tachometer monitoring for Group 2 fans
        self.tachometers = {}
        self.gpio_chip = None
        if TACHOMETER_AVAILABLE:
            try:
                print("Initializing tachometer monitoring for air sampling fans...")
                self.gpio_chip = lgpio.gpiochip_open(0)

                # Group 2 tachometer pins: {pwm_gpio: tach_gpio}
                tach_pins = {
                    13: 6,   # GPIO13 PWM → GPIO6 Tach (Fan 1)
                    19: 26   # GPIO19 PWM → GPIO26 Tach (Fan 2)
                }

                for pwm_gpio, tach_gpio in tach_pins.items():
                    try:
                        tach = TachometerReader(self.gpio_chip, tach_gpio)
                        self.tachometers[pwm_gpio] = tach
                        print(f"  Tachometer initialized: GPIO{tach_gpio} monitors fan on GPIO{pwm_gpio}")
                    except Exception as e:
                        print(f"  WARNING: Failed to initialize tachometer on GPIO{tach_gpio}: {e}")

                if self.tachometers:
                    print("Tachometer monitoring enabled")
                else:
                    print("WARNING: No tachometers initialized")
            except Exception as e:
                print(f"WARNING: Failed to initialize tachometer monitoring: {e}")

        # Initialize CSV
        self._initialize_csv()

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

        print(f"Logging to: {self.csv_file}")
        print("=" * 80)

    def _signal_handler(self, signum, _frame):
        """Handle shutdown signals (SIGTERM, SIGINT)"""
        print(f"\nReceived signal {signum}, initiating graceful shutdown...")
        self.running = False

    def _initialize_csv(self):
        """Create CSV file with headers"""
        fieldnames = [
            "timestamp",
            # GNSS fields
            "gnss_lat", "gnss_lon", "gnss_alt", "gnss_speed",
            "gnss_fix_status", "gnss_quality", "gnss_num_sv",
            "gnss_pdop", "gnss_hdop", "gnss_vdop",
            # Fan tachometer fields (Group 2 air sampling fans)
            "fan1_rpm", "fan2_rpm",
            # SEN66 fields
            "pm1p0", "pm2p5", "pm4p0", "pm10p0",
            "sen66_humidity", "sen66_temperature", "voc_index", "nox_index", "co2",
            # SpecSensor CO fields
            "spec_co_sensor_sn", "spec_co_ppb", "spec_co_ppm",
            "spec_co_temperature_c", "spec_co_humidity_pct",
            "spec_co_adc_g", "spec_co_adc_t", "spec_co_adc_h",
            # SpecSensor NO2 fields
            "spec_no2_sensor_sn", "spec_no2_ppb", "spec_no2_ppm",
            "spec_no2_temperature_c", "spec_no2_humidity_pct",
            "spec_no2_adc_g", "spec_no2_adc_t", "spec_no2_adc_h",
            # SpecSensor O3 fields
            "spec_o3_sensor_sn", "spec_o3_ppb", "spec_o3_ppm",
            "spec_o3_temperature_c", "spec_o3_humidity_pct",
            "spec_o3_adc_g", "spec_o3_adc_t", "spec_o3_adc_h"
        ]

        with open(self.csv_file, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

    def _collect_sensor_data(self):
        """Collect data from all sensors"""
        row = {"timestamp": datetime.now().isoformat()}

        # Poll GNSS
        self.gnss.poll()
        gnss_data = self.gnss.get_position_data()
        row.update({
            "gnss_lat": gnss_data["lat"],
            "gnss_lon": gnss_data["lon"],
            "gnss_alt": gnss_data["alt"],
            "gnss_speed": gnss_data["speed"],
            "gnss_fix_status": gnss_data["fix_status"],
            "gnss_quality": gnss_data["quality"],
            "gnss_num_sv": gnss_data["num_sv"],
            "gnss_pdop": gnss_data["pdop"],
            "gnss_hdop": gnss_data["hdop"],
            "gnss_vdop": gnss_data["vdop"]
        })

        # Read fan tachometers (Group 2 air sampling fans)
        fan1_rpm = None
        fan2_rpm = None
        if self.tachometers:
            try:
                # Update RPM readings
                for pwm_gpio, tach in self.tachometers.items():
                    rpm = tach.update_rpm()
                    if pwm_gpio == 13:
                        fan1_rpm = rpm
                    elif pwm_gpio == 19:
                        fan2_rpm = rpm
            except Exception:
                pass
        row.update({
            "fan1_rpm": fan1_rpm,
            "fan2_rpm": fan2_rpm
        })

        # Read SEN66
        try:
            (pm1p0, pm2p5, pm4p0, pm10p0, humidity, temperature,
             voc_index, nox_index, co2) = self.sen66.read_measured_values()
            row.update({
                "pm1p0": pm1p0.value if pm1p0 is not None else None,
                "pm2p5": pm2p5.value if pm2p5 is not None else None,
                "pm4p0": pm4p0.value if pm4p0 is not None else None,
                "pm10p0": pm10p0.value if pm10p0 is not None else None,
                "sen66_humidity": humidity.value if humidity is not None else None,
                "sen66_temperature": temperature.value if temperature is not None else None,
                "voc_index": voc_index.value if voc_index is not None else None,
                "nox_index": nox_index.value if nox_index is not None else None,
                "co2": co2.value if co2 is not None else None
            })
        except Exception:
            row.update({
                "pm1p0": None, "pm2p5": None, "pm4p0": None, "pm10p0": None,
                "sen66_humidity": None, "sen66_temperature": None,
                "voc_index": None, "nox_index": None, "co2": None
            })

        # Read SpecSensor CO
        self.spec_co.read_measurement()
        spec_co_data = self.spec_co.get_measurement_data()
        row.update({
            "spec_co_sensor_sn": spec_co_data["sensor_sn"],
            "spec_co_ppb": spec_co_data["gas_ppb"],
            "spec_co_ppm": spec_co_data["gas_ppm"],
            "spec_co_temperature_c": spec_co_data["temperature_c"],
            "spec_co_humidity_pct": spec_co_data["humidity_pct"],
            "spec_co_adc_g": spec_co_data["adc_g"],
            "spec_co_adc_t": spec_co_data["adc_t"],
            "spec_co_adc_h": spec_co_data["adc_h"]
        })

        # Read SpecSensor NO2
        self.spec_no2.read_measurement()
        spec_no2_data = self.spec_no2.get_measurement_data()
        row.update({
            "spec_no2_sensor_sn": spec_no2_data["sensor_sn"],
            "spec_no2_ppb": spec_no2_data["gas_ppb"],
            "spec_no2_ppm": spec_no2_data["gas_ppm"],
            "spec_no2_temperature_c": spec_no2_data["temperature_c"],
            "spec_no2_humidity_pct": spec_no2_data["humidity_pct"],
            "spec_no2_adc_g": spec_no2_data["adc_g"],
            "spec_no2_adc_t": spec_no2_data["adc_t"],
            "spec_no2_adc_h": spec_no2_data["adc_h"]
        })

        # Read SpecSensor O3
        self.spec_o3.read_measurement()
        spec_o3_data = self.spec_o3.get_measurement_data()
        row.update({
            "spec_o3_sensor_sn": spec_o3_data["sensor_sn"],
            "spec_o3_ppb": spec_o3_data["gas_ppb"],
            "spec_o3_ppm": spec_o3_data["gas_ppm"],
            "spec_o3_temperature_c": spec_o3_data["temperature_c"],
            "spec_o3_humidity_pct": spec_o3_data["humidity_pct"],
            "spec_o3_adc_g": spec_o3_data["adc_g"],
            "spec_o3_adc_t": spec_o3_data["adc_t"],
            "spec_o3_adc_h": spec_o3_data["adc_h"]
        })

        return row

    def _write_buffer_to_csv(self):
        """Write buffered data to CSV file"""
        if not self.buffer:
            return

        try:
            with open(self.csv_file, 'a', newline='') as csvfile:
                fieldnames = list(self.buffer[0].keys())
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writerows(self.buffer)

            print(f"[{datetime.now().strftime('%H:%M:%S')}] Wrote {len(self.buffer)} samples to CSV")
            self.buffer.clear()
            self.last_write_time = time.time()
        except Exception as e:
            print(f"Error writing to CSV: {e}")

    def _print_status(self, row):
        """Print current sensor readings"""
        # GNSS data
        fix_status = row['gnss_fix_status'] if row['gnss_fix_status'] is not None else '?'
        lat_str = f"{row['gnss_lat']:.6f}" if row['gnss_lat'] is not None else 'N/A'
        lon_str = f"{row['gnss_lon']:.6f}" if row['gnss_lon'] is not None else 'N/A'
        speed_str = f"{row['gnss_speed']:.1f}" if row['gnss_speed'] is not None else 'N/A'
        pdop_str = f"{row['gnss_pdop']:.1f}" if row['gnss_pdop'] is not None else 'N/A'
        hdop_str = f"{row['gnss_hdop']:.1f}" if row['gnss_hdop'] is not None else 'N/A'
        vdop_str = f"{row['gnss_vdop']:.1f}" if row['gnss_vdop'] is not None else 'N/A'
        num_sv_str = f"{row['gnss_num_sv']}" if row['gnss_num_sv'] is not None else 'N/A'

        # SEN66 data
        pm25_str = f"{row['pm2p5']:.1f}" if row['pm2p5'] is not None else 'N/A'
        temp_str = f"{row['sen66_temperature']:.1f}" if row['sen66_temperature'] is not None else 'N/A'
        humid_str = f"{row['sen66_humidity']:.1f}" if row['sen66_humidity'] is not None else 'N/A'
        co2_str = f"{row['co2']:.0f}" if row['co2'] is not None else 'N/A'
        voc_str = f"{row['voc_index']:.0f}" if row['voc_index'] is not None else 'N/A'
        nox_str = f"{row['nox_index']:.0f}" if row['nox_index'] is not None else 'N/A'

        # SPEC sensor data
        co_str = f"{row['spec_co_ppm']:.3f}" if row['spec_co_ppm'] is not None else 'N/A'
        no2_str = f"{row['spec_no2_ppm']:.3f}" if row['spec_no2_ppm'] is not None else 'N/A'
        o3_str = f"{row['spec_o3_ppm']:.3f}" if row['spec_o3_ppm'] is not None else 'N/A'

        # Fan RPM data
        fan1_rpm_str = f"{row['fan1_rpm']:.0f}" if row['fan1_rpm'] is not None else 'N/A'
        fan2_rpm_str = f"{row['fan2_rpm']:.0f}" if row['fan2_rpm'] is not None else 'N/A'

        print(f"[{datetime.now().strftime('%H:%M:%S')}] "
              f"GPS:{fix_status} {lat_str}°,{lon_str}° {speed_str}kn SV:{num_sv_str} P/H/V:{pdop_str}/{hdop_str}/{vdop_str} | "
              f"T:{temp_str}°C RH:{humid_str}% PM2.5:{pm25_str} CO2:{co2_str} VOC:{voc_str} NOx:{nox_str} | "
              f"CO:{co_str} NO2:{no2_str} O3:{o3_str}ppm | "
              f"Fan:{fan1_rpm_str}/{fan2_rpm_str}RPM | "
              f"Buf:{len(self.buffer)}")

    def run(self):
        """Main logging loop"""
        print("Starting data collection...")
        print(f"Starting air sampling fans at {FAN_SPEED_PERCENT}%...")
        self.fans.set_group2_speed(FAN_SPEED_PERCENT)
        print("Press Ctrl+C to stop")
        print("=" * 80)

        try:
            while self.running:
                loop_start = time.time()

                # Collect data from all sensors
                row = self._collect_sensor_data()
                self.buffer.append(row)

                # Print status
                self._print_status(row)

                # Check if it's time to write to CSV
                if time.time() - self.last_write_time >= CSV_BUFFER_INTERVAL:
                    self._write_buffer_to_csv()

                # Maintain 1-second sampling rate
                elapsed = time.time() - loop_start
                sleep_time = max(0, SAMPLE_INTERVAL - elapsed)
                time.sleep(sleep_time)

        finally:
            print("\n" + "=" * 80)
            print("Stopping data collection...")

            # Write remaining buffer
            if self.buffer:
                print("Writing remaining buffered data...")
                self._write_buffer_to_csv()

            print("Shutdown complete.")
            print("=" * 80)
            self.cleanup()

    def cleanup(self):
        """Clean up sensor connections and stop fans"""
        try:
            print("Stopping air sampling fans...")
            self.fans.cleanup()

            # Clean up tachometers
            if self.tachometers:
                print("Stopping tachometer monitoring...")
                for tach in self.tachometers.values():
                    tach.cleanup()
                if self.gpio_chip is not None:
                    try:
                        lgpio.gpiochip_close(self.gpio_chip)
                    except:
                        pass

            print("Stopping sensors...")
            self.sen66.stop_measurement()
            self.sen66_transceiver.close()
            self.gnss.close()
        except Exception as e:
            print(f"Error during cleanup: {e}")


# ============================================================================
# Entry Point
# ============================================================================

if __name__ == "__main__":
    logger = MAQMLogger()
    logger.run()
