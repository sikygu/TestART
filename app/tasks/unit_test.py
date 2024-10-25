import asyncio
import concurrent.futures
import difflib
import threading
import zipfile
from typing import Tuple, Any, List, Dict
import re
import xml.etree.ElementTree as ET
import subprocess
import psutil
import tiktoken
from langchain_community.chat_models import ChatOpenAI
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate
from pydantic import BaseModel
import os
import time
from langchain.schema import BaseMessage, HumanMessage, SystemMessage, AIMessage
import re
import json
from prefect import get_run_logger, task, runtime
from prefect.artifacts import create_markdown_artifact, create_table_artifact
from app.classes import Template, TestStatus, CloverTestRequest, LLMConfig, Markdown, TestController, LLMRecord
from app.exceptions import ApiException
from app.constants import ExceptionCode, CONFIG, CoverageMode
from app.utils import replace_package_info, extract_class_name, etree_to_dict, extract_error_content, fix_unit_test, \
    extract_test_methods, insert_test_methods, add_imports


class CloverTestExecutor:
    def __init__(self,
                 mode: CoverageMode,
                 source_code: str,
                 project_absolute_path: str,
                 package_reference: str = "",
                 source_class_name: str = "",
                 test_class_name: str = "",
                 source_function_name: str = "",
                 source_function_start: int = -1,
                 source_function_end: int = -1,
                 auto_fix: bool = True,
                 ):
        logger = get_run_logger()
        self.project_name: str = "TestJavaCode"
        self.package_reference: str = package_reference
        self.clover_output_relative_path: str = "/target/site/clover"
        self.mvn_output_relative_path: str = "/target/surefire-reports"
        self.source_code: str = source_code

        self.test_code: str | None = None
        self.source_class_name: str = source_class_name
        self.test_class_name: str = test_class_name
        self.source_function_name: str = source_function_name
        self.source_function_start: int = source_function_start
        self.source_function_end: int = source_function_end
        self.project_absolute_path: str = project_absolute_path
        self.test_folder = f"{self.project_absolute_path}/src/test/java/{self.package_reference.replace('.', '/')}"
        self.source_folder = f"{self.project_absolute_path}/src/main/java/{self.package_reference.replace('.', '/')}"
        self.auto_fix = auto_fix
        self.code_analysis = ""
        self.mode: CoverageMode = mode

        logger.info("cleaning...")
        try:
            asyncio.run(self.clean())
        except Exception as e:
            logger.exception(e)
            logger.error("clean error")

        logger.info("config initializing...")
        try:
            if not os.path.exists(self.test_folder):
                os.makedirs(self.test_folder)
                logger.warning(f"test folder {self.test_folder} not exists, created")
            if not os.path.exists(self.source_folder):
                os.makedirs(self.source_folder)
                logger.warning(f"source folder {self.source_folder} not exists, created")

        except Exception as e:
            raise ApiException(ExceptionCode.INIT_ERROR, f"TestExecutor init error", e)

        logger.info("config init done")
        logger.info("code writing...")
        try:
            # temp_len = len(self.source_code.splitlines())
            # self.source_code = replace_package_info(self.package_reference, self.source_code, is_test=False)
            # source_code_offset = len(self.source_code.splitlines()) - temp_len
            # assert source_code_offset == 0, "source code offset error"
            # self.source_function_start += source_code_offset
            # self.source_function_end += source_code_offset
            self.test_code = None

            if not self.source_class_name:
                self.source_class_name = extract_class_name(self.source_code)
            if not self.test_class_name:
                self.test_class_name = f"{self.source_class_name}Test"

            self.test_filepath = f"{self.project_absolute_path}/src/test/java/{self.package_reference.replace('.', '/')}/{self.test_class_name}.java"
            self.source_filepath = f"{self.project_absolute_path}/src/main/java/{self.package_reference.replace('.', '/')}/{self.source_class_name}.java"
            self.test_reference = f"{self.package_reference}.{self.test_class_name}" if self.package_reference else self.test_class_name
            self.source_reference = f"{self.package_reference}.{self.source_class_name}" if self.package_reference else self.test_class_name
            self.mvn_xml_path = f"{self.project_absolute_path}{self.mvn_output_relative_path}/TEST-{self.test_reference}.xml"
            self.clover_xml_path = f"{self.project_absolute_path}{self.clover_output_relative_path}/clover.xml"
            self.clover_source_js_path = f"{self.project_absolute_path}{self.clover_output_relative_path}/{self.package_reference.replace('.', '/') if self.package_reference else 'default-pkg'}/{self.source_class_name}.js"
            self.clover_test_js_path = f"{self.project_absolute_path}{self.clover_output_relative_path}/{self.package_reference.replace('.', '/') if self.package_reference else 'default-pkg'}/{self.test_class_name}.js"

            self.source_report = None
            self.test_report = None

        except Exception as e:
            logger.exception(e)
            raise ApiException(ExceptionCode.INIT_ERROR, f"TestExecutor init error2", e)


    def _parse_clover_report(self):
        logger = get_run_logger()
        tree = ET.parse(self.clover_xml_path)
        root = tree.getroot()
        root_dict = etree_to_dict(root)['coverage']
        source_packages: list = root_dict['project'][0]['package']
        test_packages: list = root_dict['testproject'][0]['package']

        # 找到focal class & focal method
        source_package = None
        for package in source_packages:
            if (self.package_reference if self.package_reference else "default-pkg") == package['@name']:
                source_package = package
                break
        assert source_package is not None

        source_files = source_package['file']
        source_file = None
        for file in source_files:
            if f"{self.source_class_name}.java" == file['@name']:
                source_file = file
                break
        assert source_file is not None

        # 假设测试文件（测试类）只有一个
        test_file = test_packages[0]['file'][0]

        def handle(file: dict, code: dict):
            """
            将代码内容嵌入file节点，便于后续处理
            :param file: dict, 代表解析后的结点
            :param code: dict, {行号，代码内容}
            :return:
            """
            if isinstance(file['class'], dict):
                file['class'] = [file['class']]
            file['class'] = {clazz['@name']: clazz for clazz in file['class']}
            file['line'] = [dict(code=code[int(line['@num'])], **line) for line in file['line']]

        def extract_code_from_source(path: str):
            with open(path, encoding='utf8') as f:
                content = f.readlines()
            return {x + 1: content[x].strip() for x in range(len(content))}

        source_code = extract_code_from_source(self.source_filepath)
        test_code = extract_code_from_source(self.test_filepath)

        handle(source_file, source_code)
        handle(test_file, test_code)

        self.source_report = source_file
        self.test_report = test_file

        report_lines = self.source_report['line']
        branches = [line for line in report_lines if line['@type'] == 'cond']
        lines = [line for line in report_lines if line['@type'] == 'stmt']

        # 当测试某一个方法时，筛选出这个方法的line/branch
        if self.source_function_name:
            branches = [branch for branch in branches if
                        self.source_function_start <= int(branch["@num"]) <= self.source_function_end]
            lines = [line for line in lines if
                     self.source_function_start <= int(line["@num"]) <= self.source_function_end]

        uncovered_branch = []
        false_uncovered_branch = []
        true_uncovered_branch = []
        unreachable_branch = []

        for branch in branches:
            if branch['@truecount'] == '0' or branch['@falsecount'] == '0':
                uncovered_branch.append(branch)
            if branch['@truecount'] != '0' and branch['@falsecount'] == '0':
                false_uncovered_branch.append(branch)
            if branch['@truecount'] == '0' and branch['@falsecount'] != '0':
                true_uncovered_branch.append(branch)
            if branch['@truecount'] == '0' and branch['@falsecount'] == '0':
                unreachable_branch.append(branch)

        branch_num_uncovered = len(false_uncovered_branch) + len(true_uncovered_branch) + 2 * len(unreachable_branch)
        branch_num_total = 1 if len(branches) == 0 else len(branches) * 2
        branch_num_covered = branch_num_total - branch_num_uncovered

        uncovered_line = []
        for line in lines:
            if line['@count'] == '0':
                uncovered_line.append(line)

        line_num_uncovered = len(uncovered_line)
        line_num_total = 1 if len(lines) == 0 else len(lines)
        line_num_covered = line_num_total - line_num_uncovered

        if line_num_covered == 0:
            logger.warning("not covered anything!")
            branch_num_covered = 0

        branch_rate_tuple = (branch_num_covered, branch_num_total, branch_num_covered / branch_num_total)
        line_rate_tuple = (line_num_covered, line_num_total, line_num_covered / line_num_total)

        branch_covered_result: str = self.get_branch_covered_result(true_uncovered_branch, false_uncovered_branch,
                                                                    unreachable_branch)
        line_covered_result: str = self.get_line_covered_result(uncovered_line)
        covered_result = branch_covered_result if self.mode == CoverageMode.BRANCH_COVERAGE else line_covered_result
        return line_rate_tuple, branch_rate_tuple, covered_result

    def get_branch_covered_result(self, true_uncovered_branch, false_uncovered_branch, unreachable_branch) -> str:
        method_code = self.source_code.split('\n')[self.source_function_start - 1:self.source_function_end]
        for b in true_uncovered_branch:
            offset = int(b['@num']) - self.source_function_start
            method_code[offset] = f"{method_code[offset].rstrip()} // [[true condition not covered]]"
        for b in false_uncovered_branch:
            offset = int(b['@num']) - self.source_function_start
            method_code[offset] = f"{method_code[offset].rstrip()} // [[false condition not covered]]"
        for b in unreachable_branch:
            offset = int(b['@num']) - self.source_function_start
            method_code[offset] = f"{method_code[offset].rstrip()} // [[unreached branch]]"
        return "\n".join(method_code)

    def get_line_covered_result(self, uncovered_line) -> str:
        method_code = self.source_code.split('\n')[self.source_function_start - 1:self.source_function_end]
        for b in uncovered_line:
            offset = int(b['@num']) - self.source_function_start
            method_code[offset] = f"{method_code[offset].rstrip()} // [[line not covered]]"
        return "\n".join(method_code)

    async def _run_command(self, command: str) -> int:
        logger = get_run_logger()

        async def kill_proc_tree(pid, including_parent=True):
            parent = psutil.Process(pid)
            children = parent.children(recursive=True)
            for child in children:
                child.kill()
            gone, still_alive = psutil.wait_procs(children, timeout=5)
            if including_parent:
                parent.kill()
                parent.wait(5)

        import os
        os.environ["JAVA_TOOL_OPTIONS"] = "-Duser.language=en"
        io = asyncio.subprocess.PIPE
        process = await asyncio.create_subprocess_shell(command, shell=True, stdout=io, stderr=io, cwd=self.project_absolute_path)

        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=120)
        except asyncio.TimeoutError as e:
            await kill_proc_tree(process.pid)
            raise e

        if process.returncode == 0:
            logger.info(stdout)
        else:
            raise ApiException(ExceptionCode.RUN_ERROR, f"TestExecutor run command error: {stderr}")

        return process.returncode

    def _extract_code_from_stacktrace(self, stacktrace: str, test_code_copy: str):
        logger = get_run_logger()
        source_reference = self.source_reference
        test_reference = self.test_reference

        source_lines = self.source_code.split("\n")
        test_lines = test_code_copy.split("\n")
        loc_list = []
        loc_num_list = []
        code_list = []
        for line in stacktrace.split('\n'):
            if f"at {test_reference}" in line:
                loc = re.search(r'\((.*?)\)', line).group(1)
                loc_num = int(loc.split(':')[1])
                code = test_lines[loc_num - 1]

                # record test code, for fix
                loc_list.append(loc)
                code_list.append(code)
                loc_num_list.append(loc_num)

            elif f"at {source_reference}" in line:
                loc = re.search(r'\((.*?)\)', line).group(1)
                loc_num = int(loc.split(':')[1])
                code = source_lines[loc_num - 1]
            else:
                continue

        if self.auto_fix:
            _test_lines_cpy = test_lines.copy()
            try:
                if not loc_num_list:
                    logger.warning(f"no loc_num_list, skip fix")
                else:
                    fix_unit_test(stacktrace, test_lines, loc_num_list, code_list)
                    self.test_code = "\n".join(test_lines)
            except Exception as e:
                logger.error(f"fix error", e)
                self.test_code = "\n".join(_test_lines_cpy)

        return "".join([f"{loc.strip()}: {code.strip()}\n" for loc, code in zip(loc_list, code_list)])

    def _report(self) -> tuple[TestStatus, dict]:
        """
        :param xml_path: mvn test report path
        :return: (is_terminated, (covered_lines, total_lines, branch_coverage_rate), feedback)

        """
        logger = get_run_logger()

        tree = ET.parse(self.mvn_xml_path)
        root = tree.getroot()
        attr = root.attrib

        try:
            (line_covered, line_total, line_coverage_rate), \
                (branch_covered, branch_total, branch_coverage_rate), \
                covered_result = self._parse_clover_report()
        except Exception as e:
            raise ApiException(ExceptionCode.REPORT_ERROR,
                               f"TestExecutor parse clover class report error", e)

        if self.auto_fix and (int(attr['failures']) > 0 or int(attr['errors']) > 0):
            logger.warning(
                f"auto_fix=True, try to fix {int(attr['failures'])} failures and {int(attr['errors'])} errors!")

        error_code_message = ""
        error_message = ""
        test_code_copy = self.test_code  # 修复应用到test_code上，但是要从原本的代码定位错误
        try:
            if int(attr['failures']) > 0:
                errors = [x.find('failure').text for x in root.findall('testcase') if x.find('failure') is not None]
                error_message = "\n".join(
                    [
                        f"```java\n{error_code}```\nerror: `{error_stacktrace}`\n"
                        for error_code, error_stacktrace in
                        zip(
                            [self._extract_code_from_stacktrace(x, test_code_copy) for x in errors],
                            [x.splitlines()[0] for x in errors]
                        )
                    ]
                )

            if int(attr['errors']) > 0:
                errors = [x.find('error').text for x in root.findall('testcase') if x.find('error') is not None]
                error_message = "\n".join(
                    [
                        f"```java\n{error_code}```\nerror: `{error_stacktrace}`\n"
                        for error_code, error_stacktrace in
                        zip(
                            [self._extract_code_from_stacktrace(x, test_code_copy) for x in errors],
                            [x.splitlines()[0] for x in errors]
                        )
                    ]
                )

        except Exception as e:
            raise ApiException(ExceptionCode.REPORT_ERROR, f"TestExecutor extract code error", e)

        state = {**self.__dict__,
                 **{key: str(value) for key, value in locals().items()}}
        failures = int(attr['failures'])
        errors = int(attr['errors'])
        skipped = int(attr['skipped'])
        tests = int(attr['tests'])
        passed = tests - failures - errors - skipped

        status = TestStatus(bc=branch_covered,
                            bt=branch_total,
                            br=branch_coverage_rate,
                            lc=line_covered,
                            lt=line_total,
                            lr=line_coverage_rate,
                            tests=tests,
                            failures=failures,
                            errors=errors,
                            skipped=skipped,
                            passed=passed,
                            mode=self.mode,
                            )
        return status, state

    async def compile(self):
        logger = get_run_logger()
        try:
            await self._run_command("mvn compile")
        except ApiException as e:
            raise ApiException(ExceptionCode.COMPILE_ERROR, f"Compile error! Check your code and try again.")
    async def test_compile(self):
        logger = get_run_logger()
        try:
            await self._run_command("mvn test-compile > test-compile.txt")
        except ApiException as e:
            error_message = extract_error_content(f"{self.project_absolute_path}/test-compile.txt")
            raise ApiException(ExceptionCode.COMPILE_ERROR, f"Test Code Compile error! \n {error_message}", e)

    async def run(self, test_code: str | None = None) -> tuple[TestStatus, dict]:
        logger = get_run_logger()
        if test_code is not None:
            self.test_code = test_code
            self.save_test_code()
        try:
            await self._run_command("mvn test-compile > test-compile.txt")
        except ApiException as e:
            # read compile error
            error_message = extract_error_content(f"{self.project_absolute_path}/test-compile.txt")
            raise ApiException(ExceptionCode.COMPILE_ERROR, f"Test Code Compile error! \n {error_message}", e)

        try:
            await self._run_command(
                f'mvn clover:setup test clover:aggregate clover:clover -Djava.awt.headless=true')
        except ApiException as e:
            raise ApiException(ExceptionCode.TEST_ERROR, f"Successfully compile, but test error!", e)
        except asyncio.TimeoutError as e:
            raise ApiException(ExceptionCode.TEST_ERROR, f"Test timeout! Check your code and try again.", e)

        try:
            return self._report()
        except ApiException as e:
            raise ApiException(e.error_code, f"TestExecutor report error", e)
        except Exception as e:
            raise ApiException(ExceptionCode.REPORT_ERROR, f"TestExecutor report error", e)

    async def clean(self):
        import shutil
        await self._run_command("mvn clean")
        shutil.rmtree(f"{self.project_absolute_path}/src/main/java")
        shutil.rmtree(f"{self.project_absolute_path}/src/test/java")

    def try_insert_test_methods(self, new_test_code):
        if self.test_code is not None:
            test_methods: List = extract_test_methods(new_test_code)
            code = insert_test_methods(self.test_code, test_methods)
        else:
            code = replace_package_info(self.package_reference, new_test_code, is_test=True)
        self.test_code = code

    def add_imports(self, imports: List[str]):
        code = add_imports(self.test_code, imports)
        self.test_code = code


    def save_test_code(self):
        get_run_logger().info(f"save test code")
        with open(self.test_filepath, 'w', encoding='utf8') as f:
            f.write(self.test_code)

    def get_class_map(self):
        # 递归遍历source文件夹，找到所有的class文件
        class_map = {} # {class_name: package_reference}
        for root, dirs, files in os.walk(self.source_folder):
            for file in files:
                if file.endswith(".java"):
                    class_name = file[:-5]
                    class_map[class_name] = root.split("src/main/java/")[1][:-1].replace("/", ".")



@task(task_run_name="Init Executor")
def init_clover_executor_TASK(request: CloverTestRequest, project_path: str) -> CloverTestExecutor:
    return CloverTestExecutor(mode=request.mode,
                              source_code=request.source_code,
                              package_reference=request.package_reference,
                              source_class_name=request.source_class_name,
                              test_class_name=request.test_class_name,
                              source_function_name=request.source_function_name,
                              source_function_start=request.source_function_start,
                              source_function_end=request.source_function_end,
                              project_absolute_path=project_path,
                              auto_fix=request.auto_fix)


@task(task_run_name="Compile")
async def compile_java_project_TASK(executor: CloverTestExecutor):
    await executor.compile()


def get_cache_key(context, parameters: dict):
    import hashlib
    prompt = parameters['prompt']
    version = parameters['cache_key']
    md5 = hashlib.md5()
    md5.update(f"{version}".join([x.content for x in prompt]).encode('utf-8'))
    key = md5.hexdigest()
    return key


@task(task_run_name="LLM Call ({description})",
      cache_key_fn=get_cache_key)
async def llm_call_TASK(llm: ChatOpenAI, prompt: List[BaseMessage], cache_key: int, description: str = "", force_response: str = "") -> LLMRecord:

    tiktoken_encoder = tiktoken.encoding_for_model("gpt-3.5-turbo")
    logger = get_run_logger()
    in_tokens = sum([len(tiktoken_encoder.encode(x.content)) for x in prompt])

    # 判断是否超出长度限制
    max_tokens: int | None = 16000 - in_tokens
    if max_tokens > 4000:
        max_tokens = None
    elif max_tokens < 300:
        raise ApiException(ExceptionCode.LLM_ERROR, f"{in_tokens} too long")

    llm.max_tokens = max_tokens

    start_time_ms = int(time.time() * 1000)
    timeout_delay = [0, 4, 16, 64]
    retry = 0
    response = None
    while True and not force_response:
        try:
            # do not use ainvoke (async invoke), timeout for some reason
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(None, llm.invoke, prompt)
        except Exception as e:
            retry += 1
            await asyncio.sleep(timeout_delay[retry])
            logger.warning(f"LLM Call Error: {e}, retry: {retry} / {len(timeout_delay)}")
            logger.warning(f"delay for {timeout_delay[retry]} seconds")
            if retry >= 3:
                raise ApiException(ExceptionCode.LLM_ERROR, f"LLM Call Error: {e}")
            else:
                continue
        break
    content = response.content if not force_response else force_response
    if force_response:
        logger.warning(f"force_response")
    out_tokens = len(tiktoken_encoder.encode(content))
    end_time_ms = int(time.time() * 1000)

    record = LLMRecord(
        in_tokens=in_tokens,
        out_tokens=out_tokens,
        prompt=[{'type': x.type, 'content': x.content} for x in prompt],
        response=content,
        start_time_ms=start_time_ms,
        end_time_ms=end_time_ms,
        description=description,
    )
    # 记录交互历史
    prompt.append(AIMessage(content=content))
    format_prompt: str = "\n".join([
        f'\n**{x.type}:**\n{x.content.strip()}'
        for x in prompt
    ])

    await create_markdown_artifact(
        Markdown()
        .table(
            [
                {
                    "description": description,
                    "in_tokens": in_tokens,
                    "out_tokens": out_tokens,
                    "start_time": start_time_ms,
                    "end_time": end_time_ms,
                }
            ]
        )
        .header("prompt")
        .text(format_prompt)
        .header("response")
        .text(content)
        .build()
    )
    return record


@task(task_run_name="Run Test({description})")
async def run_test_TASK(executor: CloverTestExecutor, test_code: str | None = None, description=""):
    before = test_code
    if before is None:
        before = executor.test_code
    status, state = await executor.run(test_code)
    status.test_code = before
    status.fixed_test_code = executor.test_code
    code_diff = None
    if before and status.fixed_test_code:
        code_diff = '\n'.join(
            list(difflib.Differ().compare(before.splitlines(), status.fixed_test_code.splitlines())))
    await create_markdown_artifact(
        Markdown()
        .table(
            [
                {
                    "description": description,
                    "branch": f"{status.bc} / {status.bt} / {status.br:.2f}",
                    "line": f"{status.lc} / {status.lt} / {status.lr:.2f}",
                    "pass": status.passed,
                    "failures": status.failures,
                    "errors": status.errors,
                    "skipped": status.skipped,
                }
            ]
        )
        .header("Test code")
        .text(f"```java\n{before}\n```")
        .header("Fixed test code")
        .text(f"```java\n{executor.test_code}\n```")
        .header("Diff")
        .text(f"```java\n{code_diff}\n```")
        .build()
    )

    return status, state


@task(task_run_name="Unzip Dataset")
async def unzip_dataset_TASK(dataset_name: str, target_path: str):
    dataset_path = f"{CONFIG.dataset_folder}/{dataset_name}.zip"
    with zipfile.ZipFile(dataset_path, 'r') as zip_ref:
        zip_ref.extractall(target_path)

    # pre_compile_path = f"{CONFIG.dataset_folder}/{dataset_name}_pre.zip"
    # with zipfile.ZipFile(pre_compile_path, 'r') as zip_ref:
    #     zip_ref.extractall(target_path)
