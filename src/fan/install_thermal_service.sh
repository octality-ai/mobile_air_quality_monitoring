#!/bin/bash
#
# Install thermal-fan-control systemd service
#
# This script installs the thermal fan controller as a systemd service
# that automatically starts at boot and restarts on failure.
#

set -e

SERVICE_FILE="thermal-fan-control.service"
SYSTEM_DIR="/etc/systemd/system"

echo "========================================================================"
echo "Thermal Fan Control Service Installer"
echo "========================================================================"
echo ""

# Check if running from correct directory
if [ ! -f "$SERVICE_FILE" ]; then
    echo "Error: $SERVICE_FILE not found in current directory"
    echo "Please run this script from /home/octa/octa/src/fan"
    exit 1
fi

# Check if service already exists
if systemctl is-enabled thermal-fan-control.service &> /dev/null; then
    echo "Service is already installed and enabled."
    read -p "Do you want to reinstall? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Installation cancelled."
        exit 0
    fi
    echo "Stopping and disabling existing service..."
    sudo systemctl stop thermal-fan-control.service
    sudo systemctl disable thermal-fan-control.service
fi

echo "Installing $SERVICE_FILE to $SYSTEM_DIR..."
sudo cp "$SERVICE_FILE" "$SYSTEM_DIR/"

echo "Reloading systemd daemon..."
sudo systemctl daemon-reload

echo "Enabling service for auto-start at boot..."
sudo systemctl enable thermal-fan-control.service

echo "Starting service now..."
sudo systemctl start thermal-fan-control.service

echo ""
echo "========================================================================"
echo "Installation Complete!"
echo "========================================================================"
echo ""
echo "Service Status:"
sudo systemctl status thermal-fan-control.service --no-pager || true
echo ""
echo "Useful Commands:"
echo "  View live logs:    sudo journalctl -u thermal-fan-control.service -f"
echo "  Check status:      sudo systemctl status thermal-fan-control.service"
echo "  Restart service:   sudo systemctl restart thermal-fan-control.service"
echo "  Stop service:      sudo systemctl stop thermal-fan-control.service"
echo "  Disable auto-start: sudo systemctl disable thermal-fan-control.service"
echo ""
echo "The thermal controller will now:"
echo "  - Start automatically at boot"
echo "  - Restart automatically if it crashes"
echo "  - Control Group 1 fans based on CPU temperature"
echo "  - Keep Group 2 fans off (manual control)"
echo ""
