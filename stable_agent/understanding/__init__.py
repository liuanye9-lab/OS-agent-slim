"""Understanding Trace — 语义理解轨迹模块 (V11 Phase 3).

职责:
- 解析用户输入的语义意图和隐含约束
- 追踪假设和不确定性
- 管理用户表达习惯 (ExpressionProfile)
- 记录纠正记录并转化为表达规则

子模块:
- schemas: 数据结构定义
- semantic_interpreter: 语义解释器 (规则版)
- expression_profile: 表达习惯管理器
- assumption_tracker: 假设追踪器
- correction_store: 纠正记录存储
"""
