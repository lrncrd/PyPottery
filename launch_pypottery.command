#!/bin/bash
# PyPottery Suite Launcher - macOS double-click entry point
# Finder runs .command files by opening Terminal and executing them,
# unlike .sh files which normally just open in a text editor.
cd "$(dirname "$0")"
exec ./launch_pypottery.sh "$@"
