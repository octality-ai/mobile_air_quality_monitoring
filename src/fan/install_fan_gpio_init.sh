#!/bin/bash
# Install systemd service to ensure GPIO12 is always LOW when fan controller is not running

echo "Installing fan GPIO initialization service..."

# Copy service file to systemd directory
sudo cp fan-gpio-init.service /etc/systemd/system/

# Reload systemd daemon
sudo systemctl daemon-reload

# Enable the service to run on boot
sudo systemctl enable fan-gpio-init.service

# Start the service now
sudo systemctl start fan-gpio-init.service

# Check status
echo ""
echo "Service status:"
sudo systemctl status fan-gpio-init.service --no-pager

echo ""
echo "Current GPIO12 state:"
sudo pinctrl get 12

echo ""
echo "Installation complete!"
echo "GPIO12 will now be set to LOW (0% PWM) on boot and shutdown."
echo ""
echo "To check status: sudo systemctl status fan-gpio-init.service"
echo "To disable:      sudo systemctl disable fan-gpio-init.service"
echo "To uninstall:    sudo systemctl stop fan-gpio-init.service && sudo systemctl disable fan-gpio-init.service && sudo rm /etc/systemd/system/fan-gpio-init.service"
