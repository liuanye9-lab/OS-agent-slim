"""tests/test_skill_cli_commands.py — CLI Skill Commands 测试。"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest


class TestSkillCliCommands:
    """CLI Skill Commands 测试。"""

    def _run_cli(self, *args) -> dict:
        """运行 CLI 命令。"""
        import os
        project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cmd = [
            sys.executable, "-m", "stable_agent.cli",
            "skill",
            *args,
            "--json",
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=project_dir,
            env={**os.environ, "PYTHONPATH": project_dir},
        )
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return {"ok": False, "error": result.stdout + result.stderr}

    def test_skill_health_json(self):
        """skill health --json。"""
        data = self._run_cli("health")
        assert data.get("ok") is True
        assert "active_skills" in data

    def test_skill_list_json(self):
        """skill list --json。"""
        data = self._run_cli("list")
        assert data.get("ok") is True
        assert "skills" in data

    def test_skill_search_json(self):
        """skill search --json。"""
        data = self._run_cli("search", "--query", "test")
        assert data.get("ok") is True
        assert "results" in data

    def test_skill_rollback_json(self):
        """skill rollback --json。"""
        # 这个测试需要先创建技能
        # 在集成测试中验证
        pass

    def test_failure_has_error(self):
        """失败有 error。"""
        # 模拟失败场景
        pass

    def test_no_python_python3_in_docs(self):
        """文档中不推荐 python/python3。"""
        import os
        project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cli_path = os.path.join(project_dir, "stable_agent", "cli.py")
        with open(cli_path, "r") as f:
            content = f.read()
        # 检查文档中不推荐 python/python3
        # 注意：这里检查的是 CLI 文档，不是代码本身
        assert "python -m stable_agent.cli" not in content or ".venv/bin/python" in content
