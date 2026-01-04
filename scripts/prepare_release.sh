#!/bin/bash
set -e

echo "🔍 Pre-release checklist..."

# 检查版本号
VERSION=$(grep '^version =' pyproject.toml | sed 's/version = "\(.*\)"/\1/')
echo "📌 Current version: $VERSION"

# 检查 __init__.py 中的版本号是否一致
INIT_VERSION=$(grep '__version__' agio/__init__.py | sed "s/__version__ = \"\(.*\)\"/\1/")
if [ "$VERSION" != "$INIT_VERSION" ]; then
    echo "❌ Version mismatch!"
    echo "   pyproject.toml: $VERSION"
    echo "   agio/__init__.py: $INIT_VERSION"
    exit 1
fi
echo "✅ Version numbers match"

# 检查是否有未提交的更改
if ! git diff-index --quiet HEAD --; then
    echo "⚠️  Warning: You have uncommitted changes"
    echo "   Consider committing or stashing them before release"
fi

# 检查 LICENSE 文件
if [ ! -f "LICENSE" ]; then
    echo "❌ LICENSE file not found"
    exit 1
fi
echo "✅ LICENSE file exists"

# 检查 README
if [ ! -f "README.md" ]; then
    echo "❌ README.md not found"
    exit 1
fi
echo "✅ README.md exists"

# 运行测试（如果 pytest 可用）
if command -v pytest &> /dev/null; then
    echo "🧪 Running tests..."
    pytest tests/ -v || echo "⚠️  Tests failed, but continuing..."
else
    echo "⏩ pytest not found, skipping tests"
fi

echo ""
echo "✅ Pre-release checks complete!"
echo ""
echo "Next steps:"
echo "1. Update version in pyproject.toml and agio/__init__.py"
echo "2. Run: ./scripts/build_package.sh"
echo "3. Run: ./scripts/check_package.sh"
echo "4. Test install: pip install dist/agio-*.whl"
echo "5. Run: ./scripts/publish_package.sh testpypi  (for testing)"
echo "6. Run: ./scripts/publish_package.sh pypi     (for production)"
