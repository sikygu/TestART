from typing import List, Tuple, Set
import re
import os
from app.classes import CloverTestRequest, TestStatus, CloverTestHandler, Template
from typing import List


def extract_error_content(file_path):
    """
    处理maven编译错误日志，将无关信息去除
    :param file_path: 日志文件路径
    :return: 错误信息
    """
    with open(file_path, 'r') as file:
        lines = file.readlines()

    error_lines = []
    error_section = False

    for line in lines:
        if '[ERROR] COMPILATION ERROR :' in line:
            error_section = True
            error_lines.append(line)
        elif '[INFO] BUILD FAILURE' in line:
            error_section = False
            error_lines.append(line)
            break
        elif error_section:
            error_lines.append(line)

    output_lines = [line for line in error_lines if '[INFO]' not in line]
    # trim
    output_lines = [line.strip() for line in output_lines]

    return "\n".join(output_lines)


def get_feedback(request: CloverTestRequest, status: TestStatus, states: dict):
    feedback = None
    if status.failures > 0:
        feedback = Template(content=request.failure_prompt_template).format(states)
    elif status.errors > 0:
        feedback = Template(content=request.error_prompt_template).format(states)
    elif status.value != 1:
        feedback = Template(content=request.success_prompt_template).format(states)
    return feedback


def generate_compile_error_feedback(filepath: str, stacktrace: str):
    stacktrace += "\n[ERROR]"  # for regex match to work
    filepath = filepath.replace('\\', '/')
    results = re.findall(rf"{re.escape(filepath)}:\[(\d+),(\d+)] (.*?)(?=\[ERROR\])", stacktrace,
                         re.MULTILINE | re.DOTALL)
    with open(filepath, 'r', encoding='utf-8') as file:
        code_lines = file.readlines()

    # (keyword, error_reason)
    # eg. ('TestEnum','cannot find symbol')
    errors: List[Tuple[str, str]] = []
    for line, loc, reason in results:
        line = int(line) - 1
        loc = int(loc) - 1

        code_line = code_lines[line]
        if 'public void' in code_line:
            continue
        errors.append((code_line, reason))

    errors: Set[Tuple[str, str]] = set(errors)
    feedback = ["Your code has compilation errors:\n"]
    for i, (code_line, reason) in enumerate(errors):
        feedback.append(f"{i + 1}. {code_line.strip()} // {reason}")

    feedback.append("\nRegenerate your test code in a java code cell!")
    return "\n".join(feedback)




def get_class_imports(source_folder: str, stacktrace: str):
    pattern = r".*symbol:\s*class\s(.*)$"
    class_names = re.findall(pattern, stacktrace, re.MULTILINE)
    class_names = list(set(class_names))
    # 递归遍历source文件夹，找到所有的class文件
    class_map = {}  # {class_name: [package_reference, ...]}
    for root, dirs, files in os.walk(source_folder):
        for file in files:
            if file.endswith(".java"):
                class_name = file[:-5]
                root = root.replace("\\", ".")
                root = root.replace("/", ".")
                if "src.main.java." not in root:
                    continue
                ref = root.split("src.main.java.")[1]
                if class_name not in class_map:
                    class_map[class_name] = [ref]
                else:
                    class_map[class_name].append(ref)
    imports = []
    for name in class_names:
        if name not in class_map:
            return None

        refs = set(class_map[name])
        for ref in refs:
            imports.append(f"import {ref}.{name};")
    return imports


__all__ = ["extract_error_content", "get_feedback", "generate_compile_error_feedback", "get_class_imports"]
