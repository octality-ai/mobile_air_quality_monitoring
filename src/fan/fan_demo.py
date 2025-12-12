#!/usr/bin/env python3
"""
Interactive 4-Wire Fan Controller Demo
=======================================

Real-time fan control with live RPM feedback display.
Designed for Noctua NF-A4x10 5V PWM fan.

Controls:
- UP/DOWN arrows:  Increase/decrease fan speed by 5%
- LEFT/RIGHT:      Increase/decrease fan speed by 1%
- 0-9:            Set fan to 0%, 10%, 20%, ... 90%
- F:              Full speed (100%)
- S:              Stop fan (0%)
- R:              Ramp speed smoothly
- Q or ESC:       Quit

Hardware Connections:
- GPIO12 (Pin 32) → Blue wire (PWM control - NORMAL LOGIC)
- GPIO23 (Pin 16) → Green wire (Tachometer)
- Pi GND → Black wire (common ground with 5V supply)
- 5V Supply → Yellow wire

IMPORTANT: This fan uses normal PWM logic (HIGH=full speed, LOW=stopped).
Reference: https://www.noctua.at/en/products/nf-a4x10-5v-pwm
"""

import sys
import termios
import tty
import time
import threading
from fan_control import FanController


class KeyboardController:
    """Non-blocking keyboard input handler for interactive control."""

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

    def get_key(self, timeout=0.1):
        """
        Get a single keypress (non-blocking with timeout).

        Args:
            timeout: Maximum time to wait for key in seconds

        Returns:
            str: Key pressed, or None if timeout
        """
        import select

        # Check if input is available
        rlist, _, _ = select.select([sys.stdin], [], [], timeout)

        if rlist:
            key = sys.stdin.read(1)

            # Handle arrow keys and special keys (escape sequences)
            if key == '\x1b':  # ESC or arrow key
                # Read the next two characters
                next_chars = sys.stdin.read(2)
                if next_chars == '[A':
                    return 'UP'
                elif next_chars == '[B':
                    return 'DOWN'
                elif next_chars == '[C':
                    return 'RIGHT'
                elif next_chars == '[D':
                    return 'LEFT'
                else:
                    return 'ESC'

            return key

        return None


class FanDisplay:
    """Real-time display manager for fan status."""

    def __init__(self, fan):
        self.fan = fan
        self.running = False
        self.display_thread = None
        self.message = ""
        self.message_time = 0

    def start(self):
        """Start the display update thread."""
        self.running = True
        self.display_thread = threading.Thread(target=self._display_loop, daemon=True)
        self.display_thread.start()

    def stop(self):
        """Stop the display update thread."""
        self.running = False
        if self.display_thread:
            self.display_thread.join(timeout=1.0)

    def set_message(self, message, duration=2.0):
        """Display a temporary status message."""
        self.message = message
        self.message_time = time.time() + duration

    def _display_loop(self):
        """Background thread that continuously updates the display."""
        while self.running:
            self._update_display()
            time.sleep(0.2)  # Update 5 times per second

    def _update_display(self):
        """Update the terminal display with current fan status."""
        # Get current values
        speed_percent = self.fan.get_speed_percent()
        rpm = self.fan.get_rpm()
        pulse_count = self.fan.get_pulse_count()

        # Create speed bar graph
        bar_width = 40
        filled = int(speed_percent / 100.0 * bar_width)
        bar = '█' * filled + '░' * (bar_width - filled)

        # Check for temporary message
        current_message = ""
        if time.time() < self.message_time:
            current_message = self.message

        # Clear screen and move cursor to top
        print('\033[2J\033[H', end='')

        # Print display
        print("=" * 70)
        print("     4-WIRE FAN CONTROLLER - Noctua NF-A4x10 5V PWM")
        print("=" * 70)
        print()
        print(f"  Speed:  {speed_percent:5.1f}%  [{bar}]")
        print()
        print(f"  RPM:    {rpm:7.0f} RPM")
        print(f"  Pulses: {pulse_count:7d} total")
        print()
        print("-" * 70)
        print("  CONTROLS:")
        print("    ↑/↓ arrows    : Adjust speed by 5%")
        print("    ←/→ arrows    : Adjust speed by 1%")
        print("    0-9           : Set speed to 0%, 10%, ... 90%")
        print("    F             : Full speed (100%)")
        print("    S             : Stop (0%)")
        print("    R             : Ramp to custom speed")
        print("    Q or ESC      : Quit")
        print("-" * 70)

        if current_message:
            print(f"  STATUS: {current_message}")
        else:
            print("  Ready for input...")

        print()
        sys.stdout.flush()


def interactive_ramp(fan, display):
    """Prompt user for ramp target and duration."""
    # Temporarily stop display
    display.stop()

    # Restore terminal settings for input
    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, display_kb_settings)

    try:
        print("\n" + "=" * 70)
        print("RAMP CONFIGURATION")
        print("=" * 70)

        target = input("Enter target speed (0-100%): ").strip()
        target_percent = float(target)

        if not 0 <= target_percent <= 100:
            print("Invalid speed. Must be 0-100.")
            time.sleep(2)
            return

        duration = input("Enter ramp duration in seconds (default 2.0): ").strip()
        if duration:
            duration_seconds = float(duration)
        else:
            duration_seconds = 2.0

        print(f"\nRamping to {target_percent}% over {duration_seconds} seconds...")

        # Restart display
        display.start()
        time.sleep(0.5)

        # Perform ramp
        fan.ramp_speed(target_percent, duration_seconds=duration_seconds)
        display.set_message(f"Ramped to {target_percent}%", duration=3.0)

    except ValueError as e:
        print(f"Invalid input: {e}")
        time.sleep(2)
    except Exception as e:
        print(f"Error: {e}")
        time.sleep(2)
    finally:
        # Restore raw mode
        tty.setraw(sys.stdin.fileno())
        display.start()


# Global variable for terminal settings (used in ramp function)
display_kb_settings = None


def main():
    """Main interactive fan control program."""
    global display_kb_settings

    print("=" * 70)
    print("4-Wire Fan Controller - Interactive Demo")
    print("Noctua NF-A4x10 5V PWM Fan")
    print("=" * 70)
    print("\nInitializing...")

    try:
        # Initialize fan controller
        fan = FanController()

        # Start with fan off
        fan.stop()
        time.sleep(0.5)

        # Initialize display
        display = FanDisplay(fan)
        display.start()

        # Enable keyboard control
        with KeyboardController() as kb:
            # Save settings for ramp function
            display_kb_settings = termios.tcgetattr(sys.stdin)

            display.set_message("System ready. Use arrow keys to control fan.", duration=3.0)

            # Main control loop
            running = True
            while running:
                key = kb.get_key(timeout=0.1)

                if key:
                    current_speed = fan.get_speed_percent()

                    # Arrow keys - adjust speed
                    if key == 'UP':
                        new_speed = min(100, current_speed + 5)
                        fan.set_speed_percent(new_speed)
                        display.set_message(f"Speed increased to {new_speed:.1f}%")

                    elif key == 'DOWN':
                        new_speed = max(0, current_speed - 5)
                        fan.set_speed_percent(new_speed)
                        display.set_message(f"Speed decreased to {new_speed:.1f}%")

                    elif key == 'RIGHT':
                        new_speed = min(100, current_speed + 1)
                        fan.set_speed_percent(new_speed)
                        display.set_message(f"Speed: {new_speed:.1f}%")

                    elif key == 'LEFT':
                        new_speed = max(0, current_speed - 1)
                        fan.set_speed_percent(new_speed)
                        display.set_message(f"Speed: {new_speed:.1f}%")

                    # Number keys - set specific speeds
                    elif key in '0123456789':
                        speed = int(key) * 10
                        fan.set_speed_percent(speed)
                        display.set_message(f"Speed set to {speed}%")

                    # F - Full speed
                    elif key.upper() == 'F':
                        fan.set_speed_percent(100)
                        display.set_message("Full speed (100%)")

                    # S - Stop
                    elif key.upper() == 'S':
                        fan.stop()
                        display.set_message("Fan stopped")

                    # R - Ramp mode
                    elif key.upper() == 'R':
                        interactive_ramp(fan, display)

                    # Q or ESC - Quit
                    elif key.upper() == 'Q' or key == 'ESC':
                        display.set_message("Shutting down...")
                        running = False

        # Stop display
        display.stop()

        # Cleanup
        print('\033[2J\033[H', end='')  # Clear screen
        print("Shutting down fan controller...")
        fan.cleanup()
        print("Done!")

    except KeyboardInterrupt:
        print("\n\nCtrl+C detected. Shutting down...")
        if 'fan' in locals():
            fan.cleanup()

    except Exception as e:
        print(f"\n\nError: {e}")
        import traceback
        traceback.print_exc()
        if 'fan' in locals():
            fan.cleanup()


if __name__ == "__main__":
    main()
