import functools
import os

from prefect.artifacts import create_markdown_artifact

from app.exceptions import ApiException
from app.classes import *
from prefect import runtime


def add_test_controller(func):
    async def wrapper(request: CloverTestRequest):
        loop = Loop(max_iteration=request.max_iteration, max_retry=request.max_retry)
        tc = TestController(
            loop=loop,
            mode=request.mode,
            flow_id=runtime.flow_run.get_id(),
        )
        attempt_status = AttemptStatus(
            mode=request.mode,
            name=request.flow_run_name,
            link=f"/flow-runs/flow-run/{runtime.flow_run.get_id()}",
            clazz=request.source_class_name,
            method=request.source_function_name,
            idx=request.dataset_id,
            start_time_ms=int(time.time() * 1000),
        )
        try:
            await func(request, tc)
        except ApiException as e:
            get_run_logger().exception(e)
            loop.iterations[-1].exception = e.error_code

            if e.error_code == ExceptionCode.COMPILE_ERROR:
                loop.iterations[-1].type = IterationStatus.Type.COMPILE_ERROR
            elif e.error_code == ExceptionCode.SYNTAX_ERROR:
                loop.iterations[-1].type = IterationStatus.Type.SYNTAX_ERROR
            else:
                loop.iterations[-1].type = IterationStatus.Type.FAIL
        except Exception as e:
            get_run_logger().exception(e)
            loop.iterations[-1].exception = ExceptionCode.UNKNOWN_ERROR
            loop.iterations[-1].type = IterationStatus.Type.FAIL
        finally:
            attempt_status.history = [{'type': x.type, 'content': x.content} for x in tc.full_messages()]
            attempt_status.end_time_ms = int(time.time() * 1000)
            for its in loop.iterations:
                attempt_status.add_iteration_status(its)

            await create_markdown_artifact(
                Markdown()
                .header("Final Code:")
                .code(attempt_status.test_code)
                .header("Iterations")
                .table([
                    dict(
                        type=v.type,
                        exception=v.exception,
                        coverage=v.value,
                        is_best=v.index == i
                    )
                    for i,v in enumerate(attempt_status.sub_iteration_status)
                ])
                .build()
                )

            if attempt_status.type == IterationStatus.Type.PASS:
                final_code_dir = f"{CONFIG.result_folder}/{request.dataset_name}_{runtime.flow_run.get_parent_flow_run_id()}"
                method = attempt_status.method.split("(")[0]
                key = f"{attempt_status.clazz}_{attempt_status.idx}_{method}_Test"

                def replace_class_name(code: str, key):
                    pattern = "public class ([\w]+)"
                    class_name = re.search(pattern, code).group(1).strip()
                    code = code.replace(class_name, key)
                    return code


                code = replace_class_name(attempt_status.test_code, key)
                package_path = request.package_reference.replace(".", "/") if request.package_reference else ""
                OUTPUT_PATH = f"{final_code_dir}/{package_path}"
                os.makedirs(OUTPUT_PATH, exist_ok=True)
                with open(os.path.join(OUTPUT_PATH, f"{key}.java"), "w", encoding="utf8") as f:
                    f.write(code)
            return attempt_status

    return wrapper
