#!/usr/bin/env python3
"""
Continuous Pump Controller with Simple Keyboard Control
========================================================

Simple program to run the pump continuously with keyboard speed adjustment.

Controls:
- UP arrow    : Increase speed by 10%
- DOWN arrow  : Decrease speed by 10%
- Q or Ctrl+C : Quit (safely stops pump)

The pump runs at the set speed until you change it or quit.
"""

import sys
import termios
import tty
import time
import signal
from pump_controller import PumpController


class SimpleKeyboard:
    """Simple keyboard handler for arrow keys and Q."""

    def __init__(self):
        self.old_settings = None

    def __enter__(self):
        """Enable raw keyboard input mode."""
        self.old_settings = termios.tcgetattr(sys.stdin)
        tty.setraw(sys.stdin.fileno())
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Restore normal keyboard input mode."""
        if self.old_settings:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_settings)

    def get_key(self):
        """
        Get a single keypress (blocking).

        Returns:
            str: 'UP', 'DOWN', 'Q', or None
        """
        key = sys.stdin.read(1)

        # Handle arrow keys (escape sequences)
        if key == '\x1b':  # ESC
            next_chars = sys.stdin.read(2)
            if next_chars == '[A':
                return 'UP'
            elif next_chars == '[B':
                return 'DOWN'

        # Handle Q (both lowercase and uppercase)
        if key.upper() == 'Q':
            return 'Q'

        return None


def clear_screen():
    """Clear terminal screen."""
    print('\033[2J\033[H', end='')
    sys.stdout.flush()


def print_status(speed, rpm):
    """Print current pump status."""
    clear_screen()

    print("=" * 60)
    print("   CONTINUOUS PUMP CONTROLLER")
    print("=" * 60)
    print()

    # Speed bar
    bar_width = 40
    filled = int(speed / 100.0 * bar_width)
    bar = '█' * filled + '░' * (bar_width - filled)

    print(f"  Speed: {speed:5.1f}%  [{bar}]")
    print()
    print(f"  RPM:   {rpm:7.0f} RPM")
    print()
    print("-" * 60)
    print("  CONTROLS:")
    print("    ↑ (Up arrow)    : Increase speed by 10%")
    print("    ↓ (Down arrow)  : Decrease speed by 10%")
    print("    Q or Ctrl+C     : Quit (safely stops pump)")
    print("-" * 60)
    print()
    print(f"  Pump running at {speed:.0f}% speed...")
    print("  Press a key to adjust speed or Q to quit.")
    print()
    sys.stdout.flush()


def main():
    """Main continuous pump controller."""
    print("=" * 60)
    print("Continuous Pump Controller")
    print("=" * 60)
    print("\nInitializing pump...")

    # Initialize pump
    pump = PumpController()

    # Start at 30% speed
    current_speed = 30.0
    pump.set_speed_percent(current_speed)

    print(f"Pump started at {current_speed:.0f}%")
    print("\nPress UP/DOWN arrows to adjust speed, Q to quit.")
    time.sleep(2)

    try:
        with SimpleKeyboard() as kb:
            running = True

            while running:
                # Get current RPM
                rpm = pump.get_rpm()

                # Display status
                print_status(current_speed, rpm)

                # Wait for keypress (blocking)
                try:
                    key = kb.get_key()
                except KeyboardInterrupt:
                    # Handle Ctrl+C during keypress
                    print("\n\n  → Ctrl+C detected. Quitting and stopping pump...")
                    running = False
                    continue

                if key == 'UP':
                    # Increase speed by 10%
                    new_speed = min(100.0, current_speed + 10.0)
                    if new_speed != current_speed:
                        current_speed = new_speed
                        pump.set_speed_percent(current_speed)
                        print(f"\n  → Speed increased to {current_speed:.0f}%")
                        time.sleep(0.5)  # Brief pause to show message
                    else:
                        print(f"\n  → Already at maximum speed (100%)")
                        time.sleep(0.5)

                elif key == 'DOWN':
                    # Decrease speed by 10%
                    new_speed = max(0.0, current_speed - 10.0)
                    if new_speed != current_speed:
                        current_speed = new_speed
                        pump.set_speed_percent(current_speed)
                        print(f"\n  → Speed decreased to {current_speed:.0f}%")
                        time.sleep(0.5)  # Brief pause to show message
                    else:
                        print(f"\n  → Already at minimum speed (0%)")
                        time.sleep(0.5)

                elif key == 'Q':
                    # Quit
                    print("\n  → Quitting and stopping pump...")
                    running = False

    except KeyboardInterrupt:
        print("\n\n  → Ctrl+C detected. Quitting and stopping pump...")

    finally:
        # Clean up and stop pump
        clear_screen()
        print("=" * 60)
        print("Shutting down...")
        print("=" * 60)
        print("\nStopping pump...")
        pump.cleanup()
        print("Pump stopped safely.")
        print("\nDone!")


if __name__ == "__main__":
    main()
