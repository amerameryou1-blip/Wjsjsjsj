"""Convenience entry point for the Kaggle bundle.

This file is not required by the launcher, but it can be useful when all bundle
files are already in the same directory. It simply imports the support module
and launches the main dashboard.
"""

from browser_controller_main import launch_dashboard


if __name__ == '__main__':
    launch_dashboard()
