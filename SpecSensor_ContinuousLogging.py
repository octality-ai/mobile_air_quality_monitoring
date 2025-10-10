import serial
import csv
import time
from datetime import datetime

PORT = "/dev/ttyAMA1"
BAUDRATE = 9600
BUFFER_WRITE_INTERVAL = 600  # 10 minutes in seconds

# Create CSV filename with current date and time
CSV_FILE = f"sensor_measurements_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

def get_single_measurement():
    with serial.Serial(PORT, BAUDRATE, timeout=2) as ser:
        ser.reset_input_buffer()
        ser.write(b'\r')
        line = ser.readline().decode(errors="ignore").strip()
        return line

def parse_measurement(line: str):
    fields = [f.strip() for f in line.split(",")]
    if len(fields) < 7:
        return None

    sn = fields[0]
    ppb = int(fields[1])
    temp_raw = int(fields[2])
    rh_raw = int(fields[3])
    adc_g = int(fields[4])
    adc_t = int(fields[5])
    adc_h = int(fields[6])

    concentration_ppm = ppb / 1000.0
    temperature_c = temp_raw / 100.0
    humidity_pct = rh_raw / 100.0

    return {
        "timestamp": datetime.now().isoformat(),
        "sensor_sn": sn,
        "gas_ppb": ppb,
        "gas_ppm": concentration_ppm,
        "temperature_c": temperature_c,
        "humidity_pct": humidity_pct,
        "adc_g": adc_g,
        "adc_t": adc_t,
        "adc_h": adc_h,
    }

# Global buffer to store measurements in memory
measurement_buffer = []
last_write_time = time.time()

def initialize_csv():
    with open(CSV_FILE, 'w', newline='') as csvfile:
        fieldnames = ["timestamp", "sensor_sn", "gas_ppb", "gas_ppm",
                     "temperature_c", "humidity_pct", "adc_g", "adc_t", "adc_h"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

def write_buffer_to_csv():
    """Write all buffered measurements to CSV file."""
    global measurement_buffer, last_write_time

    if not measurement_buffer:
        return

    try:
        with open(CSV_FILE, 'a', newline='') as csvfile:
            fieldnames = ["timestamp", "sensor_sn", "gas_ppb", "gas_ppm",
                         "temperature_c", "humidity_pct", "adc_g", "adc_t", "adc_h"]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writerows(measurement_buffer)

        print(f"Wrote {len(measurement_buffer)} measurements to CSV")
        measurement_buffer.clear()
        last_write_time = time.time()
    except Exception as e:
        print(f"Error writing to CSV: {e}")

def log_measurement():
    global measurement_buffer, last_write_time

    try:
        line = get_single_measurement()
        if line:
            parsed = parse_measurement(line)
            if parsed:
                # Add to buffer instead of writing directly
                measurement_buffer.append(parsed)
                print(f"Buffered: {parsed['gas_ppm']:.3f} ppm, {parsed['temperature_c']:.1f}°C (Buffer: {len(measurement_buffer)}")

                # Check if it's time to write buffer to CSV
                current_time = time.time()
                if current_time - last_write_time >= BUFFER_WRITE_INTERVAL:
                    write_buffer_to_csv()

                return True
            else:
                print("Failed to parse measurement")
        else:
            print("No response from sensor")
        return False
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    print("Starting continuous sensor logging...")
    print(f"Data will be saved to: {CSV_FILE}")
    print("Press Ctrl+C to stop")

    initialize_csv()

    try:
        while True:
            log_measurement()
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nLogging stopped.")
        # Write any remaining buffered measurements before exiting
        if measurement_buffer:
            print("Writing remaining buffered measurements...")
            write_buffer_to_csv()