#!/bin/bash
# 
# 旧系统完全删除脚本
# 警告: 此脚本会永久删除旧代码，不可逆！
#
# 使用方法:
#   1. 审查 complete_removal_plan.md
#   2. 创建备份: git checkout -b backup-old-system
#   3. 运行此脚本: bash scripts/remove_old_system.sh --dry-run
#   4. 确认无误后: bash scripts/remove_old_system.sh --execute
#

set -e  # 遇到错误立即退出

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

DRY_RUN=true

# 解析参数
if [ "$1" == "--execute" ]; then
    DRY_RUN=false
    echo -e "${RED}⚠️  执行模式：将真实删除文件！${NC}"
    read -p "确认继续? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        echo "已取消"
        exit 0
    fi
else
    echo -e "${YELLOW}🔍 预览模式：不会实际删除文件${NC}"
    echo "使用 --execute 参数来真实执行"
    echo ""
fi

# 统计
DELETED_FILES=0
CLEANED_FILES=0

# 删除文件函数
delete_file() {
    local file=$1
    if [ -f "$file" ]; then
        if [ "$DRY_RUN" = true ]; then
            echo -e "${YELLOW}[预览] 将删除:${NC} $file"
        else
            rm "$file"
            echo -e "${RED}[已删除]${NC} $file"
        fi
        ((DELETED_FILES++))
    else
        echo -e "${YELLOW}[跳过] 文件不存在:${NC} $file"
    fi
}

# 清理代码函数
clean_file() {
    local file=$1
    local description=$2
    if [ -f "$file" ]; then
        echo -e "${GREEN}[需清理]${NC} $file - $description"
        ((CLEANED_FILES++))
    fi
}

echo "========================================"
echo "  旧系统删除脚本"
echo "========================================"
echo ""

# ============================================
# Phase 1: 删除旧协议层
# ============================================
echo -e "${GREEN}Phase 1: 删除旧协议层${NC}"
echo "----------------------------------------"
delete_file "agio/protocol/events.py"
echo ""

# ============================================
# Phase 2: 删除旧执行层
# ============================================
echo -e "${GREEN}Phase 2: 删除旧执行层${NC}"
echo "----------------------------------------"
delete_file "agio/execution/agent_executor.py"
delete_file "agio/execution/checkpoint.py"
delete_file "agio/execution/resume.py"
echo ""

# ============================================
# Phase 3: 删除旧 Runner 层
# ============================================
echo -e "${GREEN}Phase 3: 删除旧 Runner 层${NC}"
echo "----------------------------------------"
delete_file "agio/runners/base.py"
delete_file "agio/runners/context.py"
delete_file "agio/runners/state_tracker.py"
echo ""

# ============================================
# Phase 4: 删除旧 Domain 模型
# ============================================
echo -e "${GREEN}Phase 4: 删除旧 Domain 模型${NC}"
echo "----------------------------------------"
delete_file "agio/domain/messages.py"
echo ""

# ============================================
# Phase 5: 需要手动清理的文件
# ============================================
echo -e "${GREEN}Phase 5: 需要手动清理的文件${NC}"
echo "----------------------------------------"
clean_file "agio/agent/base.py" "删除 arun(), arun_stream(), get_run_history()"
clean_file "agio/db/repository.py" "删除所有 Event 相关方法"
clean_file "agio/db/mongo.py" "删除 events_collection 和相关操作"
clean_file "agio/execution/fork.py" "删除 ForkManager 类"
clean_file "agio/protocol/__init__.py" "删除 AgentEvent, EventType 导出"
clean_file "agio/api/routes/chat.py" "更新为使用 StepRunner"
echo ""

# ============================================
# Phase 6: 移动文档到归档
# ============================================
echo -e "${GREEN}Phase 6: 归档旧文档${NC}"
echo "----------------------------------------"
if [ "$DRY_RUN" = false ]; then
    mkdir -p docs/archive
    if [ -f "refactor_core.md" ]; then
        mv refactor_core.md docs/archive/
        echo -e "${GREEN}[已移动]${NC} refactor_core.md → docs/archive/"
    fi
    if [ -f "core_concepts_explained.md" ]; then
        mv core_concepts_explained.md docs/archive/
        echo -e "${GREEN}[已移动]${NC} core_concepts_explained.md → docs/archive/"
    fi
else
    echo -e "${YELLOW}[预览] 将创建:${NC} docs/archive/"
    echo -e "${YELLOW}[预览] 将移动:${NC} refactor_core.md → docs/archive/"
    echo -e "${YELLOW}[预览] 将移动:${NC} core_concepts_explained.md → docs/archive/"
fi
echo ""

# ============================================
# 总结
# ============================================
echo "========================================"
echo "  删除总结"
echo "========================================"
echo -e "完全删除的文件: ${RED}$DELETED_FILES${NC}"
echo -e "需要手动清理: ${YELLOW}$CLEANED_FILES${NC}"
echo ""

if [ "$DRY_RUN" = true ]; then
    echo -e "${YELLOW}这是预览模式，没有实际删除任何文件${NC}"
    echo ""
    echo "下一步:"
    echo "  1. 审查上述输出"
    echo "  2. 创建备份: git checkout -b backup-old-system && git commit -am 'Backup'"
    echo "  3. 执行删除: bash scripts/remove_old_system.sh --execute"
else
    echo -e "${GREEN}✅ 文件删除完成！${NC}"
    echo ""
    echo "下一步:"
    echo "  1. 手动清理上述 $CLEANED_FILES 个文件中的旧代码"
    echo "  2. 运行测试: pytest tests/ -v"
    echo "  3. 修复所有导入错误"
    echo "  4. 提交更改: git commit -am 'Remove old system'"
fi
echo ""
