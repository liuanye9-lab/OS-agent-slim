"""personal_eval — 个人评估与 A/B 回归测试模块。

V11 新增：Personal Eval / A-B Regression / 反馈闭环。

子模块:
- schemas: 数据模型定义 (PersonalEvalCase, Rubric, ABRegressionResult, FeedbackRecord)
- eval_case: EvalCaseManager — 评估用例管理
- rubric: RubricManager — 评分维度管理
- result_scorer: ResultScorer — 按 rubric 维度评分
- ab_regression_runner: ABRegressionRunner — A/B 回归测试
- feedback_loop: FeedbackProcessor — 反馈闭环处理
"""
