#!/usr/bin/env python3
"""
Dual-Group PWM Fan Controller for Raspberry Pi 5
================================================

Controls two independent groups of PWM fans:
- Group 1 (Heat Sink): GPIO12 + GPIO18
- Group 2 (Air Sampling): GPIO13 + GPIO19

Hardware Connections:
Group 1 - Heat Sink Fans:
  - Fan 1: GPIO12 (Physical Pin 32) - PWM control
  - Fan 2: GPIO18 (Physical Pin 12) - PWM control

Group 2 - Air Sampling Fans:
  - Fan 3: GPIO13 (Physical Pin 33) - PWM control
  - Fan 4: GPIO19 (Physical Pin 35) - PWM control

All fans should have:
  - Yellow wire: +5V power supply
  - Black wire: Common ground (5V supply GND + Pi GND)
  - Blue wire: GPIO PWM control
  - (Green wire: Tachometer - optional, not used here)

PWM Specifications:
- Frequency: 25 kHz (standard for PC PWM fans)
- NORMAL LOGIC: HIGH = fan runs, LOW = fan stopped
"""

import time
import signal
import sys
import atexit
import subprocess

try:
    from rpi_hardware_pwm import HardwarePWM
    HARDWARE_PWM_AVAILABLE = True
except ImportError:
    HARDWARE_PWM_AVAILABLE = False
    print("ERROR: rpi-hardware-pwm not installed.")
    print("Install with: sudo pip3 install rpi-hardware-pwm")
    sys.exit(1)


class DualFanController:
    """Controller for two independent groups of PWM fans."""

    # GPIO to PWM channel and chip mapping (Pi 5)
    # All 4 GPIOs use PWM chip 0 with different channels
    PWM_CONFIG = {
        12: {'chip': 0, 'channel': 0},  # GPIO12 = PWM0_CHAN0
        13: {'chip': 0, 'channel': 1},  # GPIO13 = PWM0_CHAN1
        18: {'chip': 0, 'channel': 2},  # GPIO18 = PWM0_CHAN2
        19: {'chip': 0, 'channel': 3}   # GPIO19 = PWM0_CHAN3
    }

    # Fan groups
    GROUP1_GPIOS = [12, 18]  # Heat sink fans
    GROUP2_GPIOS = [13, 19]  # Air sampling fans

    DEFAULT_FREQUENCY = 25000  # 25 kHz

    def __init__(self, frequency=None):
        """
        Initialize dual-group fan controller.

        Args:
            frequency: PWM frequency in Hz (default: 25000)
        """
        self.frequency = frequency or self.DEFAULT_FREQUENCY
        self.pwm_channels = {}
        self.current_speeds = {}

        # Initialize all 4 PWM channels
        for gpio in self.GROUP1_GPIOS + self.GROUP2_GPIOS:
            self._init_pwm(gpio)

        # Register cleanup handlers
        atexit.register(self._emergency_stop)
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

        print("Dual-group fan controller initialized:")
        print(f"  Group 1 (Heat Sink):   GPIO{self.GROUP1_GPIOS[0]}, GPIO{self.GROUP1_GPIOS[1]}")
        print(f"  Group 2 (Air Sampling): GPIO{self.GROUP2_GPIOS[0]}, GPIO{self.GROUP2_GPIOS[1]}")
        print(f"  PWM Frequency: {self.frequency} Hz")

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

    def set_group1_speed(self, percent):
        """
        Set speed for Group 1 (Heat Sink fans - GPIO12, GPIO18).

        Args:
            percent: Speed percentage 0-100
        """
        self._set_group_speed(self.GROUP1_GPIOS, percent)

    def set_group2_speed(self, percent):
        """
        Set speed for Group 2 (Air Sampling fans - GPIO13, GPIO19).

        Args:
            percent: Speed percentage 0-100
        """
        self._set_group_speed(self.GROUP2_GPIOS, percent)

    def _set_group_speed(self, gpios, percent):
        """Set speed for a group of fans."""
        if not 0 <= percent <= 100:
            raise ValueError(f"Percent must be between 0 and 100, got {percent}")

        duty_cycle = percent / 100.0

        for gpio in gpios:
            self.pwm_channels[gpio].change_duty_cycle(percent)
            self.current_speeds[gpio] = duty_cycle

    def get_group1_speed(self):
        """Get current speed of Group 1 as percentage."""
        return self.current_speeds[self.GROUP1_GPIOS[0]] * 100

    def get_group2_speed(self):
        """Get current speed of Group 2 as percentage."""
        return self.current_speeds[self.GROUP2_GPIOS[0]] * 100

    def stop_all(self):
        """Stop all fans."""
        self.set_group1_speed(0)
        self.set_group2_speed(0)

    def _emergency_stop(self):
        """Emergency stop - set all GPIOs LOW."""
        try:
            for gpio in self.GROUP1_GPIOS + self.GROUP2_GPIOS:
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
    Demo program showing independent control of both fan groups.
    """
    print("=" * 60)
    print("Dual-Group Fan Controller Demo")
    print("=" * 60)

    with DualFanController() as fans:
        try:
            print("\nTesting Group 1 (Heat Sink fans - GPIO12, GPIO18)...")
            for speed in [0, 30, 60, 100]:
                print(f"  Setting Group 1 to {speed}%...")
                fans.set_group1_speed(speed)
                time.sleep(2)

            print("\nTesting Group 2 (Air Sampling fans - GPIO13, GPIO19)...")
            for speed in [0, 30, 60, 100]:
                print(f"  Setting Group 2 to {speed}%...")
                fans.set_group2_speed(speed)
                time.sleep(2)

            print("\nTesting both groups together...")
            print("  Group 1: 50%, Group 2: 75%")
            fans.set_group1_speed(50)
            fans.set_group2_speed(75)
            time.sleep(3)

            print(f"\nCurrent speeds:")
            print(f"  Group 1: {fans.get_group1_speed():.1f}%")
            print(f"  Group 2: {fans.get_group2_speed():.1f}%")

            print("\nStopping all fans...")
            fans.stop_all()

            print("\nDemo complete!")

        except KeyboardInterrupt:
            print("\n\nCtrl+C detected, stopping fans...")


if __name__ == "__main__":
    main()
