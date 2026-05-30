#!/usr/bin/env python3
"""Closed-Loop Structural Check.

检查自我优化闭环的关键结构约束，不需要运行服务器。

检查项:
1. 核心模块可导入
2. RunLifecycle 阶段完整
3. SelfImprovementProofLoop 不是 hardcoded validation_passed=True
4. best_skill.md 受 Human Review 保护
5. Dashboard Observer 文件存在
6. 自动化脚本存在
7. 无隐藏 chain-of-thought 字段
"""

from __future__ import annotations

import argparse
import importlib
import inspect
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def check_file_exists(path: str) -> None:
    file_path = ROOT / path
    assert_true(file_path.exists(), f"Missing required file: {path}")
    print(f"  OK {path}")


def check_no_forbidden_fields() -> None:
    print("[CHECK] No hidden chain-of-thought fields")
    forbidden = ["chain_of_thought", "hidden_reasoning", "model_inner_thought"]
    # 只检查生产代码（稳定代码 + web），不检查测试文件
    # 测试文件中使用 chain_of_thought 作为测试输入来验证拦截是合法的
    targets = [
        ROOT / "stable_agent",
        ROOT / "web",
    ]

    violations: list[str] = []

    for target in targets:
        if not target.exists():
            continue
        for file in target.rglob("*"):
            if file.suffix not in {".py", ".js", ".html", ".md"}:
                continue
            lines = file.read_text(encoding="utf-8", errors="ignore").splitlines()
            for i, line in enumerate(lines, 1):
                stripped = line.strip()
                # 跳过注释行
                if stripped.startswith("#") or stripped.startswith("//") or stripped.startswith("<!--"):
                    continue
                for word in forbidden:
                    if word not in stripped:
                        continue
                    # 排除"断言字段不存在"的测试代码和文档说明
                    exclusion_patterns = [
                        f"{word} not in", f"{word}' not in", f'{word}" not in',
                        f"not in {word}", f"no_{word}", f"hides_{word}",
                        f"不含 {word}", f"不包含 {word}", f"不应包含 {word}",
                        f"assert not hasattr",
                    ]
                    if any(pat in stripped for pat in exclusion_patterns):
                        continue
                    # 排除 docstring 中的"不含"/"禁止"说明
                    if "禁止" in stripped and word in stripped:
                        continue
                    violations.append(f"{file.relative_to(ROOT)}:{i} contains {word} in non-comment line: {stripped[:80]}")

    assert_true(not violations, "Forbidden reasoning fields found:\n" + "\n".join(violations))
    print("  OK")


def check_imports() -> None:
    print("[CHECK] Core module imports")

    modules = [
        "stable_agent.runtime.run_lifecycle",
        "stable_agent.memory.temporal_memory_router",
        "stable_agent.context.context_compression_guard",
        "stable_agent.self_improvement.proof_loop",
        "stable_agent.observation.decision_trace_builder",
        "stable_agent.gateway.tool_router",
    ]

    for module_name in modules:
        importlib.import_module(module_name)
        print(f"  OK {module_name}")


def check_run_lifecycle() -> None:
    print("[CHECK] RunLifecycle stages")

    module = importlib.import_module("stable_agent.runtime.run_lifecycle")

    assert_true(hasattr(module, "RunStage"), "RunStage missing")
    assert_true(hasattr(module, "get_stage_meta"), "get_stage_meta missing")

    required = [
        "temporal_memory_retrieving",
        "context_compressing",
        "memory_update_candidate",
        "skill_patch_proposal",
        "validation",
        "human_review",
        "completed",
    ]

    stage_values = [stage.value for stage in module.RunStage]

    for stage in required:
        assert_true(stage in stage_values, f"RunStage missing: {stage}")
        meta = module.get_stage_meta(stage)
        assert_true(hasattr(meta, "progress_pct"), f"progress_pct missing for {stage}")
        assert_true(hasattr(meta, "status_text_zh"), f"status_text_zh missing for {stage}")
        assert_true(hasattr(meta, "avatar_state"), f"avatar_state missing for {stage}")

    print("  OK")


def check_self_improvement_not_stubbed() -> None:
    print("[CHECK] SelfImprovementProofLoop validation is not hardcoded")

    file_path = ROOT / "stable_agent/self_improvement/proof_loop.py"
    assert_true(file_path.exists(), "proof_loop.py missing")

    text = file_path.read_text(encoding="utf-8", errors="ignore")
    forbidden_patterns = [
        "passed = True  #",
        "return True  # stub",
    ]

    found = [pattern for pattern in forbidden_patterns if pattern in text]

    # validation_passed 初始化必须为 False (V8.1)
    has_true_init = "validation_passed = True" in text
    has_false_init = "validation_passed = False" in text

    if has_true_init and not has_false_init:
        found.append("validation_passed = True (no False assignment found → hardcoded!)")

    assert_true(
        not found,
        "SelfImprovementProofLoop still appears stubbed: " + ", ".join(found),
    )

    print("  OK")


def check_best_skill_guard() -> None:
    print("[CHECK] best_skill.md guarded by review")

    possible_files = [
        ROOT / "stable_agent/self_improvement/proof_loop.py",
        ROOT / "stable_agent/saas/skill_review_service.py",
        ROOT / "stable_agent/gateway/unified_tool_registry.py",
    ]

    existing_text = "\n".join(
        file.read_text(encoding="utf-8", errors="ignore")
        for file in possible_files
        if file.exists()
    )

    assert_true("human" in existing_text.lower() or "review" in existing_text.lower(), "No human review wording found around skill export")
    assert_true("best_skill" in existing_text, "No best_skill export logic found")

    print("  OK")


def check_dashboard_observer_files() -> None:
    print("[CHECK] Dashboard Observer files")

    candidates = [
        "web/templates/run_observer.html",
        "web/static/run_observer.js",
        "web/static/avatar_scene.js",
    ]

    for candidate in candidates:
        check_file_exists(candidate)

    print("  OK")


def check_scripts_exist() -> None:
    print("[CHECK] Automation scripts")

    scripts = [
        "scripts/deploy_local.sh",
        "scripts/smoke_test.sh",
        "scripts/integration_test.sh",
        "tools/integration_test.py",
        "tools/check_closed_loop.py",
    ]

    for script in scripts:
        check_file_exists(script)

    print("  OK")


def check_regression_runner_no_cases_fails() -> None:
    print("[CHECK] RegressionValidationRunner no-cases fails")

    file_path = ROOT / "stable_agent/self_improvement/regression_validation_runner.py"
    text = file_path.read_text(encoding="utf-8", errors="ignore")

    assert_true("new_score=0.0" in text, "RegressionValidationRunner should return new_score=0.0 when no cases")
    assert_true("old_score=0.0" not in text or "无法证明" in text,
               "RegressionValidationRunner should fail when no regression cases")
    assert_true("默认通过" not in text, "RegressionValidationRunner should NOT default-pass when no cases")

    print("  OK")


def check_no_private_field_access() -> None:
    """V9.0: 确认不再直接访问 memory_bank._items。"""
    print("[CHECK] No private field access (_items)")

    targets = [
        ROOT / "stable_agent",
    ]

    violations: list[str] = []

    for target in targets:
        if not target.exists():
            continue
        for file in target.rglob("*.py"):
            lines = file.read_text(encoding="utf-8", errors="ignore").splitlines()
            for i, line in enumerate(lines, 1):
                stripped = line.strip()
                # 跳过注释
                if stripped.startswith("#"):
                    continue
                # 检查 memory_bank._items 访问
                if "memory_bank._items" in stripped:
                    # 排除 list_items() 方法定义本身
                    if "def list_items" in stripped:
                        continue
                    # 排除注释/文档
                    if "不要" in stripped or "禁止" in stripped or "不再" in stripped:
                        continue
                    violations.append(f"{file.relative_to(ROOT)}:{i}: memory_bank._items access: {stripped[:80]}")

    assert_true(not violations, "Private field _items still accessed:\n" + "\n".join(violations))
    print("  OK")


def check_approve_no_auto_export() -> None:
    """V9.0: approve_patch 不自动导出 best_skill.md。"""
    print("[CHECK] approve_patch does NOT auto-export best_skill.md")

    file_path = ROOT / "stable_agent/self_improvement/proof_loop.py"
    text = file_path.read_text(encoding="utf-8", errors="ignore")

    # approve_patch 方法内不应调用 _export_best_skill_versioned
    # 找到 approve_patch 方法
    approve_start = text.find("def approve_patch(")
    if approve_start == -1:
        raise AssertionError("approve_patch method not found in proof_loop.py")

    # 找到下一个 def
    next_def = text.find("\n    def ", approve_start + 1)
    approve_body = text[approve_start:next_def] if next_def > 0 else text[approve_start:]

    assert_true("_export_best_skill" not in approve_body,
                "approve_patch should NOT call _export_best_skill_versioned anymore")

    # 必须有 export_approved_patch 方法
    assert_true("def export_approved_patch(" in text,
                "export_approved_patch method must exist")

    print("  OK")


def check_event_sync_health_in_result() -> None:
    """V9.0: os_agent 结果包含 event_sync_ok / emitted_event_count / sync_errors。"""
    print("[CHECK] os_agent result has event_sync_ok fields")

    file_path = ROOT / "stable_agent/gateway/unified_tool_registry.py"
    text = file_path.read_text(encoding="utf-8", errors="ignore")

    assert_true("emitted_event_count" in text, "Missing emitted_event_count in unified_tool_registry.py")
    assert_true("event_sync_ok" in text, "Missing event_sync_ok in unified_tool_registry.py")
    assert_true("sync_errors" in text, "Missing sync_errors in unified_tool_registry.py")

    print("  OK")


def check_memory_bank_list_items() -> None:
    """V9.0: MemoryBank 有 list_items() 方法。"""
    print("[CHECK] MemoryBank.list_items() method exists")

    file_path = ROOT / "stable_agent/memory_router.py"
    text = file_path.read_text(encoding="utf-8", errors="ignore")

    assert_true("def list_items(" in text, "MemoryBank must have list_items() method")

    print("  OK")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.parse_args()

    try:
        check_imports()
        check_run_lifecycle()
        check_self_improvement_not_stubbed()
        check_best_skill_guard()
        check_regression_runner_no_cases_fails()
        check_dashboard_observer_files()
        check_scripts_exist()
        check_no_forbidden_fields()
        # V9.0: 新增检查
        check_no_private_field_access()
        check_approve_no_auto_export()
        check_event_sync_health_in_result()
        check_memory_bank_list_items()

    except AssertionError as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"[ERROR] Unexpected error: {exc}", file=sys.stderr)
        return 1

    print("")
    print("[PASS] Closed-loop structural checks completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
