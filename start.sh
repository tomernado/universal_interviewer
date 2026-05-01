#!/bin/sh
# Start the file-browser API in the background, then the Telegram bot in the foreground.
python tools/file_browser.py &
python main.py
