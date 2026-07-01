#!/usr/bin/env bash
set -e

# Upgrade pip first to avoid metadata resolution bugs
pip install --upgrade pip

# Install CPU-only torch via PyPI (not the pytorch whl index) to avoid
# the typing-extensions name inconsistency bug in the pytorch wheel server.
pip install torch --extra-index-url https://download.pytorch.org/whl/cpu

# Install everything else
pip install -r requirements.txt
