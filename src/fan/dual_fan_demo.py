#!/usr/bin/env python3
"""
Interactive Dual-Group Fan Controller
======================================

Controls two independent fan groups with minimal real-time display.

Groups:
- Group 1 (Heat Sink):   GPIO12 + GPIO18
- Group 2 (Air Sampling): GPIO13 + GPIO19

Controls:
- 1-9: Set Group 1 speed (10%-90%)
- Q-P: Set Group 2 speed (Q=10%, W=20%, ..., P=90%)
- A:   Group 1 to 100%
- Z:   Group 1 to 0%
- L:   Group 2 to 100%
- .:   Group 2 to 0%a
- X:   Stop all fans
- ESC: Quit
"""

import sys
import termios
import tty
import time
import threading
import select
from dual_fan_controller import DualFanController


class KeyboardController:
    """Non-blocking keyboard input handler."""

    def __init__(self):
        self.old_settings = None

    def __enter__(self):
        self.old_settings = termios.tcgetattr(sys.stdin)
        tty.setraw(sys.stdin.fileno())
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.old_settings:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_settings)

    def get_key(self, timeout=0.1):
        """Get a single keypress (non-blocking)."""
        rlist, _, _ = select.select([sys.stdin], [], [], timeout)

        if rlist:
            key = sys.stdin.read(1)

            # Handle ESC
            if key == '\x1b':
                # Try to read more characters (for arrow keys)
                rlist, _, _ = select.select([sys.stdin], [], [], 0.01)
                if rlist:
                    sys.stdin.read(2)  # Consume arrow key codes
                return 'ESC'

            return key

        return None


class FanDisplay:
    """Real-time display for dual-group fan status."""

    def __init__(self, fans):
        self.fans = fans
        self.running = False
        self.display_thread = None

    def start(self):
        self.running = True
        self.display_thread = threading.Thread(target=self._display_loop, daemon=True)
        self.display_thread.start()

    def stop(self):
        self.running = False
        if self.display_thread:
            self.display_thread.join(timeout=1.0)

    def _display_loop(self):
        while self.running:
            self._update_display()
            time.sleep(0.1)

    def _update_display(self):
        """Minimal display showing both group speeds."""
        g1_speed = self.fans.get_group1_speed()
        g2_speed = self.fans.get_group2_speed()

        # Clear screen
        print('\033[2J\033[H', end='')

        # Display
        print("Group 1 (Heat Sink):   %5.1f%%" % g1_speed)
        print("Group 2 (Air Sampling): %5.1f%%" % g2_speed)
        print()
        print("Keys: 1-9 (G1) | Q-P (G2) | A/Z (G1 100/0) | L/. (G2 100/0) | X (stop) | ESC")

        sys.stdout.flush()


def main():
    """Interactive dual-group fan control."""
    print("Dual-Group Fan Controller")
    print("Initializing...")

    try:
        fans = DualFanController()

        # Start with all fans off
        fans.stop_all()
        time.sleep(0.5)

        # Start display
        display = FanDisplay(fans)
        display.start()

        # Main control loop
        with KeyboardController() as kb:
            running = True
            while running:
                key = kb.get_key(timeout=0.1)

                if key:
                    # Group 1 controls (1-9, A, Z)
                    if key in '123456789':
                        speed = int(key) * 10
                        fans.set_group1_speed(speed)

                    elif key.upper() == 'A':
                        fans.set_group1_speed(100)

                    elif key.upper() == 'Z':
                        fans.set_group1_speed(0)

                    # Group 2 controls (Q-P for 10-90%, L for 100%, . for 0%)
                    elif key.upper() in 'QWERTYUIOP':
                        # Q=10, W=20, E=30, R=40, T=50, Y=60, U=70, I=80, O=90, P=100
                        speeds = {'Q': 10, 'W': 20, 'E': 30, 'R': 40, 'T': 50,
                                 'Y': 60, 'U': 70, 'I': 80, 'O': 90, 'P': 100}
                        speed = speeds.get(key.upper(), 0)
                        fans.set_group2_speed(speed)

                    elif key.upper() == 'L':
                        fans.set_group2_speed(100)

                    elif key == '.':
                        fans.set_group2_speed(0)

                    # Stop all
                    elif key.upper() == 'X':
                        fans.stop_all()

                    # Quit
                    elif key == 'ESC':
                        running = False

        # Stop display
        display.stop()

        # Cleanup
        print('\033[2J\033[H', end='')
        print("Shutting down...")
        fans.cleanup()
        print("Done!")

    except KeyboardInterrupt:
        print("\n\nCtrl+C detected.")
        if 'fans' in locals():
            fans.cleanup()

    except Exception as e:
        print(f"\n\nError: {e}")
        import traceback
        traceback.print_exc()
        if 'fans' in locals():
            fans.cleanup()


if __name__ == "__main__":
    main()
