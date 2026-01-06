#!/usr/bin/env python3
"""
Dual-Group PWM Fan Controller with Tachometer Reading for Raspberry Pi 5
=========================================================================

Controls two independent groups of PWM fans with RPM monitoring:
- Group 1 (Heat Sink): GPIO12 + GPIO18 (PWM) with GPIO16 + GPIO23 (Tach)
- Group 2 (Air Sampling): GPIO13 + GPIO19 (PWM) with GPIO6 + GPIO26 (Tach)

Hardware Connections (4-pin PWM fans):
======================================

Group 1 - Heat Sink Fans:
  Fan 1 (GPIO18): Pin 12 (PWM) + Pin 16 (Tach GPIO23) - Adjacent even pins
  Fan 2 (GPIO12): Pin 32 (PWM) + Pin 36 (Tach GPIO16) - Adjacent even pins

Group 2 - Air Sampling Fans:
  Fan 1 (GPIO13): Pin 33 (PWM) + Pin 31 (Tach GPIO6)  - Adjacent odd pins
  Fan 2 (GPIO19): Pin 35 (PWM) + Pin 37 (Tach GPIO26) - Adjacent odd pins

4-Pin Fan Wiring:
  - Yellow wire: +5V power supply
  - Black wire: Common ground (5V supply GND + Pi GND)
  - Blue wire: GPIO PWM control (25 kHz)
  - Green wire: Tachometer output (connect to adjacent GPIO with pull-up)

Tachometer Specifications:
  - Output: 2 pulses per revolution (open-collector)
  - Pull-up: Internal pull-up resistor enabled on GPIO
  - RPM calculation: RPM = (pulses_per_second × 60) / 2
  - Frequency range: ~25 Hz (1500 RPM) to ~200 Hz (12000 RPM)
"""

import time
import signal
import sys
import atexit
import subprocess
from threading import Lock, Thread, Event

try:
    from rpi_hardware_pwm import HardwarePWM
    HARDWARE_PWM_AVAILABLE = True
except ImportError:
    HARDWARE_PWM_AVAILABLE = False
    print("ERROR: rpi-hardware-pwm not installed.")
    print("Install with: sudo pip3 install rpi-hardware-pwm")
    sys.exit(1)

try:
    import lgpio
    LGPIO_AVAILABLE = True
except ImportError:
    LGPIO_AVAILABLE = False
    print("WARNING: lgpio not installed. Tachometer reading disabled.")
    print("Install with: sudo pip3 install lgpio")


class FanTachometer:
    """Tachometer reader for a single fan using lgpio with background sampling thread."""

    def __init__(self, gpio_chip, gpio_pin, pulses_per_rev=2):
        """
        Initialize tachometer reader with background thread.

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
        Call this periodically (e.g., every 1 second).

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


class DualFanControllerWithTach:
    """
    Controller for two independent groups of PWM fans with tachometer reading.
    """

    # GPIO to PWM channel and chip mapping (Pi 5)
    PWM_CONFIG = {
        12: {'chip': 0, 'channel': 0},  # GPIO12 = PWM0_CHAN0
        13: {'chip': 0, 'channel': 1},  # GPIO13 = PWM0_CHAN1
        18: {'chip': 0, 'channel': 2},  # GPIO18 = PWM0_CHAN2
        19: {'chip': 0, 'channel': 3}   # GPIO19 = PWM0_CHAN3
    }

    # Fan configurations: {PWM_GPIO: TACH_GPIO}
    GROUP1_FANS = {
        18: 23,  # GPIO18 (Pin 12) PWM → GPIO23 (Pin 16) Tach
        12: 16   # GPIO12 (Pin 32) PWM → GPIO16 (Pin 36) Tach
    }

    GROUP2_FANS = {
        13: 6,   # GPIO13 (Pin 33) PWM → GPIO6 (Pin 31) Tach
        19: 26   # GPIO19 (Pin 35) PWM → GPIO26 (Pin 37) Tach
    }

    DEFAULT_FREQUENCY = 25000  # 25 kHz

    def __init__(self, frequency=None, enable_tach=True):
        """
        Initialize dual-group fan controller with tachometer reading.

        Args:
            frequency: PWM frequency in Hz (default: 25000)
            enable_tach: Enable tachometer reading (default: True)
        """
        self.frequency = frequency or self.DEFAULT_FREQUENCY
        self.enable_tach = enable_tach and LGPIO_AVAILABLE
        self.pwm_channels = {}
        self.current_speeds = {}
        self.tachometers = {}
        self.gpio_chip = None

        # Initialize lgpio chip for tachometer reading
        if self.enable_tach:
            try:
                self.gpio_chip = lgpio.gpiochip_open(0)
            except Exception as e:
                print(f"WARNING: Failed to open GPIO chip: {e}")
                self.enable_tach = False

        # Initialize all PWM channels and tachometers
        for pwm_gpio, tach_gpio in {**self.GROUP1_FANS, **self.GROUP2_FANS}.items():
            self._init_pwm(pwm_gpio)
            if self.enable_tach:
                self._init_tach(pwm_gpio, tach_gpio)

        # Register cleanup handlers
        atexit.register(self._emergency_stop)
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

        print("Dual-group fan controller with tachometer initialized:")
        print(f"  Group 1 (Heat Sink):")
        print(f"    Fan 1: GPIO18 (Pin 12) PWM → GPIO23 (Pin 16) Tach")
        print(f"    Fan 2: GPIO12 (Pin 32) PWM → GPIO16 (Pin 36) Tach")
        print(f"  Group 2 (Air Sampling):")
        print(f"    Fan 1: GPIO13 (Pin 33) PWM → GPIO6 (Pin 31) Tach")
        print(f"    Fan 2: GPIO19 (Pin 35) PWM → GPIO26 (Pin 37) Tach")
        print(f"  PWM Frequency: {self.frequency} Hz")
        print(f"  Tachometer: {'Enabled' if self.enable_tach else 'Disabled'}")

    def _init_pwm(self, gpio):
        """Initialize a single PWM channel."""
        if gpio not in self.PWM_CONFIG:
            raise ValueError(f"GPIO{gpio} does not support hardware PWM")

        # Configure GPIO for PWM with correct ALT function
        # GPIO12/13 use ALT0, GPIO18/19 use ALT3
        alt_function = 'a0' if gpio in [12, 13] else 'a3'
        subprocess.run(['sudo', 'pinctrl', 'set', str(gpio), 'op', alt_function],
                      check=False, capture_output=True)

        # Initialize hardware PWM with correct chip and channel
        config = self.PWM_CONFIG[gpio]
        pwm = HardwarePWM(pwm_channel=config['channel'], hz=self.frequency, chip=config['chip'])
        pwm.start(0)  # Start at 0% (stopped)

        self.pwm_channels[gpio] = pwm
        self.current_speeds[gpio] = 0.0

    def _init_tach(self, pwm_gpio, tach_gpio):
        """Initialize tachometer for a fan."""
        try:
            tach = FanTachometer(self.gpio_chip, tach_gpio)
            self.tachometers[pwm_gpio] = tach
        except Exception as e:
            print(f"WARNING: Failed to initialize tachometer for GPIO{pwm_gpio}: {e}")

    def set_group1_speed(self, percent):
        """
        Set speed for Group 1 (Heat Sink fans - GPIO12, GPIO18).

        Args:
            percent: Speed percentage 0-100
        """
        self._set_group_speed(self.GROUP1_FANS.keys(), percent)

    def set_group2_speed(self, percent):
        """
        Set speed for Group 2 (Air Sampling fans - GPIO13, GPIO19).

        Args:
            percent: Speed percentage 0-100
        """
        self._set_group_speed(self.GROUP2_FANS.keys(), percent)

    def _set_group_speed(self, gpios, percent):
        """Set speed for a group of fans."""
        if not 0 <= percent <= 100:
            raise ValueError(f"Percent must be between 0 and 100, got {percent}")

        for gpio in gpios:
            self.pwm_channels[gpio].change_duty_cycle(percent)
            self.current_speeds[gpio] = percent / 100.0

    def update_tachometers(self):
        """
        Update all tachometer RPM readings.
        Call this periodically (e.g., every 1 second) to update RPM values.

        Background threads continuously monitor GPIO pins for edge detection,
        so this method just needs to calculate RPM from accumulated pulse counts.

        Returns:
            dict: {gpio: rpm} for all fans
        """
        if not self.enable_tach:
            return {}

        rpms = {}
        for pwm_gpio, tach in self.tachometers.items():
            # Update RPM calculation (edge detection happens in background thread)
            rpm = tach.update_rpm()
            rpms[pwm_gpio] = rpm

        return rpms

    def get_group1_rpm(self):
        """
        Get RPM for Group 1 fans.

        Returns:
            dict: {gpio: rpm} for Group 1 fans
        """
        if not self.enable_tach:
            return {gpio: 0 for gpio in self.GROUP1_FANS.keys()}

        return {gpio: self.tachometers[gpio].get_rpm()
                for gpio in self.GROUP1_FANS.keys()
                if gpio in self.tachometers}

    def get_group2_rpm(self):
        """
        Get RPM for Group 2 fans.

        Returns:
            dict: {gpio: rpm} for Group 2 fans
        """
        if not self.enable_tach:
            return {gpio: 0 for gpio in self.GROUP2_FANS.keys()}

        return {gpio: self.tachometers[gpio].get_rpm()
                for gpio in self.GROUP2_FANS.keys()
                if gpio in self.tachometers}

    def get_group1_speed(self):
        """Get current speed of Group 1 as percentage."""
        return self.current_speeds[list(self.GROUP1_FANS.keys())[0]] * 100

    def get_group2_speed(self):
        """Get current speed of Group 2 as percentage."""
        return self.current_speeds[list(self.GROUP2_FANS.keys())[0]] * 100

    def stop_all(self):
        """Stop all fans."""
        self.set_group1_speed(0)
        self.set_group2_speed(0)

    def _emergency_stop(self):
        """Emergency stop - set all GPIOs LOW."""
        try:
            for gpio in list(self.GROUP1_FANS.keys()) + list(self.GROUP2_FANS.keys()):
                subprocess.run(['sudo', 'pinctrl', 'set', str(gpio), 'op', 'dl'],
                              check=False, capture_output=True, timeout=1)
        except:
            pass

    def _signal_handler(self, signum, _):
        """Handle SIGTERM and SIGINT."""
        print(f"\nReceived signal {signum}, stopping all fans...")
        self.cleanup()
        sys.exit(0)

    def cleanup(self):
        """Clean up and stop all fans."""
        print("\nCleaning up fan controller...")
        self.stop_all()
        time.sleep(0.5)

        # Clean up tachometers
        if self.enable_tach:
            for tach in self.tachometers.values():
                tach.cleanup()
            if self.gpio_chip is not None:
                lgpio.gpiochip_close(self.gpio_chip)

        # Stop all PWM channels and set GPIOs LOW
        for gpio, pwm in self.pwm_channels.items():
            pwm.stop()
            subprocess.run(['sudo', 'pinctrl', 'set', str(gpio), 'op', 'dl'],
                          check=False, capture_output=True)

        print("All fans stopped")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.cleanup()


def main():
    """
    Demo program showing fan control with RPM monitoring.
    """
    print("=" * 70)
    print("Dual-Group Fan Controller with Tachometer Demo")
    print("=" * 70)

    with DualFanControllerWithTach(enable_tach=True) as fans:
        try:
            print("\nTesting Group 2 (Air Sampling fans - Priority)...")
            print("Setting Group 2 to various speeds and monitoring RPM...\n")

            for speed in [30, 50, 75, 100]:
                print(f"Setting Group 2 to {speed}%...")
                fans.set_group2_speed(speed)
                time.sleep(3)  # Wait for fans to stabilize

                # Update and display RPM
                fans.update_tachometers()
                group2_rpm = fans.get_group2_rpm()

                print(f"  GPIO13 (Pin 33): {group2_rpm.get(13, 0):.0f} RPM")
                print(f"  GPIO19 (Pin 35): {group2_rpm.get(19, 0):.0f} RPM")
                print()

            print("\nTesting Group 1 (Heat Sink fans - Optional)...")
            print("Setting Group 1 to various speeds and monitoring RPM...\n")

            for speed in [30, 50, 75, 100]:
                print(f"Setting Group 1 to {speed}%...")
                fans.set_group1_speed(speed)
                time.sleep(3)  # Wait for fans to stabilize

                # Update and display RPM
                fans.update_tachometers()
                group1_rpm = fans.get_group1_rpm()

                print(f"  GPIO18 (Pin 12): {group1_rpm.get(18, 0):.0f} RPM")
                print(f"  GPIO12 (Pin 32): {group1_rpm.get(12, 0):.0f} RPM")
                print()

            print("\nContinuous monitoring for 10 seconds...")
            fans.set_group1_speed(50)
            fans.set_group2_speed(75)

            for i in range(10):
                fans.update_tachometers()
                g1_rpm = fans.get_group1_rpm()
                g2_rpm = fans.get_group2_rpm()

                print(f"[{i+1:2d}s] G1: GPIO18={g1_rpm.get(18,0):4.0f} GPIO12={g1_rpm.get(12,0):4.0f} | "
                      f"G2: GPIO13={g2_rpm.get(13,0):4.0f} GPIO19={g2_rpm.get(19,0):4.0f} RPM")
                time.sleep(1)

            print("\nStopping all fans...")
            fans.stop_all()
            time.sleep(2)

            # Verify fans stopped
            fans.update_tachometers()
            g1_rpm = fans.get_group1_rpm()
            g2_rpm = fans.get_group2_rpm()
            print(f"Final RPM check: G1={list(g1_rpm.values())}, G2={list(g2_rpm.values())}")

            print("\nDemo complete!")

        except KeyboardInterrupt:
            print("\n\nCtrl+C detected, stopping fans...")


if __name__ == "__main__":
    main()
