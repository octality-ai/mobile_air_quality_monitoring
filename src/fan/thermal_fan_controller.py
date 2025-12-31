#!/usr/bin/env python3
"""
Thermal-Controlled Fan Controller
==================================

Automatically controls Group 1 (heat sink) fans based on CPU temperature,
following the same logic as the Raspberry Pi 5's active cooler.

Group 1 fans will automatically adjust speed based on temperature.
Group 2 (air sampling) fans remain under manual control.
"""

import time
import signal
import sys
from dual_fan_controller import DualFanController


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


class ThermalFanController:
    """
    Automatic thermal control for Group 1 fans.
    Group 2 fans remain under manual control.
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
        self.fans = DualFanController()

        # Group 2 manual speed
        self.group2_speed = 0

        # Register signal handlers
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

        print(f"\nThermal Fan Controller initialized:")
        print(f"  Mode: {'Follow Pi fan state' if mode == 'state' else 'Smooth temperature curve'}")
        print(f"  Update interval: {update_interval}s")
        print(f"  Group 1: AUTO (thermal-controlled)")
        print(f"  Group 2: MANUAL")

    def set_group2_speed(self, percent):
        """Set Group 2 (air sampling) fan speed manually."""
        self.group2_speed = percent
        self.fans.set_group2_speed(percent)

    def get_group2_speed(self):
        """Get current Group 2 speed."""
        return self.group2_speed

    def _signal_handler(self, signum, _):
        """Handle shutdown signals."""
        print(f"\nReceived signal {signum}, stopping...")
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
        print("\nStarting thermal monitoring...")
        print("Press Ctrl+C to stop\n")

        try:
            while self.running:
                temp, state, percent = self.update()

                # Update Group 1 fans
                self.fans.set_group1_speed(percent)

                # Display status
                if self.mode == 'state':
                    print(f"Temp: {temp:5.1f}°C | Pi Fan State: {state} | Group 1: {percent:3d}% | Group 2: {self.group2_speed:3d}%")
                else:
                    print(f"Temp: {temp:5.1f}°C | Group 1: {percent:3d}% | Group 2: {self.group2_speed:3d}%")

                time.sleep(self.update_interval)

        except KeyboardInterrupt:
            print("\n\nStopping thermal control...")
            self.stop()

    def stop(self):
        """Stop thermal monitoring and clean up."""
        self.running = False
        self.fans.cleanup()


def main():
    """Demo program showing both thermal control modes."""
    import argparse

    parser = argparse.ArgumentParser(description='Thermal-controlled fan management')
    parser.add_argument('--mode', choices=['state', 'temp'], default='temp',
                       help='Control mode: "state" follows Pi fan, "temp" uses smooth curve (default: temp)')
    parser.add_argument('--interval', type=float, default=2.0,
                       help='Update interval in seconds (default: 2.0)')
    parser.add_argument('--group2', type=int, default=0, metavar='PERCENT',
                       help='Group 2 (air sampling) fan speed 0-100%% (default: 0)')

    args = parser.parse_args()

    print("=" * 70)
    print("Thermal Fan Controller - Raspberry Pi 5")
    print("=" * 70)

    controller = ThermalFanController(mode=args.mode, update_interval=args.interval)

    # Set Group 2 speed if specified
    if args.group2 > 0:
        print(f"\nSetting Group 2 (air sampling) to {args.group2}%")
        controller.set_group2_speed(args.group2)

    # Run thermal control
    controller.run()


if __name__ == "__main__":
    main()
