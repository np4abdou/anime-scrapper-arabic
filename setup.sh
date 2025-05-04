#!/bin/bash
echo "Setting up environment for repl.it..."

# Install Python dependencies
pip install -r requirements.txt

# Try to install playwright in a way that works on repl.it
echo "Installing Playwright..."
pip install playwright

# Special configuration for repl.it to run without system dependencies
echo "Setting up special configuration for browser usage..."
export PLAYWRIGHT_BROWSERS_PATH=0
python -m playwright install chromium --with-deps

# Create a configuration file for Playwright
mkdir -p ~/.playwright
echo '{
  "browsers": [
    {
      "name": "chromium",
      "headless": true,
      "launchOptions": {
        "args": [
          "--disable-gpu",
          "--no-sandbox",
          "--disable-setuid-sandbox",
          "--disable-dev-shm-usage"
        ]
      }
    }
  ]
}' > ~/.playwright/config.json

echo "Setup complete! If you still encounter issues, please run:"
echo "python -m playwright install-deps"
echo "in the Shell tab." 