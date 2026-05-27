"""Skill prompt 的结构性契约定义。

定义 skill 文档的保护区边界、结构约束和大小限制。
提供保护区检测和内容提取的静态工具方法。
"""

from __future__ import annotations


class PromptContracts:
    """Skill prompt 的结构性契约定义。

    定义 skill 文档中受保护区域（SLOW_UPDATE 区域）的边界标记，
    以及 skill 文档的大小上限。所有方法均为类方法，无需实例化。

    Attributes:
        PROTECTED_START: 保护区起始标记。
        PROTECTED_END: 保护区结束标记。
        MAX_SKILL_SIZE: skill 文档最大字符数限制。
    """

    PROTECTED_START: str = "<!-- SLOW_UPDATE_START -->"
    PROTECTED_END: str = "<!-- SLOW_UPDATE_END -->"
    MAX_SKILL_SIZE: int = 5000

    @classmethod
    def is_in_protected_zone(cls, content: str, position: int) -> bool:
        """检查给定位置是否在保护区范围内。

        通过查找 PROTECTED_START 和 PROTECTED_END 标记的位置，
        判断 position 是否落在两个标记之间。

        Args:
            content: skill 文档的完整文本内容。
            position: 要检查的字符位置（0-based 索引）。

        Returns:
            True 如果 position 位于保护区内，否则 False。
            如果找不到保护区标记，返回 False。
        """
        start_idx = content.find(cls.PROTECTED_START)
        end_idx = content.find(cls.PROTECTED_END)

        if start_idx == -1 or end_idx == -1:
            return False

        # 保护区从 START 标记之后开始，到 END 标记之前结束
        protected_start = start_idx + len(cls.PROTECTED_START)
        protected_end = end_idx

        return protected_start <= position < protected_end

    @classmethod
    def extract_protected_content(cls, content: str) -> str:
        """提取保护区内的内容（不含标记本身）。

        Args:
            content: skill 文档的完整文本内容。

        Returns:
            保护区内的文本内容。如果找不到保护区标记，返回空字符串。
        """
        start_idx = content.find(cls.PROTECTED_START)
        end_idx = content.find(cls.PROTECTED_END)

        if start_idx == -1 or end_idx == -1:
            return ""

        start = start_idx + len(cls.PROTECTED_START)
        # 跳过 START 标记所在行的换行符
        if start < len(content) and content[start] == "\n":
            start += 1

        return content[start:end_idx].rstrip()

    @classmethod
    def extract_unprotected_content(cls, content: str) -> str:
        """提取非保护区内容（保护区之前和之后的部分拼接）。

        将 PROTECTED_START 之前的内容与 PROTECTED_END 之后的内容拼接，
        中间保留保护区的标记但内容被移除。

        Args:
            content: skill 文档的完整文本内容。

        Returns:
            去除保护区内容后的文本。
        """
        start_idx = content.find(cls.PROTECTED_START)
        end_idx = content.find(cls.PROTECTED_END)

        if start_idx == -1 or end_idx == -1:
            return content

        before = content[:start_idx].rstrip()
        after = content[end_idx + len(cls.PROTECTED_END):]
        # 确保 after 不以多余的换行开头
        after = after.lstrip("\n")

        return before + "\n\n" + after if after else before

    @classmethod
    def check_skill_size(cls, content: str) -> tuple[bool, int]:
        """检查 skill 是否超过大小限制。

        Args:
            content: skill 文档的完整文本内容。

        Returns:
            (is_valid, current_size) 元组。
            is_valid 为 True 表示未超过限制，False 表示超过。
        """
        current_size = len(content)
        is_valid = current_size <= cls.MAX_SKILL_SIZE
        return is_valid, current_size
