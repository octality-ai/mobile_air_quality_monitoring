#!/usr/bin/env python3
"""
Quick Test Script for Fan Tachometer Reading
=============================================

Tests tachometer reading on Group 2 (air sampling) fans.
Run this script to verify your tachometer wiring is correct.

Usage:
    sudo /home/octa/.octa/bin/python3 test_tachometer.py
"""

import sys
import time
from dual_fan_controller_with_tach import DualFanControllerWithTach


def test_group2_tachometers():
    """Test Group 2 (priority) fan tachometers."""
    print("=" * 70)
    print("Group 2 Fan Tachometer Test")
    print("=" * 70)
    print("\nThis will test tachometer reading on Group 2 (air sampling) fans.")
    print("\nExpected connections:")
    print("  Fan 1: GPIO13 (Pin 33) PWM → GPIO6 (Pin 31) Tach")
    print("  Fan 2: GPIO19 (Pin 35) PWM → GPIO26 (Pin 37) Tach")
    print("\nPress Ctrl+C to stop\n")

    with DualFanControllerWithTach(enable_tach=True) as fans:
        try:
            # Test at different speeds
            test_speeds = [30, 50, 75, 100]

            for speed in test_speeds:
                print(f"\n{'='*70}")
                print(f"Testing at {speed}% speed")
                print('='*70)

                fans.set_group2_speed(speed)
                print(f"Set Group 2 fans to {speed}%")
                print("Waiting 3 seconds for fans to stabilize...")
                time.sleep(3)

                # Monitor RPM for 5 seconds
                print("\nRPM readings (updating every second):")
                for i in range(5):
                    time.sleep(1)  # Wait 1 second between readings

                    # Update and get RPM reading
                    fans.update_tachometers()
                    rpm = fans.get_group2_rpm()

                    gpio13_rpm = rpm.get(13, 0)
                    gpio19_rpm = rpm.get(19, 0)

                    # Check if readings are reasonable
                    status13 = "✓" if gpio13_rpm > 0 else "✗"
                    status19 = "✓" if gpio19_rpm > 0 else "✗"

                    print(f"  [{i+1}/5] GPIO13: {gpio13_rpm:5.0f} RPM {status13}  |  "
                          f"GPIO19: {gpio19_rpm:5.0f} RPM {status19}")

            # Stop fans
            print("\n" + "="*70)
            print("Stopping fans and verifying RPM drops to zero...")
            print("="*70)

            fans.stop_all()
            time.sleep(3)  # Wait longer for fans to fully stop

            fans.update_tachometers()
            final_rpm = fans.get_group2_rpm()

            print(f"GPIO13 final RPM: {final_rpm.get(13, 0):.0f}")
            print(f"GPIO19 final RPM: {final_rpm.get(19, 0):.0f}")

            print("\n" + "="*70)
            print("Test Complete!")
            print("="*70)

            # Summary
            max_final_rpm = max(final_rpm.values())
            if max_final_rpm > 200:
                print(f"\n⚠ WARNING: Fans still showing {max_final_rpm:.0f} RPM after stop command.")
                print("This could indicate a wiring issue or stuck fans.")
            elif max_final_rpm > 0:
                print(f"\n✓ SUCCESS: Tachometers working! (residual RPM: {max_final_rpm:.0f})")
                print("Note: Small residual RPM during spin-down is normal.")
            else:
                print("\n✓ SUCCESS: Tachometers working perfectly!")

        except KeyboardInterrupt:
            print("\n\nTest interrupted by user.")


def test_group1_tachometers():
    """Test Group 1 (optional) fan tachometers."""
    print("=" * 70)
    print("Group 1 Fan Tachometer Test")
    print("=" * 70)
    print("\nThis will test tachometer reading on Group 1 (heat sink) fans.")
    print("\nExpected connections:")
    print("  Fan 1: GPIO18 (Pin 12) PWM → GPIO23 (Pin 16) Tach")
    print("  Fan 2: GPIO12 (Pin 32) PWM → GPIO16 (Pin 36) Tach")
    print("\nPress Ctrl+C to stop\n")

    with DualFanControllerWithTach(enable_tach=True) as fans:
        try:
            # Quick test at 50% speed
            print("Setting Group 1 fans to 50%...")
            fans.set_group1_speed(50)
            time.sleep(3)

            print("\nRPM readings (5 samples):")
            for i in range(5):
                time.sleep(1)  # Wait 1 second between readings

                # Update and get RPM reading
                fans.update_tachometers()
                rpm = fans.get_group1_rpm()

                gpio18_rpm = rpm.get(18, 0)
                gpio12_rpm = rpm.get(12, 0)

                status18 = "✓" if gpio18_rpm > 0 else "✗"
                status12 = "✓" if gpio12_rpm > 0 else "✗"

                print(f"  [{i+1}/5] GPIO18: {gpio18_rpm:5.0f} RPM {status18}  |  "
                      f"GPIO12: {gpio12_rpm:5.0f} RPM {status12}")

            fans.stop_all()
            print("\n✓ Group 1 test complete!")

        except KeyboardInterrupt:
            print("\n\nTest interrupted by user.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--group1":
        test_group1_tachometers()
    else:
        test_group2_tachometers()
        print("\nTo test Group 1 (optional), run:")
        print("  sudo /home/octa/.octa/bin/python3 test_tachometer.py --group1")
