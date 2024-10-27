import asyncio
import time
from enum import Enum

from langchain_community.chat_message_histories import ChatMessageHistory
from typing import Tuple, Any, List, Generator, Iterator

from langchain_core.prompts import PromptTemplate, ChatPromptTemplate
from pydantic import BaseModel
from langchain.schema import BaseMessage, HumanMessage, SystemMessage, AIMessage
import re
import json
from prefect import get_run_logger
from tabulate import tabulate
import pandas as pd

from app.exceptions import ApiException
from app.constants import ExceptionCode, CoverageMode

from app.constants import CONFIG


class Dataset(BaseModel):
    class ClassInfo(BaseModel):
        class MethodInfo(BaseModel):
            signature: str
            start: int
            end: int
            content: str # method content for debug
            compressed_content: str # compressed class content for prompt
            name: str

        package_reference: str
        content: str
        tokens: int
        lines: int
        class_name: str
        methods: List[MethodInfo]  # method_signature -> method_info

        def __iter__(self) -> Iterator[MethodInfo]:
            return iter(self.methods)

    data: List[ClassInfo]

    def __iter__(self) -> Iterator[ClassInfo]:
        return iter(self.data)

    def get_item(self, class_name, method_name):
        class_info = self.data[class_name]
        method_info = class_info.methods[method_name]
        return class_info, method_info


class LLMConfig(BaseModel):
    model: str = "gpt-3.5-turbo"
    api_key: str = "sk-10pQoL6LjUKnKS4wb8ATZ2hIGZ28Gm6NEkBz0QPDQap3T2m6"
    api_base: str = "https://aigptx.top/v1"
    temperature: float = 0
    seed: int = 123456789
    frequency_penalty: float = 0
    request_timeout: float = 60


class FlowRunRequest(BaseModel):
    """expose to prefect server"""
    mode: CoverageMode = CoverageMode.BRANCH_COVERAGE
    llm_config: LLMConfig = LLMConfig()
    no_code_reply: str = 'Java code cell not detected, please provide your test code ' \
                         'then output in a java code cell'
    syntax_error_reply: str = 'Syntax error, please regenerate your test code!'
    max_retry: int = 1
    max_iteration: int = 3
    max_fix: int = 3
    auto_fix: bool = True
    fix_compile_error: bool = True
    cache_key: str = str(int(time.time()))
    dataset_name: str = "lang_1_fixed"
    dataset_size: int = 1
    dataset_start_index: int = 0


class CloverTestRequest(BaseModel):
    """actual request for execution"""
    mode: CoverageMode
    llm_config: LLMConfig
    no_code_reply: str
    syntax_error_reply: str
    max_retry: int = 1
    max_iteration: int = 3
    max_fix: int = 3
    source_code: str | None = None
    compressed_source_code: str | None = None
    source_code_tokens: int | None = None
    test_code: str | None = None
    additional_context: str | None = None
    dataset_name: str | None = None
    dataset_id: int = -1
    package_reference: str | None = None
    source_class_name: str | None = None
    test_class_name: str | None = None
    source_function_name: str | None = None
    source_function_start: int | None = None
    source_function_end: int | None = None
    system_prompt_template: str | None = None
    init_prompt_template: str | None = None
    success_prompt_template: str | None = None
    error_prompt_template: str | None = None
    failure_prompt_template: str | None = None
    analysis_prompt_template: str | None = None
    auto_fix: bool = True
    fix_compile_error: bool = True
    flow_run_name: str = "default_flow"
    cache_key: int = str(int(time.time()))


class Template:
    def __init__(self, content: str):
        self.content: str = content

    def format(self, values: dict) -> str:
        try:
            # locals() contains 'self' but conflict with func call (self, **kwargs), so delete it
            if 'self' in values:
                del values['self']
            chat_template: ChatPromptTemplate = ChatPromptTemplate.from_template(self.content)
            prompt: str = chat_template.format_prompt(**values).to_messages()[0].content
        except Exception as e:
            get_run_logger().exception(e)
            raise ApiException(ExceptionCode.TEMPLATE_ERROR,
                               f"Template format error: {e}, please check spelling and if the system supports this key")
        return prompt


class LLMRecord(BaseModel):
    in_tokens: int
    out_tokens: int
    prompt: List[dict]
    response: str
    start_time_ms: int
    end_time_ms: int
    description: str | None = None


class TestStatus(BaseModel):
    class Type(Enum):
        SUCCESS = "SUCCESS"
        FIX_SUCCESS = "FIX_SUCCESS"
        ERROR = "ERROR"
        FIX_ERROR = "FIX_ERROR"

        def __str__(self):
            return self.value

    test_code: str | None = None
    fixed_test_code: str | None = None
    bc: int = -1
    bt: int = -1
    br: float = -1
    lc: int = -1
    lt: int = -1
    lr: float = -1
    tests: int = -1
    failures: int = -1
    errors: int = -1
    skipped: int = -1
    passed: int = -1
    retry: int = 0
    type: Type | None = None
    mode: CoverageMode

    @property
    def value(self):
        """返回覆盖率值"""
        if self.mode == CoverageMode.BRANCH_COVERAGE:
            return self.br if self.br >= 0 else -1
        elif self.mode == CoverageMode.LINE_COVERAGE:
            return self.lr if self.lr >= 0 else -1

    @property
    def cover_value(self):
        """返回覆盖率值"""
        if self.mode == CoverageMode.BRANCH_COVERAGE:
            return self.bc, self.bt
        elif self.mode == CoverageMode.LINE_COVERAGE:
            return self.lc, self.lt

    @property
    def all_pass(self):
        assert self.tests and self.tests > 0
        return self.passed == self.tests


class IterationStatus(BaseModel):
    class Type(Enum):
        SYNTAX_ERROR = "SYNTAX_ERROR"
        COMPILE_ERROR = "COMPILE_ERROR"
        RUNTIME_ERROR = "RUNTIME_ERROR"
        PASS = "PASS"
        FAIL = "FAIL"

        def __str__(self):
            return self.value

    test_status: TestStatus | None = None
    sub_test_status: List[TestStatus] | None = None
    llm_records: List[LLMRecord] | None = None
    index: int = -1
    start_time_ms: int | None = None
    end_time_ms: int | None = None
    retry: int | None = None
    type: Type | None = None
    exception: ExceptionCode | None = None

    def add_llm_record(self, record: LLMRecord):
        if not self.llm_records:
            self.llm_records = []
        self.llm_records.append(record)

    def add_test_status(self, status: TestStatus, invalid=False):
        # 添加到状态列表
        if not self.sub_test_status:
            self.sub_test_status = []
        self.sub_test_status.append(status)

        # 此次状态无错误
        if invalid:
            return
        if status.failures + status.errors == 0:
            # 如没有最佳状态
            if not self.test_status:
                self.index = len(self.sub_test_status) - 1
                self.test_status = status
            # 比较，并选择最佳状态
            elif status.value > self.test_status.value:
                self.index = len(self.sub_test_status) - 1
                self.test_status = status

        # status 仍可能为 None

    @property
    def value(self) -> float:
        return 0 if not self.test_status else self.test_status.value

    @property
    def cover_value(self):
        if not self.test_status:
            return -1, -1
        return self.test_status.cover_value

    @property
    def all_pass(self) -> bool:
        return False if not self.test_status else self.test_status.all_pass

    @property
    def duration(self):
        return (self.end_time_ms or 0) - (self.start_time_ms or 0)


class AttemptStatus(BaseModel):
    iteration_status: IterationStatus | None = None
    sub_iteration_status: List[IterationStatus] | None = None
    index: int = -1
    name: str | None = None
    link: str | None = None
    clazz: str | None = None
    method: str | None = None
    idx: int | None = None
    start_time_ms: int | None = None
    end_time_ms: int | None = None
    history: List[dict] | None = None
    mode: CoverageMode

    @property
    def test_code(self):
        if not self.iteration_status:
            return None
        iteration_status = self.iteration_status
        test_status = iteration_status.test_status
        return test_status.test_code

    @property
    def value(self):
        if not self.iteration_status:
            return -1
        return self.iteration_status.value

    @property
    def cover_value(self):
        if not self.iteration_status:
            return -1,-1
        return self.iteration_status.cover_value

    @property
    def type(self):
        if len(self.sub_iteration_status or []) == 0:
            return IterationStatus.Type.FAIL
        elif not self.iteration_status:
            return self.sub_iteration_status[-1].type
        return self.iteration_status.type

    @property
    def exceptions(self) -> List[ExceptionCode]:
        li = []
        for its in (self.sub_iteration_status or []):
            if its.exception:
                li.append(its.exception)
        return li

    def add_iteration_status(self, status: IterationStatus):
        # 添加到状态列表
        if not self.sub_iteration_status:
            self.sub_iteration_status = []
        self.sub_iteration_status.append(status)

        # 此次迭代产生了有效结果
        if status.test_status:
            # 当前没有最佳迭代
            if not self.iteration_status:
                self.index = len(self.sub_iteration_status) - 1
                self.iteration_status = status
            # 选择最佳迭代
            elif status.test_status.value > self.iteration_status.test_status.value:
                self.index = len(self.sub_iteration_status) - 1
                self.iteration_status = status

    @property
    def duration(self):
        return (self.end_time_ms or 0) - (self.start_time_ms or 0)


class BatchAttemptStatus(BaseModel):
    attempts: List[AttemptStatus]
    flow_run_request: FlowRunRequest
    start_time_ms: int
    end_time_ms: int
    dataset: str
    doc_id: int | None = None
    mode: CoverageMode

    @property
    def duration(self):
        return (self.end_time_ms or 0) - (self.start_time_ms or 0)


class Loop:
    def __init__(self, max_iteration=3, max_retry=1):
        self.max_iteration = max_iteration
        self.max_retry = max_retry
        self.iteration_count = 0
        self.retry_count = 0
        self.terminate_flag = False
        self.retry_flag = False
        self.retry_type = None
        self.iterations: List[IterationStatus] = []

    def __next__(self) -> IterationStatus:
        logger = get_run_logger()

        # 重试逻辑
        if self.retry_flag and not self.terminate_flag:
            self.retry_count += 1
            if self.retry_count <= self.max_retry:
                logger.warning(f"Retry: {self.retry_count} / {self.max_retry}")
                self.retry_flag = False # 重试处理完毕
                return self.iterations[-1]
            else:
                self.terminate_flag = True  # 结束迭代
                assert self.retry_type is not None
                self.iterations[-1].type = self.retry_type
                logger.warning(f"Exceed max_retry {self.max_retry}")

        # 上次迭代内容更新
        if len(self.iterations) > 0:
            its = self.iterations[-1]
            its.end_time_ms = int(time.time() * 1000)
            # Exceed max_retry, 记录结果时需要减去1次retry_count
            its.retry = self.retry_count - 1 if self.retry_flag else self.retry_count
            if its.type is None:
                assert self.retry_flag is not None
                its.type = IterationStatus.Type.PASS if its.all_pass else IterationStatus.Type.RUNTIME_ERROR

        # 重置重试次数
        self.retry_flag = False
        self.retry_count = 0
        self.retry_type = None

        # 重试达到最大值，或者没有重试，则进行下一次迭代
        if self.has_next_iter():
            iteration_status: IterationStatus = IterationStatus(index=self.iteration_count,
                                                                start_time_ms=int(time.time() * 1000))
            self.iterations.append(iteration_status)
            self.iteration_count += 1
            logger.info(
                f"Iteration: {self.iteration_count} / {self.max_iteration}, Retry: {self.retry_count} / {self.max_retry}")
            return iteration_status
        else:
            logger.info("Terminate Loop")
            raise StopIteration

    def has_next_iter(self):
        if len(self.iterations) > 0 and self.iterations[-1].value == 1:
            get_run_logger().info("Terminate loop because of 100% coverage")
            return False

        self.iteration_count += 1
        valid = self.iteration_count <= self.max_iteration and not self.terminate_flag
        self.iteration_count -= 1

        return valid

    def retry(self, retry_type: IterationStatus.Type):
        self.retry_flag = True
        self.retry_type = retry_type

    def terminate(self):
        self.terminate_flag = True

    def __iter__(self):
        return self


class TestController:
    def __init__(self, loop: Loop, mode: CoverageMode, flow_id: str):
        self.__history = ChatMessageHistory()
        self.__full_history: List[BaseMessage] = []
        self.loop: Loop = loop
        self.mode = mode
        self.flow_id = flow_id

    def add_user_message(self, content: str):
        self.__history.add_user_message(content)
        self.__full_history.append(self.__history.messages[-1])

    def add_ai_message(self, content: str):
        self.__history.add_ai_message(content)
        self.__full_history.append(self.__history.messages[-1])

    def add_system_message(self, content: str):
        self.__history.add_message(SystemMessage(content=content))
        self.__full_history.append(self.__history.messages[-1])

    def messages(self):
        return self.__history.messages

    def full_messages(self):
        return self.__full_history

    def replace_last_message(self, content: str):
        self.__history.messages[-1] = AIMessage(content=content)

    def compress_history(self):
        get_run_logger().info(f"compressing the chat history...")
        prefix, test_code = self.__history.messages[:2], self.__history.messages[-1]
        self.__history.messages = prefix + [test_code]


class CloverTestHandler:
    def __init__(self, clover_test_js_path, test_code):
        self.clover_test_js_path = clover_test_js_path
        self.test_code = test_code

    def parse_test_js(self):
        text = open(self.clover_test_js_path).read()

        # Extract pageData
        regex_page = r"clover\.pageData\s=\s({.*})"
        matches = re.finditer(regex_page, text, re.MULTILINE)
        match = next(matches)
        self.pageData = json.loads(match.group(1))

        # Extract testTargets
        regex_targets = r"clover\.testTargets\s=\s({.*})"
        matches = re.finditer(regex_targets, text, re.MULTILINE)
        match = next(matches)
        self.testTargets = json.loads(match.group(1))

    def remove_failed_tests(self) -> str:
        # Iterate through testTargets
        for test, data in self.testTargets.items():
            # If test case passed, continue
            if data['pass']:
                continue

            # Test case failed, get start line
            start_line = data['methods'][0]['sl']

            # Get end line from pageData
            end_line = self._get_end_line(start_line)

            # Remove this test case from test file
            self._remove_test_case(start_line, end_line)

        return self.test_code

    def _get_end_line(self, start_line):
        for class_data in self.pageData['classes']:
            for method_data in class_data['methods']:
                if method_data['sl'] == start_line:
                    return method_data['el']
        return None

    def _remove_test_case(self, start_line, end_line):
        if not end_line:
            get_run_logger().debug(f"Cannot find end line for start line {start_line}. Skipping.")

        lines = self.test_code.split("\n")
        new_lines = []
        for idx, line in enumerate(lines):
            # if the line is within the range of the test case, skip it
            if start_line <= idx + 1 <= end_line:
                continue
            new_lines.append(line)

        self.test_code = "\n".join(new_lines)


class Markdown:
    def __init__(self):
        self.__content_list: List[str] = []

    def table(self, data: List[dict]):
        t = tabulate(data, headers="keys", tablefmt="pipe", stralign="center")
        self.__content_list.append(t)
        self.__content_list.append("\n\n")
        return self

    def header(self, content: str, level: int = 1):
        self.__content_list.append(f"\n{'#' * level} {content}\n")
        return self

    def code(self, content: str, lang: str = "java"):
        code_cell = f"```{lang}\n{content}\n```\n"
        self.__content_list.append(code_cell)
        return self

    def text(self, content: str):
        self.__content_list.append(f"{content}\n")
        return self

    def build(self):
        return "".join(self.__content_list)


class WorkerPool:
    def __init__(self, concurrency: int = len(CONFIG.maven_project)):
        self.concurrency = concurrency
        self.running = 0
        self.queue: list = []
        self.logger = get_run_logger()

    async def run(self, queue: list):
        self.queue = queue
        self.running = 0

        count = len(queue)
        running_queue = []
        result_list = []
        while len(result_list) != count:
            # # self.logger.debug(
            #     f"Queue length: {len(self.queue)}, Running: {self.running}, Concurrency: {self.concurrency}")
            # # self.logger.debug(f"Current queue: {self.queue}")
            # # self.logger.debug(f"Running queue: {running_queue}")
            # 任务队列未满，提交到任务队列
            if self.running < self.concurrency and len(self.queue) > 0:
                self.running += 1
                item = self.queue.pop(0)
                running_queue.append(asyncio.create_task(item))
                # # self.logger.debug(
                #     f"Task added to running queue. Running: {self.running}, Concurrency: {self.concurrency}")
            # 任务队列已满
            else:
                # 找到已完成的任务
                finished_flow = []
                unfinished_flow = []
                for _flow in running_queue:
                    if _flow.done():
                        finished_flow.append(_flow)
                    else:
                        unfinished_flow.append(_flow)

                result_list.extend([x.result() for x in finished_flow])
                running_queue = unfinished_flow
                self.running -= len(finished_flow)

                # self.logger.debug(f"Finished tasks: {len(finished_flow)}, Unfinished tasks: {len(unfinished_flow)}")
                # self.logger.debug(f"Result list: {result_list}")

                # 未找到已完成任务
                if len(finished_flow) == 0:
                    # self.logger.debug("No finished tasks found. Sleeping for 1 second.")
                    await asyncio.sleep(1)

        # self.logger.debug("All tasks have been processed.")
        return result_list
