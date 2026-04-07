"""Shared fixtures for real API tests. No mocks."""

import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.chdir(os.path.join(os.path.dirname(__file__), ".."))

# Default test ticker: Kweichow Moutai (A-share blue chip)
DEFAULT_TICKER = "600519.SS"
