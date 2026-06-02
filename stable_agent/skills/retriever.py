"""stable_agent.skills.retriever — SkillRetriever 技能检索。

轻量 BM25 / keyword scoring 检索，不引入重型 embedding。
2 核 2GB 可运行。
"""

from __future__ import annotations

import logging
import math
import re
from collections import Counter
from typing import Any, Optional

from stable_agent.skills.repo import SkillRepo
from stable_agent.skills.schema import SkillMetadata, SkillSearchResult

logger = logging.getLogger(__name__)


class SkillRetriever:
    """技能检索器。

    使用 BM25 + keyword scoring 进行轻量检索。
    不引入重型依赖，2 核 2GB 可运行。

    Attributes:
        repo: SkillRepo 实例。
        top_k: 默认返回数量。
    """

    def __init__(self, repo: SkillRepo, top_k: int = 5) -> None:
        """初始化检索器。

        Args:
            repo: SkillRepo 实例。
            top_k: 默认返回数量。
        """
        self.repo = repo
        self.top_k = top_k

    def search(
        self,
        query: str,
        top_k: int | None = None,
        scope: str | None = None,
    ) -> list[SkillSearchResult]:
        """搜索技能。

        评分规则：
        1. trigger phrase exact match 加权最高 (5.0)
        2. name exact match 加权高 (3.0)
        3. description match 中等 (2.0)
        4. tag match 中等 (2.0)
        5. 最近成功使用过的 skill 加小权重 (0.5)
        6. 最近失败或回滚过的 skill 降权 (-1.0)

        Args:
            query: 搜索查询。
            top_k: 返回数量。
            scope: 过滤作用域。

        Returns:
            搜索结果列表。
        """
        if top_k is None:
            top_k = self.top_k

        if not query or not query.strip():
            return []

        # 获取所有 active skills
        skills = self.repo.list_skills(status="active", limit=1000)
        if not skills:
            return []

        # 分词
        terms = self._tokenize(query)
        if not terms:
            return []

        # 计算 BM25 分数
        results: list[SkillSearchResult] = []
        for skill in skills:
            if scope and skill.scope.value != scope:
                continue

            score, matched_terms, reason = self._score_skill(skill, terms)
            if score > 0:
                results.append(SkillSearchResult(
                    skill_id=skill.skill_id,
                    name=skill.name,
                    description=skill.description,
                    score=score,
                    matched_terms=matched_terms,
                    reason=reason,
                ))

        # 按分数排序
        results.sort(key=lambda x: x.score, reverse=True)
        top_results = results[:top_k]

        # 记录检索 trace
        logger.info(
            "Skill search: query=%r, found=%d, returned=%d",
            query, len(results), len(top_results),
        )

        return top_results

    def _tokenize(self, text: str) -> list[str]:
        """分词。

        简单分词：按空格和标点分割，转小写。
        支持中文字符。
        """
        # 移除多余空格
        text = text.strip().lower()
        # 按空格和标点分割
        tokens = re.findall(r'[\w\u4e00-\u9fff]+', text)
        # 过滤过短的 token
        return [t for t in tokens if len(t) >= 1]

    def _score_skill(
        self,
        skill: SkillMetadata,
        query_terms: list[str],
    ) -> tuple[float, list[str], str]:
        """计算技能匹配分数。

        Args:
            skill: 技能元数据。
            query_terms: 查询词项列表。

        Returns:
            (score, matched_terms, reason) 元组。
        """
        score = 0.0
        matched_terms: list[str] = []
        reasons: list[str] = []

        # 1. trigger phrase exact match (最高权重)
        for phrase in skill.trigger_phrases:
            phrase_lower = phrase.lower()
            for term in query_terms:
                if term in phrase_lower:
                    score += 5.0
                    matched_terms.append(f"trigger:{term}")
                    if "trigger phrase" not in reasons:
                        reasons.append("trigger phrase matched")

        # 2. name match
        name_lower = skill.name.lower().replace("-", " ").replace("_", " ")
        for term in query_terms:
            if term in name_lower:
                score += 3.0
                matched_terms.append(f"name:{term}")
                if "name" not in reasons:
                    reasons.append("name matched")

        # 3. description match
        desc_lower = skill.description.lower()
        for term in query_terms:
            if term in desc_lower:
                score += 2.0
                matched_terms.append(f"desc:{term}")
                if "description" not in reasons:
                    reasons.append("description matched")

        # 4. tags match
        all_tags = (
            skill.tags.topic
            + skill.tags.capabilities
            + skill.tags.concepts
            + skill.tags.heuristics
            + skill.tags.pitfalls
        )
        for tag in all_tags:
            tag_lower = tag.lower()
            for term in query_terms:
                if term in tag_lower:
                    score += 2.0
                    matched_terms.append(f"tag:{term}")
                    if "tag" not in reasons:
                        reasons.append("tag matched")

        # 5. 最近成功使用加权
        if skill.success_count > skill.failure_count:
            score += 0.5
            if "recent success" not in reasons:
                reasons.append("recent success boost")

        # 6. 最近失败降权
        if skill.failure_count > skill.success_count * 2:
            score -= 1.0
            reasons.append("failure penalty")

        # 构建 reason
        reason = "; ".join(reasons) if reasons else "partial match"

        return max(0.0, score), list(set(matched_terms)), reason

    def get_skill_full(self, skill_id: str) -> Optional[dict[str, Any]]:
        """获取技能完整信息。

        检索阶段只读 name/description/tags。
        命中后才读 SKILL.md。
        需要时才读 CHECKLIST/TEMPLATE/scripts。

        Args:
            skill_id: 技能 ID。

        Returns:
            技能完整信息字典。
        """
        metadata = self.repo.get_skill(skill_id)
        if metadata is None:
            return None

        result = metadata.to_dict()

        # 尝试读取 SKILL.md
        skill_dir = metadata.storage_path
        if skill_dir:
            from pathlib import Path
            skill_md = Path(skill_dir) / "SKILL.md"
            if skill_md.exists():
                try:
                    result["skill_md"] = skill_md.read_text(encoding="utf-8")
                except Exception:
                    result["skill_md"] = ""

            # 读取其他文件
            for filename in ["CHECKLIST.md", "TEMPLATE.md", "examples.md"]:
                filepath = Path(skill_dir) / filename
                if filepath.exists():
                    try:
                        result[filename.lower().replace(".", "_")] = filepath.read_text(encoding="utf-8")
                    except Exception:
                        pass

        return result

    def get_skill_summary(self, skill_id: str) -> Optional[str]:
        """获取技能摘要。

        用于注入 context，只包含 name + description + trigger_phrases。

        Args:
            skill_id: 技能 ID。

        Returns:
            技能摘要字符串。
        """
        metadata = self.repo.get_skill(skill_id)
        if metadata is None:
            return None

        parts = [f"Skill: {metadata.name}"]
        if metadata.description:
            parts.append(f"Description: {metadata.description}")
        if metadata.trigger_phrases:
            parts.append(f"Triggers: {', '.join(metadata.trigger_phrases)}")

        return " | ".join(parts)
