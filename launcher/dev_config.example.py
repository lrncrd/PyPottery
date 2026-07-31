"""
Template for launcher/dev_config.py (gitignored - copy this file and rename it
to enable developer mode locally; the copy is never committed).

When DEVELOPER_MODE is True, the launcher runs each sub-app directly from its
git checkout at the repo root (PyPotteryLayout/, PyPotteryLens/, PyPotteryInk/,
PyPotteryScan/, PyPotteryTrace/) instead of downloading a release zip into
apps/. Install/Update are disabled for these apps - edit the checkout and
pull/push it with git as usual, then just hit Launch to test your changes.
"""

DEVELOPER_MODE = False
