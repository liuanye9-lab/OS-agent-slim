#!/usr/bin/env python3
"""StableAgent V11 CLI — 胶囊管理命令行工具。

Usage:
    python -m stable_agent.cli capsule init
    python -m stable_agent.cli capsule status
    python -m stable_agent.cli capsule doctor
    python -m stable_agent.cli capsule export [output.zip]
    python -m stable_agent.cli capsule import <zip_path> [--target PATH]
    python -m stable_agent.cli memory health
    python -m stable_agent.cli token summary [--days 7]
    python -m stable_agent.cli mcp config
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def cmd_capsule_init(args: argparse.Namespace) -> None:
    """初始化胶囊。"""
    from stable_agent.capsule.capsule_manager import CapsuleManager, get_default_capsule_path
    path = args.path or str(get_default_capsule_path())
    manifest = CapsuleManager.create_capsule(path)
    print(f"胶囊已创建: {path}")
    print(f"  capsule_id: {manifest.capsule_id}")
    print(f"  schema_version: {manifest.schema_version}")


def cmd_capsule_status(args: argparse.Namespace) -> None:
    """查看胶囊状态。"""
    from stable_agent.capsule.capsule_manager import CapsuleManager, get_default_capsule_path
    path = args.path or str(get_default_capsule_path())
    status = CapsuleManager.get_capsule_status(path)
    print(json.dumps(status, ensure_ascii=False, indent=2))


def cmd_capsule_doctor(args: argparse.Namespace) -> None:
    """胶囊健康检查。"""
    from stable_agent.capsule.capsule_doctor import CapsuleDoctor
    from stable_agent.capsule.capsule_manager import get_default_capsule_path
    path = args.path or str(get_default_capsule_path())
    report = CapsuleDoctor.check(path)
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    if not report.ok:
        print(f"\n健康分数: {report.health_score:.2f} (有错误)")
        sys.exit(1)
    else:
        print(f"\n健康分数: {report.health_score:.2f}")


def cmd_capsule_export(args: argparse.Namespace) -> None:
    """导出胶囊为 ZIP。"""
    from stable_agent.capsule.import_export import CapsuleImportExport
    from stable_agent.capsule.capsule_manager import get_default_capsule_path
    capsule_path = args.path or str(get_default_capsule_path())
    output = args.output or "capsule_export.zip"
    result = CapsuleImportExport.export_capsule(capsule_path, output)
    print(f"胶囊已导出: {result}")


def cmd_capsule_import(args: argparse.Namespace) -> None:
    """从 ZIP 导入胶囊。"""
    from stable_agent.capsule.import_export import CapsuleImportExport
    from stable_agent.capsule.capsule_manager import get_default_capsule_path
    zip_path = args.zip_path
    target = args.target or str(get_default_capsule_path())
    manifest = CapsuleImportExport.import_capsule(zip_path, target)
    print(f"胶囊已导入: {target}")
    print(f"  capsule_id: {manifest.capsule_id}")


def cmd_memory_health(args: argparse.Namespace) -> None:
    """记忆健康报告。"""
    from stable_agent.capsule.memory_lifecycle import MemoryLifecycleManager
    from stable_agent.capsule.capsule_manager import get_default_capsule_path
    path = Path(args.path or str(get_default_capsule_path()))
    mgr = MemoryLifecycleManager(capsule_path=path)
    report = mgr.generate_memory_health_report()
    print(json.dumps(report, ensure_ascii=False, indent=2))


def cmd_token_summary(args: argparse.Namespace) -> None:
    """Token 使用摘要。"""
    from stable_agent.token.budget_ledger import BudgetLedger
    ledger = BudgetLedger()
    summary = ledger.summarize_period(days=args.days)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def cmd_mcp_config(args: argparse.Namespace) -> None:
    """输出 MCP 配置。"""
    config = {
        "mcpServers": {
            "stableagent": {
                "url": "http://127.0.0.1:8000/mcp"
            }
        }
    }
    print(json.dumps(config, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="stableagent",
        description="StableAgent V11 — Agent Capsule 管理工具",
    )
    subparsers = parser.add_subparsers(dest="command")

    # capsule
    cap_parser = subparsers.add_parser("capsule", help="胶囊管理")
    cap_sub = cap_parser.add_subparsers(dest="action")

    init_p = cap_sub.add_parser("init", help="初始化胶囊")
    init_p.add_argument("--path", help="胶囊路径")
    init_p.set_defaults(func=cmd_capsule_init)

    status_p = cap_sub.add_parser("status", help="查看状态")
    status_p.add_argument("--path", help="胶囊路径")
    status_p.set_defaults(func=cmd_capsule_status)

    doctor_p = cap_sub.add_parser("doctor", help="健康检查")
    doctor_p.add_argument("--path", help="胶囊路径")
    doctor_p.set_defaults(func=cmd_capsule_doctor)

    export_p = cap_sub.add_parser("export", help="导出为 ZIP")
    export_p.add_argument("output", nargs="?", help="输出文件路径")
    export_p.add_argument("--path", help="胶囊路径")
    export_p.set_defaults(func=cmd_capsule_export)

    import_p = cap_sub.add_parser("import", help="从 ZIP 导入")
    import_p.add_argument("zip_path", help="ZIP 文件路径")
    import_p.add_argument("--target", help="目标路径")
    import_p.set_defaults(func=cmd_capsule_import)

    # memory
    mem_parser = subparsers.add_parser("memory", help="记忆管理")
    mem_sub = mem_parser.add_subparsers(dest="action")

    health_p = mem_sub.add_parser("health", help="记忆健康报告")
    health_p.add_argument("--path", help="胶囊路径")
    health_p.set_defaults(func=cmd_memory_health)

    # token
    tok_parser = subparsers.add_parser("token", help="Token 管理")
    tok_sub = tok_parser.add_subparsers(dest="action")

    summary_p = tok_sub.add_parser("summary", help="Token 使用摘要")
    summary_p.add_argument("--days", type=int, default=7, help="统计天数")
    summary_p.set_defaults(func=cmd_token_summary)

    # mcp
    mcp_parser = subparsers.add_parser("mcp", help="MCP 配置")
    mcp_sub = mcp_parser.add_subparsers(dest="action")

    config_p = mcp_sub.add_parser("config", help="输出 MCP 配置")
    config_p.set_defaults(func=cmd_mcp_config)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    if hasattr(args, "func"):
        args.func(args)
    else:
        print(f"请指定子命令: {args.command} <action>")
        sys.exit(1)


if __name__ == "__main__":
    main()
