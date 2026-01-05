#!/usr/bin/env python3
"""
Thermal-Controlled Fan Controller
==================================

Automatically controls Group 1 (heat sink) fans based on CPU temperature,
following the same logic as the Raspberry Pi 5's active cooler.

ONLY controls Group 1 (GPIO12, GPIO18) - heat sink fans.
Does NOT touch Group 2 (GPIO13, GPIO19) - air sampling fans controlled by MAQM logger.
"""

import time
import signal
import sys
import logging
import subprocess
import atexit

try:
    from rpi_hardware_pwm import HardwarePWM
except ImportError:
    print("ERROR: rpi-hardware-pwm not installed.")
    print("Install with: sudo pip3 install rpi-hardware-pwm")
    sys.exit(1)


def setup_logging():
    """Configure logging for systemd journal."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s: %(message)s',
        stream=sys.stdout
    )
    return logging.getLogger(__name__)


logger = setup_logging()


class ThermalMonitor:
    """Monitor Raspberry Pi 5 CPU temperature and cooling state."""

    TEMP_PATH = "/sys/class/thermal/thermal_zone0/temp"
    COOLING_STATE_PATH = "/sys/class/thermal/cooling_device0/cur_state"

    # Pi 5 temperature thresholds (°C)
    TEMP_THRESHOLDS = [
        (0,    50.0),   # State 0: Off
        (50.0, 60.0),   # State 1: Low
        (60.0, 67.5),   # State 2: Medium-low
        (67.5, 75.0),   # State 3: Medium-high
        (75.0, 999.0),  # State 4: Full speed
    ]

    # Map cooling states to fan percentages
    STATE_TO_PERCENT = {
        0: 0,      # Off
        1: 30,     # Low
        2: 50,     # Medium-low
        3: 70,     # Medium-high
        4: 100,    # Full speed
    }

    @staticmethod
    def get_temperature():
        """
        Get CPU temperature in degrees Celsius.

        Returns:
            float: Temperature in °C
        """
        try:
            with open(ThermalMonitor.TEMP_PATH, 'r') as f:
                millidegrees = int(f.read().strip())
                return millidegrees / 1000.0
        except (FileNotFoundError, ValueError, PermissionError) as e:
            print(f"Warning: Could not read temperature: {e}")
            return 50.0  # Safe default

    @staticmethod
    def get_cooling_state():
        """
        Get current cooling device state (0-4).

        Returns:
            int: Cooling state (0=off, 4=max)
        """
        try:
            with open(ThermalMonitor.COOLING_STATE_PATH, 'r') as f:
                return int(f.read().strip())
        except (FileNotFoundError, ValueError, PermissionError) as e:
            print(f"Warning: Could not read cooling state: {e}")
            return 0

    @staticmethod
    def temp_to_percent_smooth(temp):
        """
        Convert temperature to fan percentage with smooth curve.

        Uses a continuous curve for smoother speed transitions.

        Args:
            temp: Temperature in °C

        Returns:
            int: Fan speed percentage (0-100)
        """
        if temp < 50.0:
            return 0
        elif temp < 60.0:
            # Linear ramp 0% -> 30% between 50-60°C
            return int((temp - 50.0) / 10.0 * 30)
        elif temp < 67.5:
            # Linear ramp 30% -> 50% between 60-67.5°C
            return int(30 + (temp - 60.0) / 7.5 * 20)
        elif temp < 75.0:
            # Linear ramp 50% -> 70% between 67.5-75°C
            return int(50 + (temp - 67.5) / 7.5 * 20)
        else:
            # Linear ramp 70% -> 100% between 75-85°C
            return min(100, int(70 + (temp - 75.0) / 10.0 * 30))

    @staticmethod
    def state_to_percent(state):
        """
        Convert cooling state to fan percentage.

        Args:
            state: Cooling device state (0-4)

        Returns:
            int: Fan speed percentage (0-100)
        """
        return ThermalMonitor.STATE_TO_PERCENT.get(state, 0)


class Group1FanController:
    """
    Direct PWM controller for Group 1 (heat sink) fans ONLY.
    Does NOT initialize or control Group 2 GPIOs.
    """

    # Group 1 GPIO configuration
    GROUP1_GPIOS = [12, 18]  # Heat sink fans only
    PWM_CONFIG = {
        12: {'chip': 0, 'channel': 0},  # GPIO12 = PWM0_CHAN0
        18: {'chip': 0, 'channel': 2}   # GPIO18 = PWM0_CHAN2
    }
    DEFAULT_FREQUENCY = 25000  # 25 kHz

    def __init__(self, frequency=None):
        """Initialize Group 1 PWM controllers only."""
        self.frequency = frequency or self.DEFAULT_FREQUENCY
        self.pwm_channels = {}
        self.current_speed = 0

        # Initialize ONLY Group 1 GPIOs
        for gpio in self.GROUP1_GPIOS:
            self._init_pwm(gpio)

        # Register cleanup
        atexit.register(self._emergency_stop)

    def _init_pwm(self, gpio):
        """Initialize a single PWM channel."""
        # Configure GPIO for PWM (GPIO12 uses ALT0, GPIO18 uses ALT3)
        alt_function = 'a0' if gpio == 12 else 'a3'
        subprocess.run(['sudo', 'pinctrl', 'set', str(gpio), 'op', alt_function],
                      check=False, capture_output=True)

        # Initialize hardware PWM
        config = self.PWM_CONFIG[gpio]
        pwm = HardwarePWM(pwm_channel=config['channel'], hz=self.frequency, chip=config['chip'])
        pwm.start(0)  # Start at 0%

        self.pwm_channels[gpio] = pwm

    def set_speed(self, percent):
        """Set speed for Group 1 fans."""
        if not 0 <= percent <= 100:
            raise ValueError(f"Percent must be between 0 and 100, got {percent}")

        for gpio in self.GROUP1_GPIOS:
            self.pwm_channels[gpio].change_duty_cycle(percent)

        self.current_speed = percent

    def get_speed(self):
        """Get current speed."""
        return self.current_speed

    def _emergency_stop(self):
        """Emergency stop - set Group 1 GPIOs LOW."""
        try:
            for gpio in self.GROUP1_GPIOS:
                subprocess.run(['sudo', 'pinctrl', 'set', str(gpio), 'op', 'dl'],
                              check=False, capture_output=True, timeout=1)
        except:
            pass

    def cleanup(self):
        """Clean up and stop fans."""
        self.set_speed(0)
        time.sleep(0.1)
        for gpio, pwm in self.pwm_channels.items():
            pwm.stop()
            subprocess.run(['sudo', 'pinctrl', 'set', str(gpio), 'op', 'dl'],
                          check=False, capture_output=True)


class ThermalFanController:
    """
    Automatic thermal control for Group 1 fans ONLY.
    Does NOT touch Group 2 fans (reserved for MAQM logger).
    """

    def __init__(self, mode='state', update_interval=2.0):
        """
        Initialize thermal fan controller.

        Args:
            mode: 'state' to follow Pi fan state, 'temp' for smooth temperature curve
            update_interval: Seconds between temperature checks (default: 2.0)
        """
        self.mode = mode
        self.update_interval = update_interval
        self.running = False
        self.fans = Group1FanController()

        # Register signal handlers
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

        logger.info("Thermal Fan Controller initialized (Group 1 ONLY)")
        logger.info(f"  Mode: {'Follow Pi fan state' if mode == 'state' else 'Smooth temperature curve'}")
        logger.info(f"  Update interval: {update_interval}s")
        logger.info(f"  Controlling: GPIO12, GPIO18 (Group 1 heat sink fans)")
        logger.info(f"  NOT touching: GPIO13, GPIO19 (Group 2 reserved for MAQM)")

    def _signal_handler(self, signum, _):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, stopping...")
        self.stop()
        sys.exit(0)

    def update(self):
        """Update Group 1 fan speed based on temperature (single update)."""
        if self.mode == 'state':
            # Follow Pi cooling device state
            state = ThermalMonitor.get_cooling_state()
            percent = ThermalMonitor.state_to_percent(state)
            temp = ThermalMonitor.get_temperature()
            return temp, state, percent
        else:
            # Use smooth temperature curve
            temp = ThermalMonitor.get_temperature()
            percent = ThermalMonitor.temp_to_percent_smooth(temp)
            state = None  # Not using state in this mode
            return temp, state, percent

    def run(self):
        """Run continuous thermal monitoring loop."""
        self.running = True
        logger.info("Starting thermal monitoring...")
        if sys.stdout.isatty():
            print("Press Ctrl+C to stop\n")

        # Counter for periodic logging when running as service
        log_counter = 0
        log_interval = int(30 / self.update_interval)  # Log every 30 seconds

        try:
            while self.running:
                temp, state, percent = self.update()

                # Update Group 1 fans only
                self.fans.set_speed(percent)

                # Display status
                if sys.stdout.isatty():
                    # Running manually in terminal - show every update
                    if self.mode == 'state':
                        print(f"Temp: {temp:5.1f}°C | Pi Fan State: {state} | Group 1: {percent:3d}%")
                    else:
                        print(f"Temp: {temp:5.1f}°C | Group 1: {percent:3d}%")
                else:
                    # Running as service - log every 30 seconds (based on iteration count)
                    if log_counter % log_interval == 0:
                        if self.mode == 'state':
                            logger.info(f"Temp: {temp:5.1f}°C | Pi Fan State: {state} | G1: {percent:3d}%")
                        else:
                            logger.info(f"Temp: {temp:5.1f}°C | G1: {percent:3d}%")
                    log_counter += 1

                time.sleep(self.update_interval)

        except KeyboardInterrupt:
            logger.info("Stopping thermal control...")
            self.stop()

    def stop(self):
        """Stop thermal monitoring and clean up."""
        self.running = False
        self.fans.cleanup()


def main():
    """Demo program showing thermal control for Group 1 (heat sink) fans only."""
    import argparse

    parser = argparse.ArgumentParser(description='Thermal-controlled fan management (Group 1 only)')
    parser.add_argument('--mode', choices=['state', 'temp'], default='temp',
                       help='Control mode: "state" follows Pi fan, "temp" uses smooth curve (default: temp)')
    parser.add_argument('--interval', type=float, default=2.0,
                       help='Update interval in seconds (default: 2.0)')

    args = parser.parse_args()

    print("=" * 70)
    print("Thermal Fan Controller - Raspberry Pi 5 (Group 1 Only)")
    print("=" * 70)
    print("NOTE: This controller only manages Group 1 (GPIO12, GPIO18)")
    print("      Group 2 (GPIO13, GPIO19) is reserved for MAQM logger")
    print("=" * 70)

    controller = ThermalFanController(mode=args.mode, update_interval=args.interval)

    # Run thermal control
    controller.run()


if __name__ == "__main__":
    main()
