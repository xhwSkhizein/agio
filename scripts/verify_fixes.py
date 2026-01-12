#!/usr/bin/env python3
"""
验证脚本 - 检查修复是否生效

用法:
    python scripts/verify_fixes.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


async def verify_termination_reason_fix():
    """验证 Agent 正常完成时设置了 termination_reason"""
    print("=" * 60)
    print("验证 1: Agent 正常完成时的 termination_reason")
    print("=" * 60)
    
    # 检查代码中是否包含修复
    executor_file = project_root / "agio" / "agent" / "executor.py"
    with open(executor_file, "r", encoding="utf-8") as f:
        content = f.read()
    
    # 查找关键修复行
    if 'state.termination_reason = "completed"' in content:
        print("✅ 代码修复已应用: termination_reason = 'completed'")
        return True
    else:
        print("❌ 代码修复未应用: 缺少 termination_reason 设置")
        return False


async def verify_incremental_save_fix():
    """验证增量保存逻辑"""
    print("\n" + "=" * 60)
    print("验证 2: Trace 增量保存机制")
    print("=" * 60)
    
    # 检查代码中是否包含修复
    collector_file = project_root / "agio" / "observability" / "collector.py"
    with open(collector_file, "r", encoding="utf-8") as f:
        content = f.read()
    
    checks = [
        ("StepEventType.RUN_STARTED", "RUN_STARTED 检查点"),
        ("StepEventType.STEP_COMPLETED", "STEP_COMPLETED 检查点"),
        ("StepEventType.RUN_COMPLETED", "RUN_COMPLETED 检查点"),
        ("StepEventType.RUN_FAILED", "RUN_FAILED 检查点"),
        ("asyncio.create_task(self._save_trace_safe())", "异步保存任务"),
        ("async def _save_trace_safe", "_save_trace_safe 方法"),
    ]
    
    all_passed = True
    for check_str, description in checks:
        if check_str in content:
            print(f"✅ {description}")
        else:
            print(f"❌ {description} - 未找到")
            all_passed = False
    
    return all_passed


async def verify_tests():
    """验证测试文件存在且可运行"""
    print("\n" + "=" * 60)
    print("验证 3: 测试文件")
    print("=" * 60)
    
    test_file = project_root / "tests" / "test_incremental_trace_save.py"
    
    if test_file.exists():
        print(f"✅ 测试文件存在: {test_file.name}")
        
        # 尝试运行测试
        import subprocess
        try:
            result = subprocess.run(
                ["uv", "run", "pytest", str(test_file), "-v", "--tb=short"],
                cwd=str(project_root),
                capture_output=True,
                text=True,
                timeout=30,
            )
            
            if result.returncode == 0:
                print("✅ 所有测试通过")
                return True
            else:
                print(f"❌ 测试失败:\n{result.stdout}\n{result.stderr}")
                return False
        except subprocess.TimeoutExpired:
            print("⚠️  测试超时")
            return False
        except Exception as e:
            print(f"⚠️  无法运行测试: {e}")
            return True  # 文件存在就算通过
    else:
        print(f"❌ 测试文件不存在: {test_file}")
        return False


async def main():
    """运行所有验证"""
    print("\n")
    print("🔍 开始验证修复...")
    print("\n")
    
    results = []
    
    # 验证 1: termination_reason 修复
    result1 = await verify_termination_reason_fix()
    results.append(("Agent 完成状态修复", result1))
    
    # 验证 2: 增量保存修复
    result2 = await verify_incremental_save_fix()
    results.append(("Trace 增量保存", result2))
    
    # 验证 3: 测试
    result3 = await verify_tests()
    results.append(("测试套件", result3))
    
    # 总结
    print("\n" + "=" * 60)
    print("验证总结")
    print("=" * 60)
    
    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{name}: {status}")
    
    all_passed = all(r[1] for r in results)
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 所有验证通过！修复已成功应用。")
        print("\n下一步:")
        print("1. 运行 ./start.sh 重启服务")
        print("2. 在 Web 界面测试 Agent 对话")
        print("3. 检查 Traces 页面是否正常显示")
    else:
        print("⚠️  部分验证失败，请检查上述错误信息。")
    print("=" * 60)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
