#!/bin/bash
# Test script to verify read-only tachometer monitor works while fans are controlled

echo "======================================================================="
echo "Read-Only Tachometer Monitor Test"
echo "======================================================================="
echo ""
echo "This test will:"
echo "  1. Start Group 2 fans at 50% speed"
echo "  2. Monitor RPM with read-only script for 10 seconds"
echo "  3. Stop the fans"
echo ""

# Create a temporary Python script to control fans
cat > /tmp/fan_controller_test.py << 'EOF'
#!/usr/bin/env python3
import time
import sys
sys.path.insert(0, '/home/octa/octa/src/fan')
from dual_fan_controller_with_tach import DualFanControllerWithTach

print("Starting Group 2 fans at 50%...")
with DualFanControllerWithTach(enable_tach=False) as fans:
    fans.set_group2_speed(50)
    print("Fans running at 50%. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping fans...")
EOF

# Start fan controller in background
sudo /home/octa/.octa/bin/python3 /tmp/fan_controller_test.py &
FAN_PID=$!

# Wait for fans to start
sleep 3

echo ""
echo "Fans should now be running at 50%..."
echo "Starting read-only monitor for 10 seconds..."
echo ""

# Run the read-only monitor
timeout 10 sudo /home/octa/.octa/bin/python3 /home/octa/octa/src/fan/read_group2_tachometer.py

# Stop the fan controller
echo ""
echo "Stopping fan controller..."
sudo kill -INT $FAN_PID 2>/dev/null
wait $FAN_PID 2>/dev/null

# Clean up
rm -f /tmp/fan_controller_test.py

echo ""
echo "Test complete!"
