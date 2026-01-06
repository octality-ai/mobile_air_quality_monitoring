#!/usr/bin/env python3
"""
Read-Only Group 2 Tachometer Monitor
=====================================

Monitors RPM on Group 2 (air sampling) fans without controlling them.
Safe to run while thermal_fan_controller.py or other programs are controlling the fans.

Group 2 Tachometer Pins:
  - GPIO6 (Pin 31): Fan 1 tachometer (PWM controlled by GPIO13)
  - GPIO26 (Pin 37): Fan 2 tachometer (PWM controlled by GPIO19)

Usage:
    sudo /home/octa/.octa/bin/python3 read_group2_tachometer.py
"""

import time
import signal
import sys
from threading import Lock, Thread, Event

try:
    import lgpio
except ImportError:
    print("ERROR: lgpio not installed.")
    print("Install with: sudo pip3 install lgpio")
    sys.exit(1)


class TachometerReader:
    """Read-only tachometer reader for a single fan."""

    def __init__(self, gpio_chip, gpio_pin, pulses_per_rev=2):
        """
        Initialize tachometer reader.

        Args:
            gpio_chip: lgpio chip handle
            gpio_pin: GPIO pin number for tachometer input
            pulses_per_rev: Pulses per revolution (default: 2 for PC fans)
        """
        self.chip = gpio_chip
        self.pin = gpio_pin
        self.pulses_per_rev = pulses_per_rev
        self.pulse_count = 0
        self.last_count = 0
        self.last_time = time.time()
        self.last_state = 1  # Start assuming high (pull-up)
        self.rpm = 0
        self.lock = Lock()
        self.stop_event = Event()

        # Configure GPIO as input with pull-up
        lgpio.gpio_claim_input(self.chip, self.pin, lgpio.SET_PULL_UP)

        # Initialize with current state
        self.last_state = lgpio.gpio_read(self.chip, self.pin)

        # Start background sampling thread
        self.sample_thread = Thread(target=self._sample_loop, daemon=True)
        self.sample_thread.start()

    def _sample_loop(self):
        """Background thread that continuously samples GPIO for edge detection."""
        while not self.stop_event.is_set():
            try:
                current_state = lgpio.gpio_read(self.chip, self.pin)

                # Detect rising edge (0 -> 1 transition)
                if current_state == 1 and self.last_state == 0:
                    with self.lock:
                        self.pulse_count += 1

                self.last_state = current_state

                # Sample at ~1ms intervals (1000 Hz) to catch edges reliably
                time.sleep(0.001)
            except:
                # Handle any GPIO read errors gracefully
                pass

    def update_rpm(self):
        """
        Update RPM calculation based on pulse count.

        Returns:
            float: Current RPM
        """
        current_time = time.time()

        with self.lock:
            current_count = self.pulse_count

        # Calculate time elapsed and pulses received
        time_delta = current_time - self.last_time
        pulses = current_count - self.last_count

        if time_delta > 0:
            # Calculate RPM: (pulses/sec * 60 sec/min) / pulses_per_rev
            pulses_per_sec = pulses / time_delta
            self.rpm = (pulses_per_sec * 60) / self.pulses_per_rev
        else:
            self.rpm = 0

        # Update last values
        self.last_count = current_count
        self.last_time = current_time

        return self.rpm

    def get_rpm(self):
        """Get current RPM value."""
        return self.rpm

    def cleanup(self):
        """Clean up GPIO resources and stop background thread."""
        self.stop_event.set()
        if self.sample_thread.is_alive():
            self.sample_thread.join(timeout=1.0)
        try:
            lgpio.gpio_free(self.chip, self.pin)
        except:
            pass


class Group2TachMonitor:
    """Read-only monitor for Group 2 fan tachometers."""

    def __init__(self):
        """Initialize tachometer monitoring for Group 2 fans."""
        self.gpio_chip = None
        self.tachometers = {}

        # Group 2 tachometer pins
        self.tach_pins = {
            13: 6,   # GPIO13 PWM → GPIO6 Tach (Fan 1)
            19: 26   # GPIO19 PWM → GPIO26 Tach (Fan 2)
        }

        # Open GPIO chip
        try:
            self.gpio_chip = lgpio.gpiochip_open(0)
        except Exception as e:
            print(f"ERROR: Failed to open GPIO chip: {e}")
            sys.exit(1)

        # Initialize tachometers
        for pwm_gpio, tach_gpio in self.tach_pins.items():
            try:
                tach = TachometerReader(self.gpio_chip, tach_gpio)
                self.tachometers[pwm_gpio] = tach
                print(f"Initialized tachometer on GPIO{tach_gpio} (monitors fan on GPIO{pwm_gpio})")
            except Exception as e:
                print(f"WARNING: Failed to initialize tachometer for GPIO{tach_gpio}: {e}")

        if not self.tachometers:
            print("ERROR: No tachometers initialized!")
            sys.exit(1)

    def read_rpm(self):
        """
        Read current RPM from all Group 2 fans.

        Returns:
            dict: {pwm_gpio: rpm}
        """
        rpms = {}
        for pwm_gpio, tach in self.tachometers.items():
            rpms[pwm_gpio] = tach.update_rpm()
        return rpms

    def cleanup(self):
        """Clean up resources."""
        for tach in self.tachometers.values():
            tach.cleanup()
        if self.gpio_chip is not None:
            try:
                lgpio.gpiochip_close(self.gpio_chip)
                self.gpio_chip = None
            except:
                pass


def main():
    """Monitor Group 2 tachometers and display RPM continuously."""
    print("=" * 70)
    print("Group 2 Fan Tachometer Monitor (Read-Only)")
    print("=" * 70)
    print("\nMonitoring Group 2 (air sampling) fans:")
    print("  Fan 1: GPIO13 (Pin 33) PWM → GPIO6 (Pin 31) Tach")
    print("  Fan 2: GPIO19 (Pin 35) PWM → GPIO26 (Pin 37) Tach")
    print("\nPress Ctrl+C to stop\n")

    monitor = Group2TachMonitor()

    def signal_handler(signum, _frame):
        """Handle Ctrl+C gracefully."""
        print("\n\nStopping monitor...")
        monitor.cleanup()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Display header
        print(f"{'Time':<10} {'GPIO13 RPM':>12} {'GPIO19 RPM':>12}")
        print("-" * 70)

        while True:
            # Read RPM values
            rpms = monitor.read_rpm()

            gpio13_rpm = rpms.get(13, 0)
            gpio19_rpm = rpms.get(19, 0)

            # Display current time and RPM
            current_time = time.strftime("%H:%M:%S")
            print(f"{current_time:<10} {gpio13_rpm:12.0f} {gpio19_rpm:12.0f}", flush=True)

            time.sleep(1)  # Update every second

    except KeyboardInterrupt:
        print("\n\nMonitor stopped by user")
    finally:
        monitor.cleanup()


if __name__ == "__main__":
    main()
