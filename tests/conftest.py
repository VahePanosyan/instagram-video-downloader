"""Pytest configuration and global session fixtures."""

import os

# Ensure Qt runs in headless/offscreen mode across all test sessions
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
