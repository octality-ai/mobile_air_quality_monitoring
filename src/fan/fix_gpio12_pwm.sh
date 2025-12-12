#!/bin/bash
#
# Fix GPIO12 for Hardware PWM
# ============================
#
# Sets GPIO12 to ALT0 function (PWM) on Raspberry Pi 5
#

echo "Configuring GPIO12 for hardware PWM..."
echo

# Check current function
echo "Current GPIO12 function:"
pinctrl get 12

# Set to ALT0 (PWM function)
echo
echo "Setting GPIO12 to ALT0 (PWM)..."
sudo pinctrl set 12 op a0

# Verify
echo
echo "New GPIO12 function:"
pinctrl get 12

echo
echo "Done! GPIO12 is now configured for PWM."
echo "Now test with: sudo python3 test_hw_pwm_direct.py"
