"""Tests for code quality — no silent exceptions, no stray prints."""
import os
import re


def test_no_except_exception_pass():
    """stable_agent 目录下没有 except Exception: pass 模式。"""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    stable_dir = os.path.join(project_root, "stable_agent")

    # 收集 stable_agent 下所有 .py 文件（递归遍历子目录）
    py_files: list[str] = []
    for dirpath, _dirnames, filenames in os.walk(stable_dir):
        for f in filenames:
            if f.endswith('.py'):
                py_files.append(os.path.join(dirpath, f))

    silent_count = 0
    for file_path in py_files:
        with open(file_path) as fh:
            lines_list = fh.readlines()
        for i, line in enumerate(lines_list):
            stripped = line.strip()
            if stripped == "except Exception:":
                # 检查下一行是否是 pass（跳过空行和注释）
                for j in range(i + 1, min(i + 5, len(lines_list))):
                    next_stripped = lines_list[j].strip()
                    if next_stripped == "" or next_stripped.startswith("#"):
                        continue
                    if next_stripped == "pass":
                        silent_count += 1
                    break  # 只看第一个非空非注释行

    assert silent_count == 0, f"发现 {silent_count} 处 except Exception: pass"


def test_no_print_in_production():
    """workflow_state_machine.py 没有 print 语句（除 docstring）。"""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    wf_path = os.path.join(project_root, "stable_agent", "workflow_state_machine.py")
    with open(wf_path) as f:
        content = f.read()
    # 移除 docstring（三引号字符串）
    no_docstring = re.sub(r'""".*?"""', '', content, flags=re.DOTALL)
    assert "print(" not in no_docstring, "workflow_state_machine.py 中有 print 语句"
