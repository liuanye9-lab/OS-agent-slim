"""测试 Self-Iteration 实验文件 (Phase 10+12)。

验证:
1. 实验目录文件完整
2. dataset.jsonl 格式正确
3. run_experiment.py 可导入
4. results.json 格式正确
5. report.md 标注 demo
"""

import json
import os
import pytest


EXPERIMENTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "experiments", "self_iteration_5_rounds",
)


class TestExperimentFiles:
    """实验文件完整性测试。"""

    def test_dataset_exists(self):
        """dataset.jsonl 存在且非空。"""
        path = os.path.join(EXPERIMENTS_DIR, "dataset.jsonl")
        assert os.path.exists(path), f"{path} 不存在"
        with open(path, "r", encoding="utf-8") as f:
            lines = [l for l in f if l.strip()]
        assert len(lines) == 15  # 15 个任务

    def test_dataset_format(self):
        """dataset.jsonl 每行是有效 JSON。"""
        path = os.path.join(EXPERIMENTS_DIR, "dataset.jsonl")
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    obj = json.loads(line)
                    assert "id" in obj
                    assert "type" in obj
                    assert "task" in obj

    def test_run_experiment_exists(self):
        """run_experiment.py 存在。"""
        path = os.path.join(EXPERIMENTS_DIR, "run_experiment.py")
        assert os.path.exists(path)

    def test_results_exists(self):
        """results.json 存在且格式正确。"""
        path = os.path.join(EXPERIMENTS_DIR, "results.json")
        assert os.path.exists(path)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert len(data) == 5  # 5 rounds
        for round_data in data:
            assert "round" in round_data
            assert "quality_score" in round_data
            assert "hallucination_rate" in round_data
            assert "token_usage" in round_data

    def test_report_marks_demo(self):
        """report.md 明确标注 simulated demo。"""
        path = os.path.join(EXPERIMENTS_DIR, "report.md")
        assert os.path.exists(path)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "simulated demo" in content.lower()
        assert "disclaimer" in content.lower()
