#!/bin/bash
#
# Setup PWM Permissions for Raspberry Pi 5
# =========================================
#
# This script creates udev rules to allow non-root users to access PWM.
#

echo "Setting up PWM permissions for hardware PWM access..."
echo

# Create udev rule for PWM access
echo "Creating udev rule..."
sudo tee /etc/udev/rules.d/99-pwm.rules > /dev/null <<EOF
# Allow users in gpio group to access PWM
SUBSYSTEM=="pwm", KERNEL=="pwmchip*", ACTION=="add", \
  RUN+="/bin/chgrp -R gpio /sys/class/pwm/%k", \
  RUN+="/bin/chmod -R g+w /sys/class/pwm/%k"

SUBSYSTEM=="pwm", KERNEL=="pwm*", ACTION=="add", \
  RUN+="/bin/chgrp -R gpio /sys%p", \
  RUN+="/bin/chmod -R g+w /sys%p"
EOF

echo "✓ Created /etc/udev/rules.d/99-pwm.rules"

# Reload udev rules
echo
echo "Reloading udev rules..."
sudo udevadm control --reload-rules
sudo udevadm trigger

echo "✓ udev rules reloaded"

# Set permissions for existing PWM devices
echo
echo "Setting permissions for existing PWM devices..."
if [ -d "/sys/class/pwm/pwmchip0" ]; then
    sudo chgrp -R gpio /sys/class/pwm/pwmchip0
    sudo chmod -R g+w /sys/class/pwm/pwmchip0
    echo "✓ Set permissions for pwmchip0"
fi

if [ -d "/sys/class/pwm/pwmchip1" ]; then
    sudo chgrp -R gpio /sys/class/pwm/pwmchip1
    sudo chmod -R g+w /sys/class/pwm/pwmchip1
    echo "✓ Set permissions for pwmchip1"
fi

echo
echo "================================================================"
echo "PWM permissions setup complete!"
echo "================================================================"
echo
echo "You may need to log out and back in, or run:"
echo "  newgrp gpio"
echo
echo "Then test with:"
echo "  python3 test_hw_pwm_direct.py"
echo
