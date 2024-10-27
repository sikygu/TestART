from collections import defaultdict
from typing import List, Tuple, Set
import re
from prefect import get_run_logger

import javalang
from javalang.tree import TryStatement, MethodDeclaration, ClassDeclaration
from typing import List


def etree_to_dict(t):
    d = {t.tag: {} if t.attrib else None}
    children = list(t)
    if children:
        dd = defaultdict(list)
        for dc in map(etree_to_dict, children):
            for k, v in dc.items():
                dd[k].append(v)
        d = {t.tag: {k: v for k, v in dd.items()}}
    if t.attrib:
        d[t.tag].update(('@' + k, v) for k, v in t.attrib.items())
    if t.text:
        text = t.text.strip()
        if children or t.attrib:
            if text:
                d[t.tag]['#text'] = text
        else:
            d[t.tag] = text
    return d


def modify_exception_type(code_lines: List[str], error_loc: str | int, exception_type: str):
    error_loc = int(error_loc)

    def get_method_name_by_loc(methods: List[MethodDeclaration]):
        for i in range(len(methods)):
            method1 = methods[i]
            method2 = methods[i + 1] if i + 1 < len(methods) else None
            if method2 is None or method1.position[0] <= error_loc < method2.position[0]:
                return method1.name

    def get_try_block_by_loc(try_blocks: List[TryStatement]):
        for tb in try_blocks:
            for statement in tb.block:
                if error_loc == statement.position[0]:
                    return tb

        return None

    def get_catch_position(start: int, types: List[str]):
        """
        :param start: 起始行下表，表示从哪一行开始找
        :param types: 目标类型，例：['IllegalArgumentException', 'NumberFormatException'] 表示找到 catch(IllegalArgumentException | NumberFormatException e)
        :return: 目标行的下标
        """
        for i in range(start, len(code_lines)):
            line = code_lines[i]
            flag = 'catch' in line
            for t in types:
                flag = flag and t in line
            if flag:
                return i

    tree = javalang.parse.parse("\n".join(code_lines))
    types = tree.types
    clazz = [x for x in types if isinstance(x, ClassDeclaration) and x.name.endswith("Test")][0]
    methods = clazz.methods
    target_method = get_method_name_by_loc(methods)
    body = [x.body for x in methods if target_method == x.name]
    assert len(body) == 1
    body = body[0]
    try_blocks = [x for x in body if isinstance(x, TryStatement)]

    if try_blocks is None or len(try_blocks) == 0:
        return False

    try_block = get_try_block_by_loc(try_blocks)
    if try_block is None:
        return False

    catch_loc = get_catch_position(try_block.position[0], try_block.catches[0].parameter.types)
    catch_statement = re.sub("catch.*\((.*) .*\)", lambda x: x.group(0).replace(x.group(1), exception_type),
                             code_lines[catch_loc], count=1)

    indent: int = len(catch_statement) - len(catch_statement.lstrip())
    indent_space: str = ' ' * indent
    indent_space_tab: str = ' ' * (indent + 4)
    code_lines[catch_loc - 1: catch_loc] = [
        f'{catch_statement}',
        f'{indent_space_tab} // Expected',
    ]
    for i in range(try_block.position[0], catch_loc):
        code_lines[i] = re.sub(f'\".*({type}).*\"',
                               lambda x: x.group(0).replace(x.group(1), exception_type), code_lines[i], count=1)
    return True

def get_local_variable_declaration(line):
    from javalang.tree import LocalVariableDeclaration, StatementExpression
    import javalang
    template = f"""
    public class Example {{
        private Boolean a;
        public void example() {{
            {line}
        }}
    }}
    """
    tree = javalang.parse.parse(template)
    method = tree.types[0].methods[0]
    statement = method.body[0]
    if isinstance(statement, LocalVariableDeclaration):
        return statement.type.name, statement.declarators[0].name, len(statement.type.dimensions)
    else:
        return None

def get_first_param(code: str, delete_param_gt3=True) -> Tuple[str, str]:
    """
    :param code: 代码行, eg: assertEquals("hello1", "hello2")
    :param delete_param_gt3: 当参数个数大于3时，是否删除第一个参数
    :return: （修改后的代码行，第一个参数）
    """
    import javalang
    template = f"""
    public class Temp{{
        public void temp(){{
            {code}
        }}
    }}
    """
    try:
        tree = javalang.parse.parse(template)
        method = tree.types[0].methods[0]
        num = len(method.body[0].expression.arguments)
        arg_0 = method.body[0].expression.arguments[0]
        arg_1 = method.body[0].expression.arguments[1]
        if num == 3 and delete_param_gt3:  # delete first param
            regex_param1 = re.escape(arg_0.value)
            code = re.sub(fr'\(\s*?{regex_param1}\s*?,', "(", code, count=1)  # remove the first param
            arg_0 = arg_1

        if isinstance(arg_0, javalang.tree.Literal) and '"' in arg_0.value:
            param1 = arg_0.value
        else:
            param1 = re.search(r'\(([^\n]+?),\s', code).group(1)
        return code, param1
    except Exception as e:
        get_run_logger().exception(e)
        return code, ""

def fix_unit_test(stacktrace: str, test_lines: List[str], locs: List[int], lines: List[str]):
    """
    Fix the unit test code based on the stacktrace
    :param stacktrace:
    :param test_lines: 源代码
    :param locs:  错误行号
    :param lines: 测试代码
    :return:
    """
    stacktrace_lines = stacktrace.split('\n')

    # Step 1: Check if AssertionError is present in the stacktrace
    if 'AssertionError' in stacktrace or 'org.junit.ComparisonFailure' in stacktrace:
        # Failure type processing
        for loc, code in zip(locs, lines):
            # Check if the line contains assertion statements
            # Replace the incorrect assert statement based on the expectation and actual value
            if 'assertFalse' in code:
                # Negate the expression for assertFalse
                fixed_code = code.replace('assertFalse', 'assertTrue')
            elif 'assertTrue' in code:
                # Negate the expression for assertTrue
                fixed_code = code.replace('assertTrue', 'assertFalse')
            elif 'assertNull' in code:
                # Negate the expression for assertNull
                fixed_code = code.replace('assertNull', 'assertNotNull')
            elif 'assertNotNull' in code:
                # Negate the expression for assertNotNull
                fixed_code = code.replace('assertNotNull', 'assertNull')
            elif 'assertArrayEquals' in code:
                fixed_code = code  # TODO: fix array
            elif 'assertEquals' in code:
                code, param1 = get_first_param(code)
                regex_param1 = re.escape(param1)
                param1_with_bracket = fr'\(\s*?{regex_param1}\s*?,'

                result = re.search("expected:(.*) but was:(.*)", stacktrace)
                expected = None
                was = None
                if result:
                    expected = result.group(1).strip()
                    was = result.group(2).strip()

                if expected is None:  # eg: assertEquals("hello\n", "hello\r\n")
                    get_run_logger().error("expected is None")
                    return
                assert was is not None

                def replace_brackets(string: str):

                    if string.startswith("<["):
                        string = string.replace("<[", "")
                    elif string.startswith("<..."):
                        string = string.replace("<...", "")
                        string = string.replace("[", "")
                    elif string.startswith("<"):
                        string = string.replace("<", "")
                        string = string.replace("[", "")
                    else:
                        return string

                    if string.endswith("]>"):
                        string = string.replace("]>", "")
                    elif string.endswith("...>"):
                        string = string.replace("...>", "")
                        string = string.replace("]", "")
                    elif string.endswith(">"):
                        string = string.replace(">", "")
                        string = string.replace("]", "")
                    return string

                expected = replace_brackets(expected)
                was = replace_brackets(was)

                was = was.replace("\\u", "\\\\\\\\u")  # for java unicode
                replace_str = ""
                value = re.search("<(.*)>", was)
                if value:
                    value = value.group(1)
                    if was.startswith("java.lang.Integer") \
                            or was.startswith("java.lang.Boolean") \
                            or was.startswith("java.lang.Float") \
                            or was.startswith("java.lang.Double") \
                            or was.startswith("java.lang.Byte"):
                        replace_str = fr"({value},"
                    elif was.startswith("java.lang.String"):
                        value = f'"{value}"'
                        replace_str = fr"({value},"
                    elif was.startswith("java.lang.Long"):
                        replace_str = fr"({value}L,"
                elif was.startswith("null"):
                    replace_str = fr"(null,"
                else:
                    if expected and expected in param1:  # expected can't be empty string
                        value = param1.replace(expected, was)
                        replace_str = fr"({value},"
                    else:
                        if not expected.isnumeric():
                            was = f'"{was}"'
                        replace_str = fr"({was},"
                try:
                    fixed_code = re.sub(param1_with_bracket, replace_str, code, count=1)
                except Exception as e:
                    try:
                        fixed_code = re.sub(param1_with_bracket, replace_str, code, count=1)
                    except Exception as e:
                        # if still failed, then use origin code
                        get_run_logger().error(f"replace fail! origin: {code}, replace_str: {replace_str}, pattern: {param1_with_bracket}, error: {e}")
                        fixed_code = code


            else:
                fixed_code = code
            # Replace the original code with the fixed code
            test_lines[loc - 1] = fixed_code

    else:
        error_type = stacktrace_lines[0].split(':')[0].strip()
        # 筛选目标行号
        target_loc = []
        for loc, line in zip(locs, lines):
            if 'public void' not in line:
                target_loc.append(loc)

        assert len(target_loc) >= 1
        target_loc = target_loc[0]

        if modify_exception_type(test_lines, target_loc, error_type):
            return  # 错误行在try_catch语句中，处理后直接返回

        target_line = test_lines[target_loc - 1]

        # 分析是否包含变量定义
        def_statement = None
        dinfo = get_local_variable_declaration(target_line)
        if dinfo is not None:
            dtype, dname, dimensions = dinfo
            # 判断是否为基本类型
            type_map = {
                'int': 'Integer',
                'float': 'Float',
                'double': 'Double',
                'boolean': 'Boolean',
                'char': 'Character',
                'byte': 'Byte',
                'short': 'Short',
                'long': 'Long',
            }
            boxed_dtype = None
            if dtype in type_map and dimensions == 0:
                boxed_dtype = type_map[dtype]
            dtype = f"{dtype}{'[]' * dimensions}"
            boxed_dtype = f"{boxed_dtype}{'[]' * dimensions}" if boxed_dtype else None
            def_statement = f'{boxed_dtype or dtype} {dname} = null;'
            target_line = re.sub(f"{dtype}\s*?{dname}".replace("[", "\["), dname, target_line, count=1)

        # 否则添加try_catch语句
        indent: int = len(target_line) - len(target_line.lstrip())
        indent_space: str = ' ' * indent
        indent_space_tab: str = ' ' * (indent + 4)
        new_lines = [
            f'{indent_space}{def_statement or ""}\n'
            f'{indent_space}try {{',
            f'{indent_space_tab}{target_line.lstrip()}',
            f'{indent_space_tab}fail("Expected {error_type}");\n'
            f'{indent_space}}}',
            f'{indent_space}catch ({error_type} e) {{',
            f'{indent_space_tab}// Expected',
            f'{indent_space}}}',
        ]
        test_lines[target_loc - 1:target_loc] = new_lines

__all__ = ["etree_to_dict", "modify_exception_type", "get_local_variable_declaration", "get_first_param", "fix_unit_test"]