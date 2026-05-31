"""表达习惯管理器。

管理用户的表达习惯 (ExpressionProfile)，支持:
- 添加/删除/列出表达习惯
- 匹配文本中的已知表达
- 持久化到 JSON 文件

用法::

    manager = ExpressionProfileManager("/path/to/expressions.json")
    manager.add_expression("继续优化", ["需要项目上下文继续改进"], scope="global")
    matches = manager.match_expressions("继续优化这个项目")
"""

from __future__ import annotations

import json
import os
from typing import Optional

from stable_agent.understanding.schemas import ExpressionProfile, ExpressionScope


class ExpressionProfileManager:
    """表达习惯管理器。

    管理用户的表达习惯，支持持久化到 JSON 文件。

    Attributes:
        _storage_path: 持久化文件路径。
        _profiles: 表达习惯列表。
    """

    def __init__(self, storage_path: str = "") -> None:
        """初始化表达习惯管理器。

        Args:
            storage_path: 持久化 JSON 文件路径。为空则仅内存存储。
        """
        self._storage_path = storage_path
        self._profiles: list[ExpressionProfile] = []
        self._load()

    def add_expression(
        self,
        phrase: str,
        meaning: list[str],
        scope: str = ExpressionScope.GLOBAL,
        confirmed: bool = False,
        confidence: float = 0.5,
        examples: list[str] | None = None,
    ) -> ExpressionProfile:
        """添加表达习惯。

        Args:
            phrase: 用户表达短语。
            meaning: 标准化含义列表。
            scope: 作用域。
            confirmed: 是否经用户确认。
            confidence: 置信度。
            examples: 示例列表。

        Returns:
            创建的 ExpressionProfile。
        """
        # 检查是否已存在
        for p in self._profiles:
            if p.phrase == phrase:
                # 更新已有记录
                p.normalized_meaning = meaning
                p.scope = scope
                p.confirmed_by_user = confirmed
                p.confidence = confidence
                if examples:
                    p.examples = examples
                self._save()
                return p

        profile = ExpressionProfile(
            phrase=phrase,
            normalized_meaning=meaning,
            scope=scope,
            confirmed_by_user=confirmed,
            confidence=confidence,
            examples=examples or [],
        )
        self._profiles.append(profile)
        self._save()
        return profile

    def delete_expression(self, phrase: str) -> bool:
        """删除表达习惯。

        Args:
            phrase: 要删除的表达短语。

        Returns:
            是否成功删除。
        """
        original_count = len(self._profiles)
        self._profiles = [p for p in self._profiles if p.phrase != phrase]
        if len(self._profiles) < original_count:
            self._save()
            return True
        return False

    def list_expressions(self, scope: str | None = None) -> list[ExpressionProfile]:
        """列出表达习惯。

        Args:
            scope: 按作用域过滤 (可选)。

        Returns:
            匹配的 ExpressionProfile 列表。
        """
        if scope is None:
            return list(self._profiles)
        return [p for p in self._profiles if p.scope == scope]

    def match_expressions(self, text: str) -> list[ExpressionProfile]:
        """匹配文本中的已知表达习惯。

        使用子串匹配，返回所有匹配的 ExpressionProfile。

        Args:
            text: 待匹配文本。

        Returns:
            匹配的 ExpressionProfile 列表。
        """
        matches = []
        for profile in self._profiles:
            if profile.phrase in text:
                matches.append(profile)
        return matches

    def update_expression_rule(
        self,
        phrase: str,
        corrected_meaning: str | list[str],
        source: str = "user_correction",
        confirmed: bool = False,
        confidence: float = 0.7,
    ) -> str:
        """更新或创建表达规则。

        如果 phrase 已存在，更新 normalized_meaning、confidence、examples/source。
        如果 phrase 不存在，创建新的 ExpressionProfile（默认非 confirmed）。

        Args:
            phrase: 用户表达短语（key）。
            corrected_meaning: 标准化含义，str 或 list[str]。
            source: 来源标签。
            confirmed: 是否经用户确认（默认 False，candidate 状态）。
            confidence: 置信度（默认 0.7）。

        Returns:
            phrase 作为 rule_id。
        """
        meanings = [corrected_meaning] if isinstance(corrected_meaning, str) else corrected_meaning

        # 检查是否已存在
        for p in self._profiles:
            if p.phrase == phrase:
                # 更新已有记录
                p.normalized_meaning = meanings
                p.confirmed_by_user = confirmed
                p.confidence = confidence
                if not p.examples:
                    p.examples = []
                if source not in p.examples:
                    p.examples.append(f"[{source}]")
                # 更新 scope 为 global（用户纠正的表达默认全局）
                p.scope = ExpressionScope.GLOBAL
                self._save()
                return p.phrase

        # 新建
        profile = ExpressionProfile(
            phrase=phrase,
            normalized_meaning=meanings,
            scope=ExpressionScope.GLOBAL,
            confirmed_by_user=confirmed,
            confidence=confidence,
            examples=[f"[{source}]"],
        )
        self._profiles.append(profile)
        self._save()
        return phrase

    def _load(self) -> None:
        """从 JSON 文件加载。"""
        if not self._storage_path or not os.path.exists(self._storage_path):
            return

        try:
            with open(self._storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._profiles = [
                ExpressionProfile(
                    phrase=item.get("phrase", ""),
                    normalized_meaning=item.get("normalized_meaning", []),
                    scope=item.get("scope", ExpressionScope.GLOBAL),
                    confirmed_by_user=item.get("confirmed_by_user", False),
                    confidence=item.get("confidence", 0.5),
                    examples=item.get("examples", []),
                )
                for item in data
            ]
        except (json.JSONDecodeError, OSError):
            self._profiles = []

    def _save(self) -> None:
        """保存到 JSON 文件。"""
        if not self._storage_path:
            return

        os.makedirs(os.path.dirname(self._storage_path) or ".", exist_ok=True)
        data = [p.to_dict() for p in self._profiles]
        with open(self._storage_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
