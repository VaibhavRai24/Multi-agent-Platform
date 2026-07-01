#!/usr/bin/env bash
set -e

# Install CPU-only torch first (slim build, no CUDA).
# The CPU wheel index only publishes recent versions so we use the latest
# stable CPU build instead of pinning 2.2.2.
pip install torch==2.9.0+cpu --index-url https://download.pytorch.org/whl/cpu

# Install everything else — sentence-transformers will see torch already
# present and skip re-downloading it.
pip install -r requirements.txt
