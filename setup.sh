#!/bin/bash
echo "Installing system dependencies for Playwright..."
apt-get update
apt-get install -y libnspr4 libnss3 libdbus-1-3 libatk1.0-0 libatk-bridge2.0-0 libatspi2.0-0 libxcomposite1 libxdamage1 libxfixes3 libgbm1 libxkbcommon0 libasound2 libxcb1

echo "Installing Playwright browsers..."
python -m playwright install chromium
echo "Setup complete!" 