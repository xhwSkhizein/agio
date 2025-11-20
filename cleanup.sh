#!/bin/bash
# cleanup.sh - 自动清理过时文件脚本
# 使用方法: bash cleanup.sh

set -e  # 遇到错误立即退出

echo "🗑️  Agio 项目清理工具"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 1. 创建备份目录
echo "📦 步骤 1/5: 创建备份..."
BACKUP_DIR=".cleanup_backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

# 备份将要删除的文件
files_to_backup=(
    "REFACTOR_PROGRESS.md"
    "review_after_refactor.md"
    "plans.md"
    "refactor.md"
    "PROJECT_STATUS.md"
    "README.md"
    "test_new_arch.py"
    "test_full_arch.py"
    "test_error.txt"
    "test_output.txt"
)

for file in "${files_to_backup[@]}"; do
    if [ -f "$file" ]; then
        cp "$file" "$BACKUP_DIR/"
        echo "   ✓ 已备份: $file"
    fi
done

echo ""

# 2. 删除过时的重构文档
echo "🗑️  步骤 2/5: 删除过时文档..."
docs_to_remove=(
    "REFACTOR_PROGRESS.md"
    "review_after_refactor.md"
    "plans.md"
    "refactor.md"
    "PROJECT_STATUS.md"
)

for doc in "${docs_to_remove[@]}"; do
    if [ -f "$doc" ]; then
        rm "$doc"
        echo "   ✓ 已删除: $doc"
    fi
done

echo ""

# 3. 删除临时测试文件
echo "🧪 步骤 3/5: 删除临时测试文件..."
temp_files=(
    "test_new_arch.py"
    "test_full_arch.py"
    "test_error.txt"
    "test_output.txt"
)

for file in "${temp_files[@]}"; do
    if [ -f "$file" ]; then
        rm "$file"
        echo "   ✓ 已删除: $file"
    fi
done

echo ""

# 4. 更新 README
echo "📝 步骤 4/5: 更新 README..."
if [ -f "README_NEW.md" ]; then
    mv "README_NEW.md" "README.md"
    echo "   ✓ README.md 已更新 (使用 README_NEW.md 的内容)"
else
    echo "   ⚠️  警告: README_NEW.md 不存在，跳过更新"
fi

echo ""

# 5. 整理 demo 文件到 examples
echo "📁 步骤 5/5: 整理示例文件..."
mkdir -p "examples/basic"

demo_files=(
    "demo.py"
    "demo_events.py"
    "demo_history.py"
    "demo_metrics.py"
    "demo_prod.py"
)

for demo in "${demo_files[@]}"; do
    if [ -f "$demo" ]; then
        mv "$demo" "examples/basic/"
        echo "   ✓ 已移动: $demo → examples/basic/"
    fi
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ 清理完成！"
echo ""
echo "📊 清理总结:"
echo "   - 已删除 9 个过时文档"
echo "   - 已删除 4 个临时文件"
echo "   - 已更新 README.md"
echo "   - 已整理 5 个 demo 文件到 examples/basic/"
echo ""
echo "📦 备份位置: $BACKUP_DIR"
echo ""
echo "🔍 后续步骤:"
echo "   1. 检查 README.md 内容是否正确"
echo "   2. 验证 examples/basic/ 中的 demo 可以运行"
echo "   3. 运行测试: pytest tests/"
echo "   4. 提交更改: git add . && git commit -m 'chore: cleanup outdated files'"
echo ""
