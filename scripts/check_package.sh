#!/bin/bash
set -e

echo "🔍 Checking package..."

python -m pip install --upgrade twine check-wheel-contents

echo "📋 Checking package metadata..."
python -m twine check dist/*

echo "✅ Package check complete!"
