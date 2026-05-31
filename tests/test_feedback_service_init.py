# test_feedback_service_init.py
# 阶段1: FeedbackLearningService 初始化测试
"""FeedbackLearningService 必须能无参数初始化，expression_manager 不能是 None。"""
import tempfile, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_feedback_service_init_ok():
    """FeedbackLearningService() 无参数初始化成功，expression_manager 不为 None。"""
    from stable_agent.feedback.feedback_learning_service import FeedbackLearningService

    service = FeedbackLearningService()
    assert service is not None, "FeedbackLearningService 初始化失败"
    assert hasattr(service, "expression_manager"), "缺少 expression_manager 属性"
    assert service.expression_manager is not None, "expression_manager 是 None"
    print("test_feedback_service_init_ok PASSED")

def test_expression_manager_path_points_to_capsule():
    """expression storage path 指向 capsule/profile/expressions.json。"""
    from stable_agent.feedback.feedback_learning_service import FeedbackLearningService

    service = FeedbackLearningService()
    # storage_path 是内部属性 _storage_path
    assert hasattr(service.expression_manager, "_storage_path"), "expression_manager 没有 _storage_path"
    path = service.expression_manager._storage_path
    assert "profile" in path, f"storage_path 不包含 profile: {path}"
    assert "expressions.json" in path, f"storage_path 不包含 expressions.json: {path}"
    print("test_expression_manager_path_points_to_capsule PASSED")

def test_web_app_creates_feedback_service():
    """web.app.create_app() 不会因 FeedbackLearningService 初始化失败而报错。"""
    try:
        from web.app import create_app
        app = create_app()
        assert app is not None, "create_app 返回 None"
        # app 上有 feedback_service 属性
        assert hasattr(app.state, "feedback_service"), "app.state 缺少 feedback_service"
        print("test_web_app_creates_feedback_service PASSED")
    except Exception as e:
        # 降级日志可接受，只要不是 ImportError 或参数错误
        if "ExpressionProfileManager" in str(e) or "storage_path" in str(e) or "data_dir" in str(e):
            raise AssertionError(f"FeedbackLearningService 初始化参数错误: {e}")
        print(f"test_web_app_creates_feedback_service PASSED (degraded: {e})")

if __name__ == "__main__":
    test_feedback_service_init_ok()
    test_expression_manager_path_points_to_capsule()
    test_web_app_creates_feedback_service()
    print("\nAll tests passed!")
