#!/usr/bin/env python3
"""
4-Wire Fan Controller for Raspberry Pi 5
=========================================

Controls a 4-wire PWM fan with speed control and tachometer feedback.
Designed for Noctua NF-A4x10 5V PWM fan.

Hardware Connections:
- Yellow wire: +5V power supply
- Black wire:  Common ground (5V supply GND + Pi GND)
- Blue wire:   GPIO12 (Physical Pin 32) - PWM control
- Green wire:  GPIO23 (Physical Pin 16) - Tachometer feedback

PWM Specifications (Noctua NF-A4x10 5V PWM):
- Frequency: 25 kHz (standard for PC PWM fans)
- Duty Cycle: 0-100% (0% = stopped, 100% = full speed)
- NORMAL LOGIC: HIGH signal = fan runs, LOW signal = fan stops
- Speed Range: 0-4500 RPM (typical)

Tachometer:
- Noctua fans output 2 pulses per revolution
- RPM calculated from pulse frequency
- Open-collector output, requires pull-up resistor

System-Level GPIO Safety:
- Install fan-gpio-init.service to ensure GPIO12 is LOW at boot/shutdown
- See FAN_GPIO_SETUP.md for installation instructions

Reference: https://www.noctua.at/en/products/nf-a4x10-5v-pwm
"""

import time
import threading
import signal
import sys
import atexit
from gpiozero import DigitalInputDevice

try:
    from rpi_hardware_pwm import HardwarePWM
    HARDWARE_PWM_AVAILABLE = True
except ImportError:
    HARDWARE_PWM_AVAILABLE = False
    print("Warning: rpi-hardware-pwm not installed. Install with: sudo pip3 install rpi-hardware-pwm")
    print("Falling back to software PWM (max 10 kHz)")
    from gpiozero import PWMOutputDevice


class FanController:
    """Controller for 4-wire PWM fan with tachometer feedback."""

    # Pin configuration
    PWM_PIN = 12        # GPIO12 (Physical Pin 32) - Hardware PWM
    TACH_PIN = 23       # GPIO23 (Physical Pin 16) - Tachometer input

    # PWM configuration
    DEFAULT_FREQUENCY = 25000  # 25 kHz (standard for PC PWM fans)

    # Hardware PWM channel mapping for Pi 5
    # GPIO12 = PWM channel 0, GPIO13 = channel 1
    # GPIO18 = PWM channel 2, GPIO19 = channel 3
    PWM_CHANNEL_MAP = {12: 0, 13: 1, 18: 2, 19: 3}

    # Tachometer configuration
    PULSES_PER_REVOLUTION = 2  # Noctua fans use 2 pulses per revolution

    def __init__(self, pwm_pin=None, tach_pin=None, frequency=None):
        """
        Initialize fan controller with PWM and tachometer.

        Args:
            pwm_pin: GPIO pin for PWM output (default: 12)
            tach_pin: GPIO pin for tachometer input (default: 23)
            frequency: PWM frequency in Hz (default: 25000)
        """
        self.pwm_pin = pwm_pin or self.PWM_PIN
        self.tach_pin = tach_pin or self.TACH_PIN
        self.frequency = frequency or self.DEFAULT_FREQUENCY
        self.use_hardware_pwm = HARDWARE_PWM_AVAILABLE

        # Initialize PWM output
        # NOTE: This fan uses NORMAL logic - HIGH = running, LOW = stopped
        if self.use_hardware_pwm:
            # Use hardware PWM for high frequencies (25 kHz)
            if self.pwm_pin not in self.PWM_CHANNEL_MAP:
                raise ValueError(f"GPIO{self.pwm_pin} does not support hardware PWM. Use GPIO 12, 13, 18, or 19.")

            # Configure GPIO pin for PWM function (ALT0)
            import subprocess
            subprocess.run(['sudo', 'pinctrl', 'set', str(self.pwm_pin), 'op', 'a0'],
                          check=False, capture_output=True)

            pwm_channel = self.PWM_CHANNEL_MAP[self.pwm_pin]
            self.fan_pwm = HardwarePWM(pwm_channel=pwm_channel, hz=self.frequency, chip=0)
            # Start at 0% duty (fan stopped)
            self.fan_pwm.start(0)
            self._current_duty = 0.0  # Track our duty cycle (0=stopped, 1=full speed)
        else:
            # Fallback to software PWM (max 10 kHz)
            if self.frequency > 10000:
                print(f"Warning: Frequency {self.frequency} Hz exceeds software PWM limit.")
                print("Reducing to 10000 Hz. Install rpi-hardware-pwm for higher frequencies.")
                self.frequency = 10000

            from gpiozero import PWMOutputDevice
            self.fan_pwm = PWMOutputDevice(
                self.pwm_pin,
                frequency=self.frequency,
                initial_value=0,      # Start at 0% duty (fan stopped)
                active_high=True      # NORMAL: HIGH=run, LOW=stop
            )
            self._current_duty = 0.0

        # Initialize tachometer input with pull-up resistor
        self.tach_input = DigitalInputDevice(
            self.tach_pin,
            pull_up=True,
            bounce_time=0.001  # 1ms debounce
        )

        # Tachometer measurement variables
        self._tach_pulses = 0
        self._last_pulse_time = time.time()
        self._rpm_lock = threading.Lock()
        self._current_rpm = 0.0
        self._rpm_update_thread = None
        self._running = False

        # Set up interrupt for tachometer edges (falling edge for open-collector)
        self.tach_input.when_deactivated = self._tach_pulse_callback

        pwm_mode = "Hardware PWM" if self.use_hardware_pwm else "Software PWM"
        print(f"Fan controller initialized:")
        print(f"  PWM Mode: {pwm_mode}")
        print(f"  PWM Pin: GPIO{self.pwm_pin} (Physical Pin 32)")
        print(f"  PWM Frequency: {self.frequency} Hz")
        print(f"  Tachometer Pin: GPIO{self.tach_pin} (Physical Pin 16)")
        print(f"  Pulses per revolution: {self.PULSES_PER_REVOLUTION}")
        print(f"  Fan Model: Noctua NF-A4x10 5V PWM")

        # Register cleanup handlers for safety
        atexit.register(self._emergency_stop)
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

    def _tach_pulse_callback(self):
        """Internal callback for tachometer pulse counting."""
        current_time = time.time()

        with self._rpm_lock:
            self._tach_pulses += 1

            # Calculate instantaneous RPM from time between pulses
            time_diff = current_time - self._last_pulse_time
            if time_diff > 0:
                # Calculate RPM from pulse period
                pulses_per_second = 1.0 / time_diff
                rpm = (pulses_per_second * 60) / self.PULSES_PER_REVOLUTION

                # Simple moving average filter (smoothing)
                self._current_rpm = self._current_rpm * 0.7 + rpm * 0.3

            self._last_pulse_time = current_time

    def set_speed(self, duty_cycle):
        """
        Set fan speed via PWM duty cycle.

        NOTE: This fan uses NORMAL logic:
        - duty_cycle 0.0 = 0% speed (pin stays LOW = fan stopped)
        - duty_cycle 1.0 = 100% speed (pin stays HIGH = fan full speed)

        Args:
            duty_cycle: Float between 0.0 (stopped) and 1.0 (full speed)

        Raises:
            ValueError: If duty_cycle is outside valid range
        """
        if not 0.0 <= duty_cycle <= 1.0:
            raise ValueError(f"Duty cycle must be between 0.0 and 1.0, got {duty_cycle}")

        self._current_duty = duty_cycle

        if self.use_hardware_pwm:
            # Hardware PWM: Direct duty cycle
            # 0.0 (stopped) -> 0% PWM (LOW), 1.0 (full speed) -> 100% PWM (HIGH)
            self.fan_pwm.change_duty_cycle(duty_cycle * 100)
        else:
            # Software PWM: gpiozero handles it with active_high=True
            self.fan_pwm.value = duty_cycle

    def set_speed_percent(self, percent):
        """
        Set fan speed as percentage.

        Args:
            percent: Integer or float between 0 (stopped) and 100 (full speed)

        Raises:
            ValueError: If percent is outside valid range
        """
        if not 0 <= percent <= 100:
            raise ValueError(f"Percent must be between 0 and 100, got {percent}")

        self.set_speed(percent / 100.0)

    def get_speed(self):
        """
        Get current fan speed setting (duty cycle).

        Returns:
            Float between 0.0 and 1.0
        """
        return self._current_duty

    def get_speed_percent(self):
        """
        Get current fan speed setting as percentage.

        Returns:
            Float between 0 and 100
        """
        return self.get_speed() * 100

    def get_rpm(self):
        """
        Get current RPM reading from tachometer.

        Returns:
            Float: Current RPM (0 if no pulses detected)
        """
        with self._rpm_lock:
            # Check if we've had a recent pulse (within last 2 seconds)
            time_since_last = time.time() - self._last_pulse_time
            if time_since_last > 2.0:
                self._current_rpm = 0.0  # Fan appears stopped

            return self._current_rpm

    def get_pulse_count(self):
        """
        Get total pulse count since initialization.

        Returns:
            Integer: Total number of pulses detected
        """
        with self._rpm_lock:
            return self._tach_pulses

    def stop(self):
        """
        Stop the fan (set speed to 0%).

        NOTE: With normal logic, this sets the pin LOW to stop the fan.
        """
        self.set_speed(0.0)

    def ramp_speed(self, target_percent, duration_seconds=2.0, steps=20):
        """
        Smoothly ramp fan speed to target value.

        Args:
            target_percent: Target speed (0-100)
            duration_seconds: Time to reach target (default: 2.0 seconds)
            steps: Number of intermediate steps (default: 20)
        """
        current = self.get_speed_percent()
        step_size = (target_percent - current) / steps
        step_delay = duration_seconds / steps

        for i in range(steps):
            new_speed = current + step_size * (i + 1)
            self.set_speed_percent(new_speed)
            time.sleep(step_delay)

        # Ensure we hit the exact target
        self.set_speed_percent(target_percent)

    def _emergency_stop(self):
        """Emergency stop - ensure GPIO12 is LOW (fan stopped)."""
        try:
            import subprocess
            subprocess.run(['sudo', 'pinctrl', 'set', str(self.pwm_pin), 'op', 'dl'],
                          check=False, capture_output=True, timeout=1)
        except:
            pass  # Silent failure - this is emergency cleanup

    def _signal_handler(self, signum, _):
        """Handle SIGTERM and SIGINT by stopping fan and exiting."""
        print(f"\nReceived signal {signum}, stopping fan...")
        self.cleanup()
        sys.exit(0)

    def cleanup(self):
        """Clean up GPIO resources and stop the fan."""
        print("\nCleaning up fan controller...")
        self.stop()
        time.sleep(0.5)  # Allow fan to stop

        if self.use_hardware_pwm:
            # Stop PWM and set GPIO LOW to ensure fan stays stopped
            self.fan_pwm.stop()

            # Set GPIO back to output mode and LOW to keep fan stopped
            import subprocess
            subprocess.run(['sudo', 'pinctrl', 'set', str(self.pwm_pin), 'op', 'dl'],
                          check=False, capture_output=True)
        else:
            self.fan_pwm.close()

        self.tach_input.close()

        print("Fan controller cleanup complete")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.cleanup()


def main():
    """
    Simple test program for fan controller.
    Ramps through different speeds and displays RPM.
    """
    print("=" * 60)
    print("4-Wire Fan Controller Test - Raspberry Pi 5")
    print("Noctua NF-A4x10 5V PWM Fan")
    print("=" * 60)

    with FanController() as fan:
        try:
            # Test sequence: ramp through different speeds
            test_speeds = [0, 30, 50, 70, 100, 70, 50, 30, 0]

            for speed_percent in test_speeds:
                print(f"\n{'='*60}")
                print(f"Setting fan to {speed_percent}%...")
                fan.ramp_speed(speed_percent, duration_seconds=1.5)

                # Wait for fan to stabilize
                time.sleep(1.0)

                # Display RPM readings for 3 seconds
                print("RPM readings:")
                for i in range(6):
                    rpm = fan.get_rpm()
                    duty = fan.get_speed_percent()
                    pulses = fan.get_pulse_count()
                    print(f"  [{i+1}/6] Duty: {duty:5.1f}% | RPM: {rpm:6.0f} | Pulses: {pulses}")
                    time.sleep(0.5)

            print(f"\n{'='*60}")
            print("Test sequence complete!")

        except KeyboardInterrupt:
            print("\n\nCtrl+C detected, stopping fan...")


if __name__ == "__main__":
    main()
