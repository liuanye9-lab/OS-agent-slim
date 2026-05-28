"""测试 API Key 管理。"""

from stable_agent.saas.repository import SaasRepository
from stable_agent.saas.api_keys import ApiKeyManager


class TestApiKeyManager:
    """测试 API Key 创建、校验、撤销。"""

    def test_create_key(self):
        repo = SaasRepository(db_path=":memory:")
        repo.init_db()
        mgr = ApiKeyManager(repo)

        result = mgr.create_key(workspace_id="ws_test", name="test-key")
        assert result["raw_key"].startswith("sk_")
        assert len(result["raw_key"]) == 67  # sk_ + 64 hex chars
        assert result["workspace_id"] == "ws_test"

    def test_validate_key_valid(self):
        repo = SaasRepository(db_path=":memory:")
        repo.init_db()
        mgr = ApiKeyManager(repo)

        result = mgr.create_key(workspace_id="ws_test")
        validation = mgr.validate_key(result["raw_key"])
        assert validation is not None
        assert validation["workspace_id"] == "ws_test"

    def test_validate_key_invalid(self):
        repo = SaasRepository(db_path=":memory:")
        repo.init_db()
        mgr = ApiKeyManager(repo)

        validation = mgr.validate_key("sk_invalid_key_123")
        assert validation is None

    def test_validate_key_empty(self):
        repo = SaasRepository(db_path=":memory:")
        repo.init_db()
        mgr = ApiKeyManager(repo)

        assert mgr.validate_key("") is None
        assert mgr.validate_key("not-sk-prefix") is None

    def test_revoke_key(self):
        repo = SaasRepository(db_path=":memory:")
        repo.init_db()
        mgr = ApiKeyManager(repo)

        result = mgr.create_key(workspace_id="ws_test")
        raw_key = result["raw_key"]

        # 撤销前应有效
        assert mgr.validate_key(raw_key) is not None

        # 撤销
        ok = mgr.revoke_key(result["key_id"])
        assert ok is True

        # 撤销后应无效
        assert mgr.validate_key(raw_key) is None

    def test_list_keys(self):
        repo = SaasRepository(db_path=":memory:")
        repo.init_db()
        mgr = ApiKeyManager(repo)

        mgr.create_key(workspace_id="ws_test", name="key1")
        mgr.create_key(workspace_id="ws_test", name="key2")

        keys = mgr.list_keys("ws_test")
        assert len(keys) == 2
        assert keys[0]["is_active"] is True

    def test_create_key_empty_workspace_fails(self):
        repo = SaasRepository(db_path=":memory:")
        repo.init_db()
        mgr = ApiKeyManager(repo)

        try:
            mgr.create_key(workspace_id="")
            assert False, "Should have raised ValueError"
        except ValueError:
            pass
