# Setting Up on Repl.it

To run this project on Repl.it, follow these steps:

1. Create a new Repl and import from GitHub using: https://github.com/np4abdou/anime-scrapper-arabic.git

2. The `.replit` file is configured to automatically run the setup script that installs the Playwright browser.

3. If you encounter browser-related errors, you may need to manually run:
   ```
   python -m playwright install chromium
   ```

4. After setup is complete, you can run the project with:
   ```
   python anime.py
   ```

## Troubleshooting

If you encounter the error about Playwright browsers not being installed:

1. Open the Shell/Terminal in Repl.it
2. Run: `python -m playwright install chromium`
3. Restart your Repl

The error looks like this:
```
BrowserType.launch: Executable doesn't exist at /home/runner/workspace/.cache/ms-playwright/chromium_headless_shell-XXXX/chrome-linux/headless_shell
``` 