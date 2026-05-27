"""RAG 上下文包管理器模块。

本模块提供 RagContextManager 类，用于管理项目知识库并生成
符合 Token 预算的上下文包。实现基于内存的简单倒排索引，
生产环境可替换为向量数据库方案。

V3 升级：新增 chunk_document（文档切块）和 retrieve_rich（增强检索）
方法，支持更细粒度的上下文管理和结构化检索结果。

模块职责：
- 索引项目文档并构建关键词倒排索引
- 根据查询检索相关文档（原始 + 增强版本）
- 按段落/标题切块文档
- 按预算截断和压缩上下文包
"""

from __future__ import annotations

import hashlib
import os
import re
from typing import Optional

from stable_agent.models import TaskType
from stable_agent.token_meter import TokenMeter


class RagContextManager:
    """RAG 上下文包管理器。

    管理项目知识库文档，构建关键词倒排索引，并根据任务类型
    生成符合 Token 预算的上下文包。

    V3 新增：
    - chunk_document: 按段落切块文档
    - retrieve_rich: 结构化检索结果（含 score、why_relevant、risk 等）

    Attributes:
        documents: 文档 id → 内容 映射（内存存储）。
        index: 关键词 → 文档 id 列表（简单倒排索引）。
        chunks: chunk_id → chunk 信息映射（文档切块存储）。
        token_meter: Token 计量器实例。
    """

    def __init__(self) -> None:
        """初始化空的文档存储和倒排索引。"""
        self.documents: dict[str, str] = {}
        self.index: dict[str, list[str]] = {}
        # V3 新增：文档切块存储
        self.chunks: dict[str, dict] = {}
        # V3 新增：Token 计量器
        self.token_meter = TokenMeter()

    # ------------------------------------------------------------------
    # 分词工具方法
    # ------------------------------------------------------------------

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """将文本分词为关键词列表。

        同时提取英文单词（长度 > 2 的字母序列）和中文词组（2-3 字符 ngram）。

        Args:
            text: 待分词的文本。

        Returns:
            关键词列表，已转为小写并去重。
        """
        tokens: list[str] = []

        # 提取英文单词（长度 > 2）
        english_words = re.findall(r"[a-zA-Z]{3,}", text)
        tokens.extend(word.lower() for word in english_words)

        # 提取中文词组：2-3 字符 ngram
        chinese_chars = re.findall(r"[\u4e00-\u9fff]", text)
        chinese_str = "".join(chinese_chars)
        for n in (2, 3):
            if len(chinese_str) >= n:
                for i in range(len(chinese_str) - n + 1):
                    tokens.append(chinese_str[i:i + n])

        # 去重并保留顺序
        seen: set[str] = set()
        unique_tokens: list[str] = []
        for token in tokens:
            if token not in seen:
                seen.add(token)
                unique_tokens.append(token)

        return unique_tokens

    @staticmethod
    def _make_document_id(file_path: str) -> str:
        """从文件路径生成文档 ID。

        取文件路径的前两级目录 + 文件名组成 document_id。

        Args:
            file_path: 文件的完整路径。

        Returns:
            生成的文档 ID。
        """
        parts = file_path.replace("\\", "/").split("/")
        # 取最后三级：parent/grandparent/filename，如果不足则全部取
        if len(parts) >= 3:
            doc_id = "/".join(parts[-3:])
        elif len(parts) == 2:
            doc_id = "/".join(parts)
        else:
            doc_id = parts[-1] if parts else file_path
        return doc_id

    # ------------------------------------------------------------------
    # V3 新增: chunk_document — 按段落/标题切块
    # ------------------------------------------------------------------

    def chunk_document(
        self, doc_id: str, content: str, chunk_size: int = 500
    ) -> list[dict]:
        """按段落/标题切分文档为多个 chunk。

        切分策略：
        1. 优先按 Markdown 标题（#、##、###）分段
        2. 每段按 double newline（段落边界）细分
        3. 超过 chunk_size 的段落进一步按句子切分
        4. 为每个 chunk 生成内容哈希

        Args:
            doc_id: 文档唯一标识。
            content: 文档文本内容。
            chunk_size: 每个 chunk 的目标字符数，默认 500。

        Returns:
            chunk 信息列表，每项包含 chunk_id, content, source_path,
            start_line, end_line, hash。
        """
        if not content:
            return []

        lines = content.split("\n")
        chunks: list[dict] = []
        current_chunk_lines: list[str] = []
        current_start: int = 0
        chunk_index: int = 0

        for line_no, line in enumerate(lines):
            # 检测 Markdown 标题作为切分边界
            is_heading = bool(re.match(r"^#{1,3}\s", line.strip()))

            current_len = sum(len(l) for l in current_chunk_lines)

            # 切分条件：遇到标题 且 当前 chunk 有内容，或超出 chunk_size
            should_split = False
            if is_heading and current_chunk_lines:
                should_split = True
            elif current_len > 0 and current_len + len(line) > chunk_size * 2:
                should_split = True

            if should_split:
                chunk_content = "\n".join(current_chunk_lines)
                chunk_hash = hashlib.md5(chunk_content.encode()).hexdigest()[:8]

                chunks.append({
                    "chunk_id": f"{doc_id}:chunk:{chunk_index}",
                    "content": chunk_content,
                    "source_path": doc_id,
                    "start_line": current_start,
                    "end_line": line_no - 1,
                    "hash": chunk_hash,
                })

                chunk_index += 1
                current_chunk_lines = []
                current_start = line_no

            current_chunk_lines.append(line)

            # 段落边界切分（double newline 逻辑）
            if line.strip() == "" and current_chunk_lines:
                current_chunk_text = "\n".join(current_chunk_lines)
                if len(current_chunk_text) >= chunk_size:
                    chunk_content = "\n".join(current_chunk_lines)
                    chunk_hash = hashlib.md5(chunk_content.encode()).hexdigest()[:8]

                    chunks.append({
                        "chunk_id": f"{doc_id}:chunk:{chunk_index}",
                        "content": chunk_content,
                        "source_path": doc_id,
                        "start_line": current_start,
                        "end_line": line_no,
                        "hash": chunk_hash,
                    })

                    chunk_index += 1
                    current_chunk_lines = []
                    current_start = line_no + 1

        # 处理最后一个 chunk
        if current_chunk_lines:
            chunk_content = "\n".join(current_chunk_lines)
            chunk_hash = hashlib.md5(chunk_content.encode()).hexdigest()[:8]

            chunks.append({
                "chunk_id": f"{doc_id}:chunk:{chunk_index}",
                "content": chunk_content,
                "source_path": doc_id,
                "start_line": current_start,
                "end_line": len(lines) - 1,
                "hash": chunk_hash,
            })

        # 存储到 chunks 字典
        for chunk in chunks:
            self.chunks[chunk["chunk_id"]] = chunk

        return chunks

    # ------------------------------------------------------------------
    # V3 新增: retrieve_rich — 增强检索（结构化返回）
    # ------------------------------------------------------------------

    def retrieve_rich(
        self, query: str, top_k: int = 5
    ) -> list[dict]:
        """根据查询检索相关文档，返回结构化结果。

        相比 retrieve()，返回增强的 dict 结构，包含 score、
        why_relevant、risk 和 token_estimate 字段。

        先尝试从 chunks 中检索（如果文档已被切块），
        否则回退到关键词倒排索引检索。

        Args:
            query: 查询字符串。
            top_k: 返回的最多文档数，默认 5。

        Returns:
            结构化 chunk 列表，每项包含：
            {chunk_id, content, source_path, score, why_relevant, risk, token_estimate}

        # STUB: 真实实现应调用 embedding 模型将 query 向量化，
        #        在向量数据库中做 ANN 搜索。
        """
        if not query:
            return []

        # 优先从 chunks 检索
        if self.chunks:
            return self._retrieve_from_chunks(query, top_k)

        # 回退到倒排索引检索
        return self._retrieve_from_index_rich(query, top_k)

    def _retrieve_from_chunks(
        self, query: str, top_k: int
    ) -> list[dict]:
        """从已切块的文档中检索（关键词匹配）。

        Args:
            query: 查询字符串。
            top_k: 返回的最多 chunk 数。

        Returns:
            结构化 chunk 列表。
        """
        if not self.chunks:
            return []

        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        # 为每个 chunk 计算匹配分数
        chunk_scores: list[tuple[str, float]] = []
        for chunk_id, chunk_info in self.chunks.items():
            content = chunk_info.get("content", "")
            if not content:
                continue
            content_lower = content.lower()

            # 计算匹配的关键词数作为分数
            matches = sum(
                1 for token in query_tokens if token.lower() in content_lower
            )
            if matches > 0:
                # 归一化分数：匹配词数 / 查询词数
                score = matches / len(query_tokens)
                chunk_scores.append((chunk_id, score))

        # 按分数降序排列
        chunk_scores.sort(key=lambda x: x[1], reverse=True)

        # 构建结构化结果
        results: list[dict] = []
        for chunk_id, score in chunk_scores[:top_k]:
            chunk_info = self.chunks[chunk_id]
            content = chunk_info.get("content", "")

            results.append({
                "chunk_id": chunk_id,
                "content": content,
                "source_path": chunk_info.get("source_path", ""),
                "score": round(score, 4),
                "why_relevant": f"匹配 {int(score * 100)}% 关键词",
                "risk": self._detect_uncertainty_risk(content),
                "token_estimate": self.token_meter.estimate_tokens(content),
            })

        return results

    def _retrieve_from_index_rich(
        self, query: str, top_k: int
    ) -> list[dict]:
        """从倒排索引检索并返回结构化结果。

        将原有的 list[str] 结果升级为 list[dict] 格式。

        Args:
            query: 查询字符串。
            top_k: 返回的最多文档数。

        Returns:
            结构化文档信息列表。
        """
        if not self.index:
            return []

        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        # 统计每个文档匹配的关键词数
        doc_scores: dict[str, int] = {}
        for token in query_tokens:
            if token in self.index:
                for doc_id in self.index[token]:
                    doc_scores[doc_id] = doc_scores.get(doc_id, 0) + 1

        if not doc_scores:
            return []

        # 按匹配词数降序排序
        ranked = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)

        # 构建结构化结果
        results: list[dict] = []
        max_matches = max(s for _, s in ranked) if ranked else 1

        for doc_id, match_count in ranked[:top_k]:
            content = self.documents.get(doc_id, "")
            score = round(match_count / max_matches, 4) if max_matches > 0 else 0.0

            results.append({
                "chunk_id": doc_id,
                "content": content,
                "source_path": doc_id,
                "score": score,
                "why_relevant": f"匹配 {match_count} 个关键词",
                "risk": self._detect_uncertainty_risk(content),
                "token_estimate": self.token_meter.estimate_tokens(content),
            })

        return results

    @staticmethod
    def _detect_uncertainty_risk(content: str) -> Optional[str]:
        """检测内容中的不确定性风险。

        检查是否包含"可能""也许"等不确定词。

        Args:
            content: 文本内容。

        Returns:
            "uncertain" 如果检测到不确定词，否则 None。
        """
        uncertainty_words = {
            "可能", "也许", "或许", "大概", "应该", "估计",
            "maybe", "perhaps", "probably", "likely", "possibly",
            "不确定", "uncertain",
        }
        content_lower = content.lower()
        for word in uncertainty_words:
            if word.lower() in content_lower:
                return "uncertain"
        return None

    # ------------------------------------------------------------------
    # 公共 API（保持向后兼容）
    # ------------------------------------------------------------------

    def index_documents(self, doc_paths: list[str]) -> None:
        """索引一批文档文件。

        读取每个文件内容，构建关键词倒排索引。

        Args:
            doc_paths: 文档文件路径列表。

        # STUB: 实际应使用 faiss/Qdrant + SentenceTransformer 构建向量索引。
        # STUB: 换真实实现时，index_documents 应产生 embedding 向量并写入向量数据库。
        """
        for path in doc_paths:
            if not os.path.isfile(path):
                continue
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
            except (OSError, UnicodeDecodeError):
                continue

            doc_id = self._make_document_id(path)
            self.documents[doc_id] = content

            # 构建倒排索引
            tokens = self._tokenize(content)
            for token in tokens:
                if token not in self.index:
                    self.index[token] = []
                if doc_id not in self.index[token]:
                    self.index[token].append(doc_id)

    def retrieve(self, query: str, top_k: int = 5) -> list[str]:
        """根据查询检索相关文档。

        将查询分词后在倒排索引中查找匹配的文档，按匹配词数降序返回。

        Args:
            query: 查询字符串。
            top_k: 返回的最多文档数量，默认 5。

        Returns:
            匹配文档的内容列表，按相关度降序排列。

        # STUB: 真实实现应调用 embedding 模型将 query 向量化，
        #        在向量数据库中做 ANN 搜索。
        """
        if not self.index or not query:
            return []

        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        # 统计每个文档匹配的关键词数
        doc_scores: dict[str, int] = {}
        for token in query_tokens:
            if token in self.index:
                for doc_id in self.index[token]:
                    doc_scores[doc_id] = doc_scores.get(doc_id, 0) + 1

        if not doc_scores:
            return []

        # 按匹配词数降序排序
        ranked = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)

        # 返回 top_k 个文档的内容
        results: list[str] = []
        for doc_id, _ in ranked[:top_k]:
            if doc_id in self.documents:
                results.append(self.documents[doc_id])

        return results

    def build_context_pack(
        self, task: TaskType, budget: int
    ) -> list[str]:
        """根据任务类型构建上下文包。

        根据 task 类型生成查询词，检索相关文档，并确保总字符数不超过 budget。

        Args:
            task: 任务类型。
            budget: 上下文包的最大字符数预算。

        Returns:
            压缩后的文档内容列表。如果索引为空，返回空列表。
        """
        # 根据任务类型生成内置查询词
        task_queries: dict[TaskType, str] = {
            TaskType.BUG_FIX: "bug 错误 修复",
            TaskType.ARCH_REFACTOR: "架构 模块 重构",
            TaskType.UI_DESIGN: "界面 设计 样式 组件",
            TaskType.PROMPT_OPTIMIZATION: "prompt 优化 提示词",
            TaskType.EVAL_TASK: "评估 测试 验证",
            TaskType.CODE_GENERATION: "代码 生成 实现",
            TaskType.GENERAL_QA: "文档 说明 指南",
        }
        query = task_queries.get(task, "文档")
        docs = self.retrieve(query, top_k=5)

        if not docs:
            return []

        # 如果总字符数超过 budget，对每个文档进行截取
        total_chars = sum(len(d) for d in docs)
        if total_chars <= budget:
            return docs

        # 按比例分配预算给每个文档
        compressed: list[str] = []
        per_doc_budget = max(1, budget // len(docs))
        for doc in docs:
            if len(doc) <= per_doc_budget:
                compressed.append(doc)
            else:
                # 保留前 70% + 后 15%（保留开头和结尾）
                head_size = int(per_doc_budget * 0.85)
                tail_size = per_doc_budget - head_size
                if tail_size > 0 and len(doc) > head_size + tail_size:
                    truncated = (
                        doc[:head_size]
                        + "\n... [内容已截断] ...\n"
                        + doc[-tail_size:]
                    )
                else:
                    truncated = doc[:per_doc_budget]
                compressed.append(truncated)

        return compressed

    def add_document(self, doc_id: str, content: str) -> None:
        """手动添加单篇文档到存储和索引中。

        Args:
            doc_id: 文档唯一标识符。
            content: 文档的文本内容。
        """
        self.documents[doc_id] = content
        tokens = self._tokenize(content)
        for token in tokens:
            if token not in self.index:
                self.index[token] = []
            if doc_id not in self.index[token]:
                self.index[token].append(doc_id)
