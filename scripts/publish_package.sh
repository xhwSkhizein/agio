#!/bin/bash
set -e

REPOSITORY=${1:-testpypi}

if [ "$REPOSITORY" != "pypi" ] && [ "$REPOSITORY" != "testpypi" ]; then
    echo "❌ Invalid repository. Use 'pypi' or 'testpypi'"
    exit 1
fi

echo "📤 Publishing to $REPOSITORY..."

if [ "$REPOSITORY" == "testpypi" ]; then
    echo "⚠️  Publishing to TestPyPI (for testing)"
    python -m twine upload --repository testpypi dist/*
else
    echo "🚀 Publishing to PyPI (production)"
    python -m twine upload dist/*
fi

echo "✅ Published successfully!"
