#!/usr/bin/env python3
"""
4-Wire Pump Controller for Raspberry Pi 5
==========================================

Controls a 4-wire pump with PWM speed control and tachometer feedback.

Hardware Connections:
- Red wire:   12V power supply (+)
- Black wire: Common ground (12V supply GND + Pi GND)
- Blue wire:  GPIO12 (Physical Pin 32) - PWM control
- Green wire: GPIO23 (Physical Pin 16) - Tachometer feedback

PWM Specifications:
- Frequency: 10-30 kHz (default: 25 kHz)
- Duty Cycle: 0-100% (0% = full speed, 100% = stopped)
- INVERTED LOGIC: LOW signal = pump runs, HIGH signal = pump stops

Tachometer:
- Most pumps output 2 pulses per revolution
- RPM calculated from pulse frequency
"""

import time
import threading
from gpiozero import DigitalInputDevice

try:
    from rpi_hardware_pwm import HardwarePWM
    HARDWARE_PWM_AVAILABLE = True
except ImportError:
    HARDWARE_PWM_AVAILABLE = False
    print("Warning: rpi-hardware-pwm not installed. Install with: sudo pip3 install rpi-hardware-pwm")
    print("Falling back to software PWM (max 10 kHz)")
    from gpiozero import PWMOutputDevice


class PumpController:
    """Controller for 4-wire PWM pump with tachometer feedback."""

    # Pin configuration
    PWM_PIN = 12        # GPIO12 (Physical Pin 32) - Hardware PWM
    TACH_PIN = 23       # GPIO23 (Physical Pin 16) - Tachometer input

    # PWM configuration
    DEFAULT_FREQUENCY = 25000  # 25 kHz (within 10-30 kHz range)

    # Hardware PWM channel mapping for Pi 5
    # GPIO12 = PWM channel 0, GPIO13 = channel 1
    # GPIO18 = PWM channel 2, GPIO19 = channel 3
    PWM_CHANNEL_MAP = {12: 0, 13: 1, 18: 2, 19: 3}

    # Tachometer configuration
    PULSES_PER_REVOLUTION = 2  # Most pumps use 2 pulses per rev

    def __init__(self, pwm_pin=None, tach_pin=None, frequency=None):
        """
        Initialize pump controller with PWM and tachometer.

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
        # NOTE: This pump uses INVERTED logic - LOW = running, HIGH = stopped
        if self.use_hardware_pwm:
            # Use hardware PWM for high frequencies (10-30 kHz)
            if self.pwm_pin not in self.PWM_CHANNEL_MAP:
                raise ValueError(f"GPIO{self.pwm_pin} does not support hardware PWM. Use GPIO 12, 13, 18, or 19.")

            # Configure GPIO pin for PWM function (ALT0)
            import subprocess
            subprocess.run(['sudo', 'pinctrl', 'set', str(self.pwm_pin), 'op', 'a0'],
                          check=False, capture_output=True)

            pwm_channel = self.PWM_CHANNEL_MAP[self.pwm_pin]
            self.pump_pwm = HardwarePWM(pwm_channel=pwm_channel, hz=self.frequency, chip=0)
            # Start at 100% duty (pin HIGH = pump stopped with inverted logic)
            self.pump_pwm.start(100)
            self._current_duty = 0.0  # Track our logical duty cycle (0=stopped, 1=full speed)
        else:
            # Fallback to software PWM (max 10 kHz)
            if self.frequency > 10000:
                print(f"Warning: Frequency {self.frequency} Hz exceeds software PWM limit.")
                print("Reducing to 10000 Hz. Install rpi-hardware-pwm for higher frequencies.")
                self.frequency = 10000

            from gpiozero import PWMOutputDevice
            self.pump_pwm = PWMOutputDevice(
                self.pwm_pin,
                frequency=self.frequency,
                initial_value=0,      # Start at 0% duty (pump stopped)
                active_high=False     # INVERTED: LOW=run, HIGH=stop
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

        # Set up interrupt for tachometer edges (rising edge detection)
        self.tach_input.when_activated = self._tach_pulse_callback

        pwm_mode = "Hardware PWM" if self.use_hardware_pwm else "Software PWM"
        print(f"Pump controller initialized:")
        print(f"  PWM Mode: {pwm_mode}")
        print(f"  PWM Pin: GPIO{self.pwm_pin} (Physical Pin 32)")
        print(f"  PWM Frequency: {self.frequency} Hz")
        print(f"  Tachometer Pin: GPIO{self.tach_pin} (Physical Pin 16)")
        print(f"  Pulses per revolution: {self.PULSES_PER_REVOLUTION}")

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
        Set pump speed via PWM duty cycle.

        NOTE: This pump uses INVERTED logic - we handle the inversion internally:
        - duty_cycle 0.0 = 0% speed (pin stays HIGH = pump stopped)
        - duty_cycle 1.0 = 100% speed (pin stays LOW = pump full speed)

        Args:
            duty_cycle: Float between 0.0 (stopped) and 1.0 (full speed)

        Raises:
            ValueError: If duty_cycle is outside valid range
        """
        if not 0.0 <= duty_cycle <= 1.0:
            raise ValueError(f"Duty cycle must be between 0.0 and 1.0, got {duty_cycle}")

        self._current_duty = duty_cycle

        if self.use_hardware_pwm:
            # Hardware PWM: Manually invert duty cycle
            # 0.0 (stopped) -> 100% PWM (HIGH), 1.0 (full speed) -> 0% PWM (LOW)
            inverted_duty = (1.0 - duty_cycle) * 100
            self.pump_pwm.change_duty_cycle(inverted_duty)
        else:
            # Software PWM: gpiozero handles inversion with active_high=False
            self.pump_pwm.value = duty_cycle

    def set_speed_percent(self, percent):
        """
        Set pump speed as percentage.

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
        Get current pump speed setting (duty cycle).

        Returns:
            Float between 0.0 and 1.0
        """
        return self._current_duty

    def get_speed_percent(self):
        """
        Get current pump speed setting as percentage.

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
                self._current_rpm = 0.0  # Pump appears stopped

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
        Stop the pump (set speed to 0%).

        NOTE: With inverted logic, this sets the pin HIGH to stop the pump.
        """
        self.set_speed(0.0)

    def ramp_speed(self, target_percent, duration_seconds=2.0, steps=20):
        """
        Smoothly ramp pump speed to target value.

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

    def cleanup(self):
        """Clean up GPIO resources and stop the pump."""
        print("\nCleaning up pump controller...")
        self.stop()
        time.sleep(0.5)  # Allow pump to stop

        if self.use_hardware_pwm:
            # Stop PWM and set GPIO HIGH to ensure pump stays stopped
            self.pump_pwm.stop()

            # Set GPIO back to output mode and HIGH to keep pump stopped
            import subprocess
            subprocess.run(['sudo', 'pinctrl', 'set', str(self.pwm_pin), 'op', 'dh'],
                          check=False, capture_output=True)
        else:
            self.pump_pwm.close()

        self.tach_input.close()

        print("Pump controller cleanup complete")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.cleanup()


def main():
    """
    Simple test program for pump controller.
    Ramps through different speeds and displays RPM.
    """
    print("=" * 60)
    print("4-Wire Pump Controller Test - Raspberry Pi 5")
    print("=" * 60)

    with PumpController() as pump:
        try:
            # Test sequence: ramp through different speeds
            test_speeds = [0, 30, 50, 70, 100, 70, 50, 30, 0]

            for speed_percent in test_speeds:
                print(f"\n{'='*60}")
                print(f"Setting pump to {speed_percent}%...")
                pump.ramp_speed(speed_percent, duration_seconds=1.5)

                # Wait for pump to stabilize
                time.sleep(1.0)

                # Display RPM readings for 3 seconds
                print("RPM readings:")
                for i in range(6):
                    rpm = pump.get_rpm()
                    duty = pump.get_speed_percent()
                    pulses = pump.get_pulse_count()
                    print(f"  [{i+1}/6] Duty: {duty:5.1f}% | RPM: {rpm:6.0f} | Pulses: {pulses}")
                    time.sleep(0.5)

            print(f"\n{'='*60}")
            print("Test sequence complete!")

        except KeyboardInterrupt:
            print("\n\nCtrl+C detected, stopping pump...")


if __name__ == "__main__":
    main()
