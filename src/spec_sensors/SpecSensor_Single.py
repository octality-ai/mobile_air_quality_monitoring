import serial

PORT = "/dev/ttyAMA1"   # Pi 5 primary UART
BAUDRATE = 9600

def get_single_measurement():
    with serial.Serial(PORT, BAUDRATE, timeout=2) as ser:
        # flush any old data
        ser.reset_input_buffer()

        # send carriage return to trigger single-shot read
        ser.write(b'\r')

        # read one response line
        line = ser.readline().decode(errors="ignore").strip()
        return line

def parse_measurement(line: str):
    """
    Parse measurement string from DGS2-970.
    Format: SN, PPB, TEMP, RH, ADC_G, ADC_T, ADC_H
    """
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

    # Convert scaled values
    concentration_ppm = ppb / 1000.0    # 1000 ppb = 1 ppm
    temperature_c = temp_raw / 100.0    # scaled by 100
    humidity_pct = rh_raw / 100.0       # scaled by 100

    return {
        "Sensor SN": sn,
        "Gas Concentration (ppb)": ppb,
        "Gas Concentration (ppm)": concentration_ppm,
        "Temperature (°C)": temperature_c,
        "Relative Humidity (%)": humidity_pct,
        "ADC_G": adc_g,
        "ADC_T": adc_t,
        "ADC_H": adc_h,
    }

if __name__ == "__main__":
    line = get_single_measurement()
    if not line:
        print("No response received. Check wiring and sensor power.")
    else:
        print("Raw response:", line)
        parsed = parse_measurement(line)
        if parsed:
            print("\nDecoded values:")
            for k, v in parsed.items():
                print(f"  {k}: {v}")
        else:
            print("Could not parse response.")
