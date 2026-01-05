#!/bin/bash
# Wrapper script to launch MAQM data logger
# This script sets the working directory and executes the logger

cd /home/octa/octa/src
exec /home/octa/.octa/bin/python3 -u MAQM_main.py
