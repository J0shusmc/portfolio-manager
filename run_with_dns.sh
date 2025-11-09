#!/bin/bash
# Temporary DNS fix for running Portfolio Manager

# Use Google DNS temporarily
export RESOLV_CONF_BACKUP=/etc/resolv.conf
echo "Using Google DNS (8.8.8.8) for this session..."

# Run Python with custom DNS by modifying /etc/hosts if needed
# or setting environment that Python's requests library will use

cd "/home/j0shusmc/Projects/Portfolio Manager"
source venv/bin/activate
python main.py
