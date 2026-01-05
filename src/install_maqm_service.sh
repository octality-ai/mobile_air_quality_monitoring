#!/bin/bash
# Installation script for MAQM data logger systemd service

set -e

SERVICE_FILE="maqm-logger.service"
WRAPPER_SCRIPT="start_maqm_logger.sh"
SERVICE_PATH="/etc/systemd/system/$SERVICE_FILE"

echo "Installing MAQM data logger service..."

# Make wrapper script executable
chmod +x "$WRAPPER_SCRIPT"

# Copy service file to systemd directory
sudo cp "$SERVICE_FILE" "$SERVICE_PATH"

# Reload systemd daemon
sudo systemctl daemon-reload

# Enable service to start at boot
sudo systemctl enable "$SERVICE_FILE"

# Start the service
sudo systemctl start "$SERVICE_FILE"

echo ""
echo "=========================================="
echo "MAQM Data Logger Service Installed!"
echo "=========================================="
echo ""
echo "Service status:"
sudo systemctl status "$SERVICE_FILE" --no-pager
echo ""
echo "Useful commands:"
echo "  Check status:        sudo systemctl status $SERVICE_FILE"
echo "  View live logs:      sudo journalctl -u $SERVICE_FILE -f"
echo "  View recent logs:    sudo journalctl -u $SERVICE_FILE -n 50"
echo "  Stop service:        sudo systemctl stop $SERVICE_FILE"
echo "  Restart service:     sudo systemctl restart $SERVICE_FILE"
echo "  Disable auto-start:  sudo systemctl disable $SERVICE_FILE"
echo ""
echo "CSV data files are saved to: /home/octa/octa/data/"
echo ""
