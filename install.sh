#!/bin/bash
# It is used to install the necessary components for the Meltingplot Duet SimplyPrint Connector.
# Ensure you have the required permissions to execute this script.

set -e
trap 'echo "An error occurred. Exiting..."; return 1' ERR

if [ "$(uname -m)" != "aarch64" ]; then
    echo "It is recommended to use a 64-bit system."
fi

if ! grep -q "bookworm" /etc/os-release; then
    echo "This script is only for Debian Bookworm."
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
if [[ $(echo -e "3.11\n$PYTHON_VERSION" | sort -V | head -n1) != "3.11" ]]; then
    echo "Python 3.11 or higher is required."
    exit 1
fi

sudo mkdir -p /opt/duet-simplyprint-connector
sudo chown "$USER":"$USER" /opt/duet-simplyprint-connector
sudo chmod 755 /opt/duet-simplyprint-connector

sudo apt-get update
sudo apt-get install -y git ffmpeg python3-venv gcc g++ make python3-dev libatlas-base-dev libopenblas0 libopenblas-dev liblapack-dev libjpeg-dev

cd /opt/duet-simplyprint-connector
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install --upgrade --extra-index-url https://www.piwheels.org/simple simplyprint-duet3d
simplyprint-duet3d autodiscover
simplyprint-duet3d install-as-service