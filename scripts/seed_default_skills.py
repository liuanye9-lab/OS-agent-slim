#!/usr/bin/env python3
"""seed_default_skills.py — 生成默认种子技能。

用法:
    PYTHONPATH=. .venv/bin/python scripts/seed_default_skills.py
    PYTHONPATH=. .venv/bin/python -m stable_agent.cli skill seed --default
"""

from __future__ import annotations

import json
import os
import sys

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from stable_agent.skills.repo import SkillRepo
from stable_agent.skills.schema import (
    RiskLevel,
    SkillMetadata,
    SkillScope,
    SkillTags,
)
from stable_agent.skills.package_manager import SkillPackageManager


# 默认种子技能定义
DEFAULT_SKILLS = [
    {
        "name": "avoid-over-editing",
        "description": "当 coding agent 执行代码修改任务时，避免大范围重构无关文件，只做最小必要变更。",
        "trigger_phrases": [
            "不要大范围重构",
            "不要重构无关文件",
            "只改必要的",
            "最小变更",
            "minimal change",
            "avoid over-editing",
        ],
        "tags": SkillTags(
            topic=["coding", "refactoring"],
            capabilities=["code-editing", "minimal-change"],
            heuristics=["minimal-diff"],
            pitfalls=["global-refactor", "unnecessary-changes"],
        ),
        "risk_level": RiskLevel.LOW,
        "skill_md": """---
name: avoid-over-editing
description: 当 coding agent 执行代码修改任务时，避免大范围重构无关文件，只做最小必要变更。
scope: global
risk_level: low
---

# Skill: Avoid Over Editing

## When to use
当任务要求修复 bug、补齐功能、局部优化时使用。

## Procedure
1. 先定位相关文件。
2. 只修改必要文件。
3. 不主动重构无关模块。
4. 修改后输出 changed files。
5. 运行最小相关测试。

## Pitfalls
- 不要因为发现代码风格不统一就全局重构。
- 不要修改无关 README 或格式化整个项目。

## Verification
- git diff 只包含相关文件。
- 测试通过。
- 用户原始需求没有被扩大。
""",
    },
    {
        "name": "preserve-project-structure",
        "description": "保持原项目结构，不随意移动目录。",
        "trigger_phrases": [
            "保持项目结构",
            "不要移动目录",
            "不要改目录",
            "preserve structure",
        ],
        "tags": SkillTags(
            topic=["project-management", "structure"],
            capabilities=["directory-management"],
            heuristics=["keep-structure"],
            pitfalls=["move-directories", "rename-folders"],
        ),
        "risk_level": RiskLevel.LOW,
        "skill_md": """---
name: preserve-project-structure
description: 保持原项目结构，不随意移动目录。
scope: global
risk_level: low
---

# Skill: Preserve Project Structure

## When to use
当在现有项目中工作时，保持目录结构不变。

## Procedure
1. 先了解现有项目结构。
2. 新文件放在合适的现有目录中。
3. 不移动现有文件或目录。
4. 如果必须重组，先询问用户。

## Pitfalls
- 不要因为"看起来更合理"就移动文件。
- 不要创建新的顶层目录。

## Verification
- 目录结构未改变（除非用户要求）。
- 新文件在正确位置。
""",
    },
    {
        "name": "output-change-summary",
        "description": "每次代码任务后输出修改文件、原因、测试结果。",
        "trigger_phrases": [
            "输出修改摘要",
            "变更摘要",
            "change summary",
            "what changed",
        ],
        "tags": SkillTags(
            topic=["reporting", "documentation"],
            capabilities=["change-tracking"],
            heuristics=["summary-after-work"],
        ),
        "risk_level": RiskLevel.LOW,
        "skill_md": """---
name: output-change-summary
description: 每次代码任务后输出修改文件、原因、测试结果。
scope: global
risk_level: low
---

# Skill: Output Change Summary

## When to use
每次完成代码修改任务后。

## Procedure
1. 列出所有修改的文件。
2. 说明每个文件的修改原因。
3. 运行相关测试并报告结果。
4. 如果有未完成的部分，说明原因。

## Verification
- 用户能清楚知道改了什么。
- 测试结果已报告。
""",
    },
    {
        "name": "no-ai-flavor-writing",
        "description": "避免模板化表达，保持克制，减少空泛营销腔。",
        "trigger_phrases": [
            "不要AI味",
            "不要ai味",
            "避免模板化",
            "不要营销腔",
            "保持克制",
            "no AI flavor",
            "avoid AI tone",
        ],
        "tags": SkillTags(
            topic=["writing", "style"],
            capabilities=["natural-writing"],
            concepts=["tone-control", "authenticity"],
            heuristics=["concise", "direct", "no-filler"],
            pitfalls=["template-words", "marketing-speak", "empty-phrases"],
        ),
        "risk_level": RiskLevel.LOW,
        "skill_md": """---
name: no-ai-flavor-writing
description: 避免模板化表达，保持克制，减少空泛营销腔。
scope: global
risk_level: low
---

# Skill: No AI Flavor Writing

## When to use
当用户说"不要AI味"或类似表达时。

## Procedure
1. 不使用"Great question!"、"I'd be happy to help!"等开场白。
2. 不使用"首先...其次...最后..."等模板结构。
3. 直接陈述事实和观点。
4. 用具体数据替代空泛描述。
5. 保持简洁，不重复用户已知信息。

## Pitfalls
- 不要用"让我们一起..."、"在这个充满挑战的时代..."。
- 不要过度使用 emoji。
- 不要每段都以"此外"、"另外"开头。

## Verification
- 文本读起来像人写的，不是 AI 生成的。
- 没有空泛的营销腔。
- 信息密度高，没有废话。
""",
    },
    {
        "name": "minimal-test-first",
        "description": "优先运行最小相关测试，不盲目全量跑重测试。",
        "trigger_phrases": [
            "最小测试",
            "运行相关测试",
            "不要全量测试",
            "minimal test",
        ],
        "tags": SkillTags(
            topic=["testing", "efficiency"],
            capabilities=["test-selection"],
            heuristics=["fast-feedback"],
            pitfalls=["full-test-suite", "slow-ci"],
        ),
        "risk_level": RiskLevel.LOW,
        "skill_md": """---
name: minimal-test-first
description: 优先运行最小相关测试，不盲目全量跑重测试。
scope: global
risk_level: low
---

# Skill: Minimal Test First

## When to use
当需要验证代码修改时。

## Procedure
1. 识别修改影响的模块。
2. 只运行相关模块的测试。
3. 如果相关测试通过，再考虑扩展测试范围。
4. 不要在每次小修改后都运行完整测试套件。

## Pitfalls
- 不要因为"保险起见"就运行所有测试。
- 不要在开发过程中等待长时间的 CI。

## Verification
- 测试运行时间合理。
- 相关功能已验证。
""",
    },
    {
        "name": "mcp-cli-fallback",
        "description": "MCP 失败时使用 .venv/bin/python CLI fallback，禁止 python/python3。",
        "trigger_phrases": [
            "MCP 失败",
            "MCP fallback",
            "CLI fallback",
            "python fallback",
        ],
        "tags": SkillTags(
            topic=["mcp", "cli", "fallback"],
            capabilities=["error-recovery"],
            concepts=["tool-routing"],
            heuristics=["venv-python"],
            pitfalls=["system-python", "python3-command"],
        ),
        "risk_level": RiskLevel.LOW,
        "skill_md": """---
name: mcp-cli-fallback
description: MCP 失败时使用 .venv/bin/python CLI fallback，禁止 python/python3。
scope: global
risk_level: low
---

# Skill: MCP CLI Fallback

## When to use
当 MCP 工具调用失败时。

## Procedure
1. 检查 MCP 错误信息。
2. 使用 CLI fallback：
   PYTHONPATH=. .venv/bin/python -m stable_agent.cli <command>
3. 禁止使用 python 或 python3（会调用系统 Python 3.9）。

## Pitfalls
- 不要使用 `python` 或 `python3`。
- 必须使用 `.venv/bin/python`。

## Verification
- CLI 命令使用正确的 Python 解释器。
- 返回正确的 JSON 输出。
""",
    },
    {
        "name": "openclaw-slim-safe-mode",
        "description": "2c2g 云端只做 control plane，不做重型推理。",
        "trigger_phrases": [
            "2c2g",
            "2核2G",
            "slim mode",
            "云端轻量",
            "openclaw",
        ],
        "tags": SkillTags(
            topic=["deployment", "cloud", "slim"],
            capabilities=["resource-optimization"],
            concepts=["control-plane", "lightweight"],
            heuristics=["no-local-llm", "external-api"],
            pitfalls=["heavy-model", "docker-compose", "dev-server"],
        ),
        "risk_level": RiskLevel.LOW,
        "skill_md": """---
name: openclaw-slim-safe-mode
description: 2c2g 云端只做 control plane，不做重型推理。
scope: global
risk_level: low
---

# Skill: OpenClaw Slim Safe Mode

## When to use
当部署到 2 核 2GB 云服务器时。

## Procedure
1. 使用生产构建，不用 npm run dev。
2. 使用 PM2/systemd 管理进程。
3. 不跑本地大模型。
4. 不用大型 Docker Compose。
5. 外部 LLM API 替代本地推理。
6. 配置日志轮转和健康检查。

## Pitfalls
- 不要在 2c2g 上跑 Qwen3-8B。
- 不要启动多个常驻服务。
- 不要用 dev server 当生产服务。

## Verification
- 内存使用 < 1.5GB。
- CPU 使用 < 80%。
- 服务稳定运行。
""",
    },
]


def seed_default_skills(skills_dir: str | None = None) -> int:
    """生成默认种子技能。

    Args:
        skills_dir: 技能库目录。

    Returns:
        创建的技能数量。
    """
    repo = SkillRepo(skills_dir=skills_dir)
    pm = SkillPackageManager()

    count = 0
    for skill_def in DEFAULT_SKILLS:
        name = skill_def["name"]

        # 检查是否已存在
        existing = repo.search_metadata(name, top_k=1)
        if existing and existing[0]["name"] == name:
            print(f"  [skip] {name} (already exists)")
            continue

        # 创建 metadata
        metadata = SkillMetadata(
            skill_id=f"skill_{name.replace('-', '_')}",
            name=name,
            description=skill_def["description"],
            scope=SkillScope.GLOBAL,
            tags=skill_def["tags"],
            trigger_phrases=skill_def["trigger_phrases"],
            risk_level=skill_def["risk_level"],
            created_by="seed",
        )

        # 插入 repo
        repo.insert_skill(metadata, reason="default seed skill")

        # 创建 package
        pm.create_package(
            skill_id=metadata.skill_id,
            metadata=metadata,
            skill_md=skill_def.get("skill_md", ""),
        )

        count += 1
        print(f"  [created] {name} ({metadata.skill_id})")

    return count


def main() -> None:
    """主入口。"""
    print("Seeding default skills...")
    count = seed_default_skills()
    print(f"\nDone. Created {count} skills.")


if __name__ == "__main__":
    main()
