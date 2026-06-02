"""stable_agent/skills/markdown.py — Skill Markdown 解析/写入。

每个 skill 是 markdown + YAML frontmatter。
"""

from __future__ import annotations

import re
import time
from typing import Any

from stable_agent.skills.models import SkillRecord, SkillStatus


def parse_skill_markdown(content: str) -> SkillRecord:
    """从 markdown 内容解析 SkillRecord。

    Args:
        content: markdown 内容 (含 YAML frontmatter)。

    Returns:
        SkillRecord 实例。
    """
    record = SkillRecord()

    # 解析 YAML frontmatter
    fm_match = re.match(r'^---\n(.*?)\n---\n', content, re.DOTALL)
    if fm_match:
        fm_text = fm_match.group(1)
        content = content[fm_match.end():]

        # 简单解析 YAML (不依赖 pyyaml)
        for line in fm_text.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if ':' in line:
                key, _, value = line.partition(':')
                key = key.strip()
                value = value.strip().strip('"').strip("'")

                if key == 'skill_id':
                    record.skill_id = value
                elif key == 'version':
                    try:
                        record.version = int(value)
                    except ValueError:
                        pass
                elif key == 'status':
                    try:
                        record.status = SkillStatus(value)
                    except ValueError:
                        pass
                elif key == 'domain':
                    record.domain = value
                elif key == 'owner':
                    record.owner = value
                elif key == 'created_at':
                    record.created_at = value
                elif key == 'updated_at':
                    record.updated_at = value
                elif key == 'risk_level':
                    record.risk_level = value

        # 解析列表字段
        record.retrieval_tags = _extract_yaml_list(fm_text, 'retrieval_tags')
        record.task_types = _extract_yaml_list(fm_text, 'task_types')
        record.source_runs = _extract_yaml_list(fm_text, 'source_runs')

    # 解析 markdown sections
    sections = _split_sections(content)
    record.intent = sections.get('Intent', '')
    record.procedure = sections.get('Procedure', '')
    record.guardrails = sections.get('Guardrails', '')
    record.positive_examples = sections.get('Positive examples', '')
    record.negative_examples = sections.get('Negative examples', '')
    record.patch_history = sections.get('Patch history', '')

    return record


def render_skill_markdown(record: SkillRecord) -> str:
    """将 SkillRecord 渲染为 markdown。

    Args:
        record: Skill 记录。

    Returns:
        markdown 内容 (含 YAML frontmatter)。
    """
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    if not record.created_at:
        record.created_at = now
    record.updated_at = now

    # YAML frontmatter
    lines = [
        '---',
        f'skill_id: {record.skill_id}',
        f'version: {record.version}',
        f'status: {record.status}',
        f'domain: {record.domain}',
        f'owner: {record.owner}',
        f'created_at: {record.created_at}',
        f'updated_at: {record.updated_at}',
        f'risk_level: {record.risk_level}',
    ]

    if record.retrieval_tags:
        lines.append('retrieval_tags:')
        for tag in record.retrieval_tags:
            lines.append(f'  - {tag}')

    if record.task_types:
        lines.append('task_types:')
        for tt in record.task_types:
            lines.append(f'  - {tt}')

    if record.source_runs:
        lines.append('source_runs:')
        for run in record.source_runs:
            lines.append(f'  - {run}')

    lines.append('---')
    lines.append('')

    # Markdown sections
    if record.intent:
        lines.append('# Intent')
        lines.append(record.intent)
        lines.append('')

    if record.procedure:
        lines.append('# Procedure')
        lines.append(record.procedure)
        lines.append('')

    if record.guardrails:
        lines.append('# Guardrails')
        lines.append(record.guardrails)
        lines.append('')

    if record.positive_examples:
        lines.append('# Positive examples')
        lines.append(record.positive_examples)
        lines.append('')

    if record.negative_examples:
        lines.append('# Negative examples')
        lines.append(record.negative_examples)
        lines.append('')

    if record.patch_history:
        lines.append('# Patch history')
        lines.append(record.patch_history)
        lines.append('')

    return '\n'.join(lines)


def _extract_yaml_list(text: str, key: str) -> list[str]:
    """从 YAML 文本中提取列表字段。"""
    pattern = rf'{key}:\s*\n((?:\s+-\s+.+\n?)*)'
    match = re.search(pattern, text)
    if not match:
        return []
    items = []
    for line in match.group(1).split('\n'):
        line = line.strip()
        if line.startswith('- '):
            items.append(line[2:].strip().strip('"').strip("'"))
    return items


def _split_sections(content: str) -> dict[str, str]:
    """将 markdown 内容按 # 标题分割为 sections。"""
    sections: dict[str, str] = {}
    current_section = None
    current_content: list[str] = []

    for line in content.split('\n'):
        if line.startswith('# '):
            if current_section:
                sections[current_section] = '\n'.join(current_content).strip()
            current_section = line[2:].strip()
            current_content = []
        else:
            current_content.append(line)

    if current_section:
        sections[current_section] = '\n'.join(current_content).strip()

    return sections
