# Setting Up on Repl.it

To run this project on Repl.it, follow these steps:

1. Create a new Repl and import from GitHub using: https://github.com/np4abdou/anime-scrapper-arabic.git

2. The `.replit` file is configured to automatically run the setup script that installs:
   - Required system dependencies
   - Playwright browser

3. If you encounter browser-related errors, you may need to manually run:
   ```
   sudo apt-get install libnspr4 libnss3 libdbus-1-3 libatk1.0-0 libatk-bridge2.0-0 libatspi2.0-0 libxcomposite1 libxdamage1 libxfixes3 libgbm1 libxkbcommon0 libasound2 libxcb1
   ```

   And then:
   ```
   python -m playwright install chromium
   ```

4. After setup is complete, you can run the project with:
   ```
   python anime.py
   ```

## Troubleshooting

### Missing Browser Error
If you encounter the error about Playwright browsers not being installed:

1. Open the Shell/Terminal in Repl.it
2. Run: `python -m playwright install chromium`
3. Restart your Repl

The error looks like this:
```
BrowserType.launch: Executable doesn't exist at /home/runner/workspace/.cache/ms-playwright/chromium_headless_shell-XXXX/chrome-linux/headless_shell
```

### Missing System Dependencies Error
If you encounter an error about missing system dependencies:

1. Open the Shell/Terminal in Repl.it
2. Run: 
```
sudo apt-get update && sudo apt-get install -y libnspr4 libnss3 libdbus-1-3 libatk1.0-0 libatk-bridge2.0-0 libatspi2.0-0 libxcomposite1 libxdamage1 libxfixes3 libgbm1 libxkbcommon0 libasound2 libxcb1
```
3. Restart your Repl

The error looks like this:
```
Host system is missing dependencies to run browsers.
Please install them with the following command:

    sudo playwright install-deps
``` 