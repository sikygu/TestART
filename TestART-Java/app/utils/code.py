import re
from prefect import get_run_logger

from app.classes import CloverTestRequest, TestStatus, CloverTestHandler, Template
from app.constants import CONFIG, ExceptionCode
from app.exceptions import ApiException
import javalang
from typing import List


def extract_codeblock(text: str, lang: str | List[str] = "java") -> str | None:
    """
    extract code block from text
    :param lang: code lang
    :param text: text
    :return: codeblock
    """
    if isinstance(lang, str):
        lang = [lang]

    for code_lang in lang:
        pattern = rf"```{code_lang}(.*?)```"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            code = match.group(1).strip()
            return code
        else:
            return None


def replace_package_info(package_reference: str, content: str, is_test: bool):
    header = f'package {package_reference};\n' if package_reference else ""
    if is_test:
        package_imports = ""
        splits = package_reference.split(".") if package_reference else []
        for i in range(len(splits) - 1):
            package_imports += f"import {'.'.join(splits[:i + 1])}.*;\n"
        added_imports = [
            "import org.junit.Test;",
            # "import java.io.*;",
            "import java.util.*;",
            # "import java.awt.*;",
            # "import java.text.*;",
            # "import java.awt.geom.*;",
            "import static org.junit.Assert.*;",
            # "import java.lang.reflect.*;",
        ]
        for added_import in added_imports:
            if added_import not in content:
                header += f"{added_import}\n"
    pattern = r'package\s+([\w.]+);'
    replaced_content = re.sub(pattern, header, content)
    if not re.search(pattern, content):
        replaced_content = header + replaced_content
    return replaced_content


def add_imports(content: str, imports: List[str]):
    _imports = '\n'.join(imports)
    lines = content.splitlines()
    started = False
    for i, line in enumerate(lines):
        if line.startswith("package"):
            started = True
            continue
        if started and line.startswith("import"):
            lines[i] = f"{_imports}\n{line}\n"
            break
    return '\n'.join(lines)


def insert_test_methods(origin_code, testcase: str | List[str]):
    if isinstance(testcase, str):
        testcase = [testcase]

    def get_function_name(input):
        match = re.search(r'public void (\w+)\(\)', input)
        # 输出匹配结果
        if match:
            return match.group(1)
        else:
            return None

    def remove_testcase(code: str, origin_names: List[str], new_names: List[str]):
        lines = code.splitlines()
        duplicate_names = set(origin_names) & set(new_names)
        for name in duplicate_names:
            for start, line in enumerate(lines):
                if f"public void {name}(" in line:
                    end = start + 1
                    stack1 = ["{"]
                    while len(stack1) != 0:
                        end += 1
                        line = lines[end - 1]
                        for ch in line:
                            if ch == "{":
                                stack1.append(ch)
                            elif ch == "}":
                                stack1.pop()
                        if end > 10000:
                            assert False
                    lines = lines[:start - 1] + lines[end:]
                # end if
        # end for
        return "\n".join(lines)

    new_testcase_name = [get_function_name(x) for x in testcase]
    origin_testcase_name: List[str] = re.findall("@Test.*\n.*public void (\w+)\(\)", origin_code)

    # 删去已经存在的测试用例
    origin_code = remove_testcase(origin_code, origin_testcase_name, new_testcase_name)

    testcase = "\n".join(testcase)

    index = origin_code.rfind('@Test')

    if index != -1:
        new_content = origin_code[:index] + '\n' + testcase + '\n' + origin_code[index:]
        return new_content
    else:
        new_content = origin_code.rstrip()[:-1] + '\n' + testcase + '\n\n}'
        return new_content


def extract_class_name(content):
    pattern = r'class\s+([\w]+)'
    match = re.search(pattern, content)

    if match:
        class_name = match.group(1)
        return class_name
    else:
        return None


def extract_test_methods(incremental_code: str) -> List[str]:
    """
    Extract test methods from incremental code
    :param incremental_code: 增量测试代码
    :return: 测试方法
    """
    test_methods = []
    lines = incremental_code.split('\n')
    stack = []
    capture = False
    method = ""

    for line in lines:
        stripped_line = line.strip()

        if '@Test' in stripped_line and not capture:
            capture = True
            method += line + '\n'
            continue

        if capture:
            method += line + '\n'
            for char in stripped_line:
                if char == '{':
                    stack.append(char)
                elif char == '}':
                    stack.pop()
                    if len(stack) == 0:
                        test_methods.append(method)
                        method = ""
                        capture = False
                        break

    return test_methods


def remove_invalid_testcase(clover_test_js_path: str, test_code: str):
    try:
        handler = CloverTestHandler(clover_test_js_path, test_code)
        handler.parse_test_js()
        return handler.remove_failed_tests()
    except Exception as e:
        get_run_logger().exception(e)
        raise ApiException(ExceptionCode.FIX_ERROR,
                           f"TestExecutor remove_invalid_testcase error: {e}.")


def syntax_java_code(code: str):
    try:
        tree = javalang.parse.parse(code)
    except Exception as e:
        get_run_logger().exception(e)
        raise ApiException(ExceptionCode.SYNTAX_ERROR, str(e))


__all__ = ["extract_codeblock", "replace_package_info", "insert_test_methods", "extract_class_name",
           "extract_test_methods", "remove_invalid_testcase", "syntax_java_code", "add_imports"]
