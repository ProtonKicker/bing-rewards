#!/usr/bin/env python3
"""
Bing Rewards GUI Launcher

Quick launcher for the web-based control panel.
"""

import sys
import webbrowser
from pathlib import Path
from threading import Timer

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from bing_rewards.gui.app import main

if __name__ == "__main__":
    # Open browser after a short delay
    def open_browser():
        webbrowser.open("http://localhost:5000")

    Timer(1.5, open_browser).start()

    # Start the server
    main()
