import pickle
import time

import tiktoken
from langchain_openai.chat_models import ChatOpenAI
from prefect import flow, Flow, State, get_run_logger
import asyncio
from prefect.artifacts import create_markdown_artifact, create_table_artifact
from prefect.client.schemas import FlowRun
from prefect import runtime, serve
from prefect.task_runners import SequentialTaskRunner

from app.database import Database
from app.flows.decorators import add_test_controller
from app.tasks.unit_test import CloverTestExecutor, unzip_dataset_TASK
from app.utils import *
from app.constants import *
from app.exceptions import ApiException
from app.allocator import ALLOCATOR
from app.tasks import *
from app.classes import CloverTestRequest, TestController, Markdown, Dataset, WorkerPool, FlowRunRequest, LLMRecord, \
    IterationStatus, AttemptStatus, BatchAttemptStatus, Template, TestStatus


async def finally_hook(flow: Flow, flow_run: FlowRun, state: State):
    await ALLOCATOR.release_project_path(str(flow_run.id))


@flow(name="UnitTest",
      retries=0,
      on_completion=[finally_hook],
      on_cancellation=[finally_hook],
      on_crashed=[finally_hook],
      on_failure=[finally_hook],
      version="0.0.1",
      flow_run_name="{request.flow_run_name}"
      )
@add_test_controller
async def unit_test(request: CloverTestRequest, test_controller: TestController):
    flow_id = runtime.flow_run.get_id()
    logger = get_run_logger()

    logger.info(f"Running Dataset Id: {request.dataset_id}")

    # 分配资源
    project_path = await ALLOCATOR.allocate_project_path(flow_id=flow_id)
    logger.info(f"资源分配: {project_path}")

    # 初始化LLM交互对象
    llm_config = request.llm_config
    llm = ChatOpenAI(openai_api_base=llm_config.api_base,
                     openai_api_key=llm_config.api_key,
                     model_name=llm_config.model,
                     streaming=False,
                     max_retries=1,
                     model_kwargs=dict(seed=llm_config.seed,
                                       frequency_penalty=llm_config.frequency_penalty),
                     request_timeout=llm_config.request_timeout,
                     verbose=True,
                     temperature=llm_config.temperature)

    # 初始化clover执行器
    executor: CloverTestExecutor = init_clover_executor_TASK(request, project_path)

    # 解压数据集
    await unzip_dataset_TASK(request.dataset_name, project_path)

    # 编译项目
    await compile_java_project_TASK(executor)

    # 分析代码 (暂时不用)
    code_analysis_module = """
    if "code_analysis" in request.init_prompt_template:
        logger.info("分析代码中...")
        prompt = [
            AIMessage(content=request.analysis_prompt_template),
            HumanMessage(content=request.source_code)
        ]
        llm_record: LLMRecord = await llm_call_TASK(llm=llm, prompt=prompt, cache_key=request.cache_key,
                                                    description="code-analysis")
        code_analysis: str = llm_record.response
        executor.code_analysis = code_analysis
        logger.info("LLM分析代码完成")
    """

    # 初始化prompt模版
    context = executor.__dict__.copy()
    if request.source_code_tokens >= 12000:
        context["source_code"] = request.compressed_source_code  # 使用压缩后的代码进行prompt
    system_prompt: str = Template(request.system_prompt_template).format(context)
    init_prompt: str = Template(request.init_prompt_template).format(context)

    # 初始化history
    test_controller.add_system_message(system_prompt)
    test_controller.add_user_message(init_prompt)


    loop = test_controller.loop
    try:
        for index, iteration_status in enumerate(loop):
            iteration_status: IterationStatus = iteration_status
            llm_record: LLMRecord = await llm_call_TASK(llm=llm,
                                                        prompt=test_controller.messages(),
                                                        cache_key=request.cache_key,
                                                        description=f"{loop.iteration_count}-{loop.retry_count}")
            llm_response = llm_record.response
            iteration_status.add_llm_record(llm_record)
            test_controller.add_ai_message(llm_record.response)
            # 提取代码块
            lang = "java"
            new_test_code = extract_codeblock(llm_response, lang=lang)

            if new_test_code is None:
                logger.error(f"extract_codeblock can't fount lang={lang}: {llm_response}")
                test_controller.add_user_message(request.no_code_reply)
                loop.retry(IterationStatus.Type.SYNTAX_ERROR)
                continue

            # 更新测试用例
            executor.try_insert_test_methods(new_test_code)
            executor.save_test_code()

            # 检查语法错误
            try:
                assert executor.test_code is not None
                syntax_java_code(executor.test_code)
            except ApiException as e:
                logger.exception(e)
                test_controller.add_user_message(request.syntax_error_reply)
                loop.retry(IterationStatus.Type.SYNTAX_ERROR)
                continue

            executor.save_test_code()

            # 测试编译是否通过
            # fix CE up to 3 times
            for i in range(3):
                if not request.fix_compile_error:
                    break
                try:
                    await executor.test_compile()
                except ApiException as e:
                    logger.warning(f"fix compile error {i + 1}/3...")
                    # [import class1, import class2, ...]
                    unimport_classes: list = get_class_imports(executor.project_absolute_path, e.error_msg)
                    if unimport_classes:
                        executor.add_imports(unimport_classes)
                        executor.save_test_code()
                        continue
                    else:
                        break  # 不包含 class 类型的 can't find symbol 错误
                break
            # 执行测试用例
            logger.info("executing the test code...")
            try:
                status, state = await run_test_TASK(executor, description=f"iter-{loop.iteration_count}")
                status: TestStatus = status
                status.type = TestStatus.Type.SUCCESS
                status.retry = loop.retry_count
                iteration_status.add_test_status(status)

            # compile error
            except ApiException as e:
                logger.error(e.error_msg)
                if e.error_code == ExceptionCode.COMPILE_ERROR:
                    error_message = e.error_msg

                    test_controller.add_user_message(
                        generate_compile_error_feedback(executor.test_filepath, e.error_msg)
                    )
                    _status: TestStatus = TestStatus(mode=request.mode)
                    _status.type = TestStatus.Type.ERROR
                    _status.retry = loop.retry_count
                    _status.test_code = executor.test_code
                    iteration_status.add_test_status(_status, invalid=True)
                    executor.test_code = None  # 清空测试用例，重新来过
                    loop.retry(IterationStatus.Type.COMPILE_ERROR)
                    continue
                else:
                    raise e

            # 修复测试用例
            fixed_times = 0
            while request.auto_fix and (status.errors + status.failures > 0) and request.max_fix - fixed_times > 0:
                if status.test_code == status.fixed_test_code:  # fix doesn't work
                    break
                fixed_times += 1
                logger.warning(
                    f"{status.failures} failures or {status.errors} errors detected, try to fixing... ({fixed_times}/{request.max_fix})!")
                # execute test code
                try:
                    status, state, = await run_test_TASK(executor, status.fixed_test_code,
                                                         description=f"fix-{fixed_times}")
                    status: TestStatus = status
                    status.type = TestStatus.Type.FIX_SUCCESS
                    status.retry = loop.retry_count
                    iteration_status.add_test_status(status)

                except Exception as e:
                    logger.exception(e)
                    iteration_status.exception = ExceptionCode.FIX_ERROR
                    _status: TestStatus = TestStatus(mode=request.mode)
                    _status.type = TestStatus.Type.FIX_ERROR
                    _status.retry = loop.retry_count
                    _status.test_code = status.fixed_test_code
                    executor.test_code = status.test_code  # 回退
                    iteration_status.add_test_status(_status, invalid=True)
                    break

            # 结果包含错误
            if status.failures + status.errors > 0:
                logger.warning(f"failures or errors detected, try to fix in next iteration!")
                loop.retry(IterationStatus.Type.RUNTIME_ERROR)
            else:
                # 结果不包含错误, 压缩token
                test_controller.compress_history()

            # 替换历史消息
            test_controller.replace_last_message(f"```java\n{executor.test_code}\n```")

            # 生成feedback
            if loop.has_next_iter():
                feedback = get_feedback(request, status, state)
                test_controller.add_user_message(feedback)

        # end for

        # 后置检查操作
        ecf = [
            len(loop.iterations) == 0,
            loop.iterations[-1].type is None
        ]
        for i, e in enumerate(ecf):
            if e:
                logger.error(f"Judge Unknown Error: {i}")
                raise ApiException(ExceptionCode.UNKNOWN_ERROR, "Judge Unknown Error")

    except ApiException as e:
        raise e
    finally:
        # expose failure and error manually
        DO_NOT_USE = """
            if status.failures + status.errors > 0:
            logger.warning("removing invalid test cases...")
            test_code = remove_invalid_testcase(
                clover_test_js_path=executor.clover_test_js_path,
                test_code=executor.test_code
            )
            logger.warning("re-run the test code...")
            status, state = await run_test_TASK(executor, test_code, description=f"final-fix")
            test_controller.set_status(status)
            test_controller.try_update_code(executor.test_code)
        """


@flow(name="UnitTest-Dataset", persist_result=True)
async def unit_test_dataset(request: FlowRunRequest = FlowRunRequest()):
    logger = get_run_logger()

    with open(f"{CONFIG.dataset_folder}/{request.dataset_name}.pkl", "rb") as f:
        raw_dataset = pickle.load(f)
        dataset = Dataset(**raw_dataset)

    # 生成subflow
    flow_list = []
    skip_num = request.dataset_start_index
    index = -1
    for class_info in dataset:
        for method_info in class_info:
            index += 1
            if skip_num > 0:
                skip_num -= 1
                continue
            # if index not in li:  # debug only
            #     continue
            clover_request = CloverTestRequest(**request.model_dump())

            class_name = class_info.class_name
            method_name = method_info.signature

            clover_request.source_class_name = class_name
            clover_request.source_code = class_info.content
            clover_request.compressed_source_code = method_info.compressed_content
            clover_request.source_code_tokens = class_info.tokens
            clover_request.flow_run_name = f"{class_name}#{method_name}"
            clover_request.source_function_name = method_name
            clover_request.package_reference = class_info.package_reference
            clover_request.dataset_name = request.dataset_name
            clover_request.dataset_id = index
            clover_request.source_function_start = method_info.start
            clover_request.source_function_end = method_info.end

            template_folder = CONFIG.bc_template_folder if request.mode == CoverageMode.BRANCH_COVERAGE else CONFIG.lc_template_folder
            clover_request.system_prompt_template = open(f"{template_folder}/system_prompt.txt").read()
            clover_request.init_prompt_template = open(f"{template_folder}/init_prompt.txt").read()
            clover_request.analysis_prompt_template = open(f"{template_folder}/analysis_prompt.txt").read()
            clover_request.success_prompt_template = open(f"{template_folder}/success_prompt.txt").read()
            clover_request.failure_prompt_template = open(f"{template_folder}/failure_prompt.txt").read()
            clover_request.error_prompt_template = open(f"{template_folder}/error_prompt.txt").read()
            flow_list.append(unit_test(clover_request))
            if len(flow_list) >= request.dataset_size:
                break
        if len(flow_list) >= request.dataset_size:
            break
    logger.info(f"flow count: {len(flow_list)}")
    start_time_ms = int(time.time() * 1000)
    flow_worker_pool = WorkerPool()
    result_list: List[AttemptStatus] = await flow_worker_pool.run(flow_list)

    end_time_ms = int(time.time() * 1000)
    request.dataset_size = len(result_list)
    batch_attempt_status = BatchAttemptStatus(
        attempts=result_list,
        flow_run_request=request,
        start_time_ms=start_time_ms,
        end_time_ms=end_time_ms,
        dataset=f"{request.dataset_name}",
        mode=request.mode
    )

    db = Database()
    db.insert(batch_attempt_status)
    # db.update(doc_id=130, attempts=result_list)  # debug only
    return batch_attempt_status


if __name__ == '__main__':
    unit_test_dataset.serve("单元测试生成任务")

