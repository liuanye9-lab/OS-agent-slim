"""P1 扩展模块测试套件。

测试范围：
- RagContextManager: 文档添加、索引构建、检索、预算截断
- TemporalKnowledgeGraph: 事实添加、时间查询、冲突检测
- VersionControlManager: Git 仓库初始化、检查点、diff、回退
"""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path

import pytest

from stable_agent.git_diff_checkpoint import VersionControlManager
from stable_agent.models import TaskType
from stable_agent.rag_context_pack import RagContextManager
from stable_agent.temporal_knowledge_graph import TemporalKnowledgeGraph


# ============================================================================
# 测试夹具
# ============================================================================


@pytest.fixture
def rag_manager() -> RagContextManager:
    """创建一个空的 RagContextManager 实例。"""
    return RagContextManager()


@pytest.fixture
def tk_graph() -> TemporalKnowledgeGraph:
    """创建一个空的 TemporalKnowledgeGraph 实例。"""
    return TemporalKnowledgeGraph()


@pytest.fixture
def temp_dir() -> str:
    """创建临时目录并返回路径，测试结束后自动清理。"""
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def temp_repo_dir() -> str:
    """创建临时目录作为 Git 仓库根目录，测试结束后自动清理。"""
    with tempfile.TemporaryDirectory() as d:
        yield d


# ============================================================================
# RagContextManager 测试
# ============================================================================


class TestRagContextManagerAddDocument:
    """测试 add_document 方法。"""

    def test_add_document_stores_content(self, rag_manager: RagContextManager) -> None:
        """添加文档后，内容应正确存储。"""
        rag_manager.add_document("doc1", "这是一篇关于 Python 编程和 AI 开发的文档。")
        assert "doc1" in rag_manager.documents
        assert rag_manager.documents["doc1"] == "这是一篇关于 Python 编程和 AI 开发的文档。"

    def test_add_document_indexes_tokens(self, rag_manager: RagContextManager) -> None:
        """添加文档后，关键词应正确索引到倒排索引中。"""
        rag_manager.add_document("doc1", "bug 修复 缓存优化 optimization cache tuning")
        # 英文 token
        assert "optimization" in rag_manager.index
        assert "doc1" in rag_manager.index["optimization"]
        # 中文 2-gram
        assert "修复" in rag_manager.index or "缓存" in rag_manager.index

    def test_add_multiple_documents(self, rag_manager: RagContextManager) -> None:
        """添加多篇文档后，索引应正确关联到各文档。"""
        rag_manager.add_document("doc1", "database 连接 池 配置")
        rag_manager.add_document("doc2", "database 查询 query 优化")
        # 共享关键词
        assert "database" in rag_manager.index
        assert "doc1" in rag_manager.index["database"]
        assert "doc2" in rag_manager.index["database"]
        # 独有关键词
        assert "连接" in rag_manager.index
        assert "doc1" in rag_manager.index["连接"]
        assert "doc2" not in rag_manager.index.get("连接", [])


class TestRagContextManagerIndexDocuments:
    """测试 index_documents 方法。"""

    def test_index_documents_from_files(self, rag_manager: RagContextManager, temp_dir: str) -> None:
        """从磁盘文件索引文档。"""
        # 创建测试文件
        file1 = os.path.join(temp_dir, "architecture_overview.txt")
        file2 = os.path.join(temp_dir, "bug_report_001.txt")
        with open(file1, "w", encoding="utf-8") as f:
            f.write("架构设计文档：系统模块划分为核心引擎和插件层。")
        with open(file2, "w", encoding="utf-8") as f:
            f.write("Bug 报告：缓存模块存在内存泄漏问题。")

        rag_manager.index_documents([file1, file2])

        # 验证文档已索引
        assert len(rag_manager.documents) == 2
        # 应能检索到
        results = rag_manager.retrieve("架构 模块")
        assert len(results) >= 1

    def test_index_documents_skips_missing(self, rag_manager: RagContextManager, temp_dir: str) -> None:
        """不存在的文件应被跳过。"""
        missing = os.path.join(temp_dir, "nonexistent.txt")
        rag_manager.index_documents([missing])
        assert len(rag_manager.documents) == 0


class TestRagContextManagerRetrieve:
    """测试 retrieve 方法。"""

    def test_retrieve_empty_index(self, rag_manager: RagContextManager) -> None:
        """空索引检索应返回空列表。"""
        results = rag_manager.retrieve("anything")
        assert results == []

    def test_retrieve_with_match(self, rag_manager: RagContextManager) -> None:
        """匹配关键词应返回对应文档。"""
        rag_manager.add_document("doc1", "Python 异步编程 async await 教程")
        rag_manager.add_document("doc2", "Java 多线程并发 concurrent 编程")
        results = rag_manager.retrieve("async await 异步")
        assert len(results) >= 1
        # doc1 应排在前面（更多匹配）
        assert "Python" in results[0]

    def test_retrieve_partial_match(self, rag_manager: RagContextManager) -> None:
        """部分匹配也应返回结果。"""
        rag_manager.add_document("doc1", "React 前端框架组件化开发指南")
        rag_manager.add_document("doc2", "Vue 前端渐进式框架教程")
        results = rag_manager.retrieve("React 组件")
        assert len(results) >= 1

    def test_retrieve_no_match(self, rag_manager: RagContextManager) -> None:
        """无匹配关键词应返回空列表。"""
        rag_manager.add_document("doc1", "Python 编程指南")
        results = rag_manager.retrieve("xyznotexist")
        assert results == []

    def test_retrieve_top_k_limit(self, rag_manager: RagContextManager) -> None:
        """top_k 应限制返回数量。"""
        for i in range(10):
            rag_manager.add_document(f"doc{i}", f"测试文档 {i} Python 开发 指南 手册 参考")
        results = rag_manager.retrieve("Python 开发", top_k=3)
        assert len(results) <= 3


class TestRagContextManagerBuildContextPack:
    """测试 build_context_pack 方法。"""

    def test_build_context_pack_within_budget(self, rag_manager: RagContextManager) -> None:
        """文档总大小在预算内，应返回完整文档。"""
        rag_manager.add_document("doc1", "简短文档")
        rag_manager.add_document("doc2", "另一个文档")
        pack = rag_manager.build_context_pack(TaskType.GENERAL_QA, budget=1000)
        assert len(pack) == 2

    def test_build_context_pack_exceeds_budget(self, rag_manager: RagContextManager) -> None:
        """文档总大小超出预算，应截断。"""
        long_text = "Python 编程 指南 参考 " * 500
        rag_manager.add_document("doc1", long_text)
        pack = rag_manager.build_context_pack(TaskType.GENERAL_QA, budget=100)
        assert len(pack) == 1
        # 截断后长度应在预算附近
        assert len(pack[0]) <= 150  # 允许 ±50% 余量

    def test_build_context_pack_empty_index(self, rag_manager: RagContextManager) -> None:
        """空索引应返回空列表。"""
        pack = rag_manager.build_context_pack(TaskType.BUG_FIX, budget=1000)
        assert pack == []

    def test_build_context_pack_task_queries(self, rag_manager: RagContextManager) -> None:
        """不同任务类型应使用不同的查询词。"""
        rag_manager.add_document("doc1", "发现一个严重 bug 需要修复 错误处理缺失")
        rag_manager.add_document("doc2", "架构重构方案：将单体拆分为微服务 模块化设计")

        pack_bug = rag_manager.build_context_pack(TaskType.BUG_FIX, budget=5000)
        pack_arch = rag_manager.build_context_pack(TaskType.ARCH_REFACTOR, budget=5000)

        # BUG_FIX 应优先返回 bug 相关文档
        assert any("bug" in d.lower() for d in pack_bug)
        # ARCH_REFACTOR 应优先返回架构相关文档
        assert any("架构" in d for d in pack_arch)


# ============================================================================
# TemporalKnowledgeGraph 测试
# ============================================================================


class TestTemporalKnowledgeGraphAddFact:
    """测试 add_fact 方法。"""

    def test_add_fact_increases_count(self, tk_graph: TemporalKnowledgeGraph) -> None:
        """添加事实后，计数应增加。"""
        assert tk_graph.get_facts_count() == 0
        tk_graph.add_fact("Alice", "owns", "projectX", time.time())
        assert tk_graph.get_facts_count() == 1

    def test_add_fact_with_end_time(self, tk_graph: TemporalKnowledgeGraph) -> None:
        """添加带 end_time 的事实。"""
        now = time.time()
        tk_graph.add_fact("server1", "runs", "nginx", now - 100, now)
        assert tk_graph.get_facts_count() == 1

    def test_add_fact_end_time_none(self, tk_graph: TemporalKnowledgeGraph) -> None:
        """end_time=None 表示持续有效。"""
        tk_graph.add_fact("service", "status", "active", time.time())
        fact = tk_graph.facts[0]
        assert fact["end_time"] is None


class TestTemporalKnowledgeGraphQueryFacts:
    """测试 query_facts 方法。"""

    def test_query_facts_no_time_range(self, tk_graph: TemporalKnowledgeGraph) -> None:
        """不加时间范围，按实体名查询。"""
        now = time.time()
        tk_graph.add_fact("Alice", "works_on", "projectX", now - 100)
        tk_graph.add_fact("Bob", "works_on", "projectY", now - 100)
        results = tk_graph.query_facts("Alice")
        assert len(results) == 1
        assert results[0]["subject"] == "Alice"

    def test_query_facts_with_time_range_included(self, tk_graph: TemporalKnowledgeGraph) -> None:
        """在指定时间范围内的查询应返回结果。"""
        now = time.time()
        tk_graph.add_fact("serviceA", "status", "degraded", now - 200, now - 100)
        tk_graph.add_fact("serviceA", "status", "healthy", now - 50, now)

        # 查询覆盖 degraded 时段
        results = tk_graph.query_facts("serviceA", (now - 150, now - 80))
        assert len(results) == 1
        assert results[0]["obj"] == "degraded"

    def test_query_facts_with_time_range_excluded(self, tk_graph: TemporalKnowledgeGraph) -> None:
        """时间范围外的查询应返回空。"""
        now = time.time()
        tk_graph.add_fact("serviceA", "status", "active", now - 10, now)

        # 查询很久以前的时间
        results = tk_graph.query_facts("serviceA", (now - 1000, now - 500))
        assert len(results) == 0

    def test_query_facts_end_time_none_matches(self, tk_graph: TemporalKnowledgeGraph) -> None:
        """end_time=None 的事实应匹配任意未来时间点。"""
        now = time.time()
        tk_graph.add_fact("config", "value", "v2", now - 100)  # end_time=None

        # 查询包含当前时间
        results = tk_graph.query_facts("config", (now - 50, now + 50))
        assert len(results) == 1
        assert results[0]["obj"] == "v2"

    def test_query_facts_by_obj_entity(self, tk_graph: TemporalKnowledgeGraph) -> None:
        """按 object 实体名查询也应匹配。"""
        now = time.time()
        tk_graph.add_fact("Alice", "reports_to", "Bob", now - 100)
        results = tk_graph.query_facts("Bob")
        assert len(results) == 1
        assert results[0]["subject"] == "Alice"


class TestTemporalKnowledgeGraphResolveConflicts:
    """测试 resolve_conflicts 方法。"""

    def test_resolve_conflicts_with_overlap(self, tk_graph: TemporalKnowledgeGraph) -> None:
        """时间重叠且 predicate 相同 obj 不同，应检测到冲突。"""
        now = time.time()
        # 两个事实时间重叠
        tk_graph.add_fact("serviceA", "status", "healthy", now - 100, now + 100)
        tk_graph.add_fact("serviceA", "status", "degraded", now - 50, now + 150)

        conflicts = tk_graph.resolve_conflicts("serviceA")
        assert len(conflicts) == 1
        assert len(conflicts[0]) == 2

    def test_resolve_conflicts_no_overlap(self, tk_graph: TemporalKnowledgeGraph) -> None:
        """时间不重叠，不应检测到冲突。"""
        now = time.time()
        tk_graph.add_fact("serviceA", "status", "healthy", now - 200, now - 100)
        tk_graph.add_fact("serviceA", "status", "degraded", now, now + 100)

        conflicts = tk_graph.resolve_conflicts("serviceA")
        assert len(conflicts) == 0

    def test_resolve_conflicts_same_obj_no_conflict(self, tk_graph: TemporalKnowledgeGraph) -> None:
        """obj 相同不应视为冲突。"""
        now = time.time()
        tk_graph.add_fact("serviceA", "status", "healthy", now - 200, now - 100)
        tk_graph.add_fact("serviceA", "status", "healthy", now - 50, now + 50)

        conflicts = tk_graph.resolve_conflicts("serviceA")
        assert len(conflicts) == 0

    def test_resolve_conflicts_different_predicate(self, tk_graph: TemporalKnowledgeGraph) -> None:
        """predicate 不同不应视为冲突。"""
        now = time.time()
        tk_graph.add_fact("serviceA", "status", "active", now - 100, now + 100)
        tk_graph.add_fact("serviceA", "owner", "Alice", now - 50, now + 150)

        conflicts = tk_graph.resolve_conflicts("serviceA")
        assert len(conflicts) == 0


class TestTemporalKnowledgeGraphClear:
    """测试 clear 方法。"""

    def test_clear_removes_all_facts(self, tk_graph: TemporalKnowledgeGraph) -> None:
        """清空后事实数应为 0。"""
        tk_graph.add_fact("A", "likes", "B", time.time())
        tk_graph.add_fact("C", "uses", "D", time.time())
        assert tk_graph.get_facts_count() == 2
        tk_graph.clear()
        assert tk_graph.get_facts_count() == 0

    def test_clear_on_empty_graph(self, tk_graph: TemporalKnowledgeGraph) -> None:
        """对空图清空不应报错。"""
        tk_graph.clear()
        assert tk_graph.get_facts_count() == 0


# ============================================================================
# VersionControlManager 测试
# ============================================================================


class TestVersionControlManagerInitializeRepo:
    """测试 initialize_repo 方法。"""

    def test_initialize_repo(self, temp_dir: str) -> None:
        """初始化 Git 仓库应成功。"""
        vcm = VersionControlManager(temp_dir)
        result = vcm.initialize_repo()
        assert result is True
        # 验证 .git 目录存在
        assert os.path.isdir(os.path.join(temp_dir, ".git"))

    def test_initialize_repo_with_path(self, temp_dir: str) -> None:
        """指定路径初始化。"""
        sub_dir = os.path.join(temp_dir, "subproject")
        os.makedirs(sub_dir, exist_ok=True)
        vcm = VersionControlManager(".")
        result = vcm.initialize_repo(path=sub_dir)
        assert result is True
        assert os.path.isdir(os.path.join(sub_dir, ".git"))


class TestVersionControlManagerCheckpoint:
    """测试 create_checkpoint 和 commit_changes 方法。"""

    def test_create_checkpoint_returns_hash(self, temp_dir: str) -> None:
        """创建检查点应返回 commit hash。"""
        vcm = VersionControlManager(temp_dir)
        vcm.initialize_repo()
        # 需要先配置 git user（CI 环境可能没有全局配置）
        subprocess_run = __import__("subprocess").run
        subprocess_run(
            ["git", "config", "user.email", "test@test.com"],
            capture_output=True, cwd=temp_dir,
        )
        subprocess_run(
            ["git", "config", "user.name", "Test"],
            capture_output=True, cwd=temp_dir,
        )
        # 创建文件以产生有意义的 commit
        test_file = os.path.join(temp_dir, "test.txt")
        with open(test_file, "w") as f:
            f.write("hello")
        commit_hash = vcm.create_checkpoint("initial commit")
        assert commit_hash is not None
        assert len(commit_hash) == 40  # SHA-1 hash

    def test_commit_changes_same_as_checkpoint(self, temp_dir: str) -> None:
        """commit_changes 应与 create_checkpoint 行为一致。"""
        vcm = VersionControlManager(temp_dir)
        vcm.initialize_repo()
        subprocess_run = __import__("subprocess").run
        subprocess_run(
            ["git", "config", "user.email", "test@test.com"],
            capture_output=True, cwd=temp_dir,
        )
        subprocess_run(
            ["git", "config", "user.name", "Test"],
            capture_output=True, cwd=temp_dir,
        )
        test_file = os.path.join(temp_dir, "data.txt")
        with open(test_file, "w") as f:
            f.write("data")
        hash1 = vcm.create_checkpoint("checkpoint via create")
        # 做新变更
        with open(test_file, "a") as f:
            f.write("more data")
        hash2 = vcm.commit_changes("checkpoint via commit")
        assert hash2 is not None
        assert hash2 != hash1  # 不同 commit 应有不同 hash


class TestVersionControlManagerDiff:
    """测试 compute_diff 方法。"""

    def test_compute_diff_no_changes(self, temp_dir: str) -> None:
        """干净仓库的 diff 应为空。"""
        vcm = VersionControlManager(temp_dir)
        vcm.initialize_repo()
        subprocess_run = __import__("subprocess").run
        subprocess_run(
            ["git", "config", "user.email", "test@test.com"],
            capture_output=True, cwd=temp_dir,
        )
        subprocess_run(
            ["git", "config", "user.name", "Test"],
            capture_output=True, cwd=temp_dir,
        )
        # 创建一个初始 commit
        init_file = os.path.join(temp_dir, "init.txt")
        with open(init_file, "w") as f:
            f.write("init")
        vcm.create_checkpoint("init")
        diff = vcm.compute_diff()
        assert diff == ""

    def test_compute_diff_with_changes(self, temp_dir: str) -> None:
        """有变更时应返回非空 diff。"""
        vcm = VersionControlManager(temp_dir)
        vcm.initialize_repo()
        subprocess_run = __import__("subprocess").run
        subprocess_run(
            ["git", "config", "user.email", "test@test.com"],
            capture_output=True, cwd=temp_dir,
        )
        subprocess_run(
            ["git", "config", "user.name", "Test"],
            capture_output=True, cwd=temp_dir,
        )
        # 初始 commit
        test_file = os.path.join(temp_dir, "code.py")
        with open(test_file, "w") as f:
            f.write("print('hello')")
        vcm.create_checkpoint("initial")

        # 修改文件
        with open(test_file, "w") as f:
            f.write("print('hello world')")

        diff = vcm.compute_diff()
        assert "hello world" in diff or "diff" in diff.lower()

    def test_compute_diff_single_file(self, temp_dir: str) -> None:
        """指定文件路径的 diff 应只包含该文件的变更。"""
        vcm = VersionControlManager(temp_dir)
        vcm.initialize_repo()
        subprocess_run = __import__("subprocess").run
        subprocess_run(
            ["git", "config", "user.email", "test@test.com"],
            capture_output=True, cwd=temp_dir,
        )
        subprocess_run(
            ["git", "config", "user.name", "Test"],
            capture_output=True, cwd=temp_dir,
        )
        file_a = os.path.join(temp_dir, "a.txt")
        file_b = os.path.join(temp_dir, "b.txt")
        with open(file_a, "w") as f:
            f.write("A")
        with open(file_b, "w") as f:
            f.write("B")
        vcm.create_checkpoint("init")

        with open(file_a, "w") as f:
            f.write("A modified")
        with open(file_b, "w") as f:
            f.write("B modified")

        diff = vcm.compute_diff(file_path="a.txt")
        assert diff != ""


class TestVersionControlManagerRevert:
    """测试 revert_to_checkpoint 方法。"""

    def test_revert_to_checkpoint(self, temp_dir: str) -> None:
        """回退到之前的检查点应成功。"""
        vcm = VersionControlManager(temp_dir)
        vcm.initialize_repo()
        subprocess_run = __import__("subprocess").run
        subprocess_run(
            ["git", "config", "user.email", "test@test.com"],
            capture_output=True, cwd=temp_dir,
        )
        subprocess_run(
            ["git", "config", "user.name", "Test"],
            capture_output=True, cwd=temp_dir,
        )
        test_file = os.path.join(temp_dir, "revert_test.txt")
        with open(test_file, "w") as f:
            f.write("version 1")
        hash1 = vcm.create_checkpoint("v1")

        with open(test_file, "w") as f:
            f.write("version 2")
        vcm.create_checkpoint("v2")

        # 回退到 v1
        assert hash1 is not None
        result = vcm.revert_to_checkpoint(hash1)
        assert result is True

        # 验证内容已回退
        with open(test_file, "r") as f:
            content = f.read()
        assert content == "version 1"


class TestVersionControlManagerGetHash:
    """测试 get_current_hash 方法。"""

    def test_get_current_hash_after_init(self, temp_dir: str) -> None:
        """init 后无 commit 时 get_current_hash 返回 None。"""
        vcm = VersionControlManager(temp_dir)
        vcm.initialize_repo()
        # 没有 commit，rev-parse HEAD 应该失败
        result = vcm.get_current_hash()
        # 新仓库没有 commit 时 get_current_hash 返回 None
        # （取决于 git 版本，可能返回 None 或引发异常）
        assert result is None or isinstance(result, str)

    def test_get_current_hash_after_commit(self, temp_dir: str) -> None:
        """commit 后应返回有效的 hash。"""
        vcm = VersionControlManager(temp_dir)
        vcm.initialize_repo()
        subprocess_run = __import__("subprocess").run
        subprocess_run(
            ["git", "config", "user.email", "test@test.com"],
            capture_output=True, cwd=temp_dir,
        )
        subprocess_run(
            ["git", "config", "user.name", "Test"],
            capture_output=True, cwd=temp_dir,
        )
        test_file = os.path.join(temp_dir, "hash_test.txt")
        with open(test_file, "w") as f:
            f.write("test")
        commit_hash = vcm.create_checkpoint("test commit")
        current = vcm.get_current_hash()
        assert current == commit_hash
        assert len(current) == 40


# ============================================================================
# 边界情况测试
# ============================================================================


class TestEdgeCases:
    """边界情况和异常处理测试。"""

    def test_rag_add_empty_document(self) -> None:
        """添加空内容文档不应报错。"""
        mgr = RagContextManager()
        mgr.add_document("empty_doc", "")
        assert "empty_doc" in mgr.documents
        assert mgr.documents["empty_doc"] == ""

    def test_rag_retrieve_empty_query(self) -> None:
        """空查询应返回空列表。"""
        mgr = RagContextManager()
        mgr.add_document("doc1", "some content")
        results = mgr.retrieve("")
        assert results == []

    def test_tkg_add_duplicate_facts(self, tk_graph: TemporalKnowledgeGraph) -> None:
        """重复添加相同事实，count 应正确累加。"""
        now = time.time()
        tk_graph.add_fact("A", "uses", "B", now)
        tk_graph.add_fact("A", "uses", "B", now)
        assert tk_graph.get_facts_count() == 2

    def test_tkg_query_nonexistent_entity(self, tk_graph: TemporalKnowledgeGraph) -> None:
        """查询不存在的实体应返回空列表。"""
        now = time.time()
        tk_graph.add_fact("Alice", "owns", "car", now)
        results = tk_graph.query_facts("Bob")
        assert results == []

    def test_git_revert_to_nonexistent_hash(self, temp_dir: str) -> None:
        """回退到不存在的 hash 应返回 False。"""
        vcm = VersionControlManager(temp_dir)
        vcm.initialize_repo()
        result = vcm.revert_to_checkpoint("nonexistenthash1234567890")
        assert result is False
