#!/bin/bash
# Wrapper script to start thermal fan controller
# This ensures all paths are absolute and environment is correct

cd /home/octa/octa/src/fan || exit 1
exec /home/octa/.octa/bin/python3 thermal_fan_controller.py --mode state --interval 2.0
