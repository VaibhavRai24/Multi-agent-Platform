#!/usr/bin/env bash
set -e

# Install CPU-only torch first (slim ~200MB vs full ~800MB GPU version).
# This prevents the default pip resolution from pulling the CUDA build,
# which causes OOM on Render's free tier during build.
pip install torch==2.2.2 --index-url https://download.pytorch.org/whl/cpu

# Now install everything else (sentence-transformers will see torch already
# installed and skip re-downloading it).
pip install -r requirements.txt
