#!/bin/bash
# Install systemd service to ensure all 4 fan GPIOs are LOW at boot/shutdown

echo "Installing quad-fan GPIO initialization service..."

# Copy service file to systemd directory
sudo cp quad-fan-gpio-init.service /etc/systemd/system/

# Reload systemd daemon
sudo systemctl daemon-reload

# Enable the service to run on boot
sudo systemctl enable quad-fan-gpio-init.service

# Start the service now (sets all GPIOs LOW immediately)
sudo systemctl start quad-fan-gpio-init.service

# Check status
echo ""
echo "Service status:"
sudo systemctl status quad-fan-gpio-init.service --no-pager

echo ""
echo "Current GPIO states:"
for gpio in 12 13 18 19; do
    sudo pinctrl get $gpio
done

echo ""
echo "Installation complete!"
echo "All 4 fan GPIOs (12, 13, 18, 19) will be set to LOW on every boot."
echo ""
echo "Commands:"
echo "  Check status: sudo systemctl status quad-fan-gpio-init.service"
echo "  Disable:      sudo systemctl disable quad-fan-gpio-init.service"
echo "  Uninstall:    sudo systemctl stop quad-fan-gpio-init.service && sudo systemctl disable quad-fan-gpio-init.service && sudo rm /etc/systemd/system/quad-fan-gpio-init.service"
