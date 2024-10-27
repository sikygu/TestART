"""
a simple fastapi server to serve the ui
"""
import os
import sys
import json
import time
import uuid
import zipfile
from datetime import datetime
from typing import List, TypeVar

import httpx
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from collections import Counter
import difflib

from starlette.requests import Request

from app.constants import CoverageMode

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from fastapi import FastAPI, HTTPException
from app.database import Database, BatchAttemptStatus, get_db_key
from app.classes import AttemptStatus, IterationStatus, TestStatus
from app.constants import CONFIG
from app.utils import *

# 创建一个 FastAPI 应用程序实例
app = FastAPI()
db = Database()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许访问的源
    allow_credentials=True,
    allow_methods=["*"],  # 允许的 HTTP 方法
    allow_headers=["*"],  # 允许的请求头
)

Status = TypeVar("Status", BatchAttemptStatus, AttemptStatus, IterationStatus, TestStatus)


def format_history(history):
    return "\n".join([
        f"**{x['type']}**:\n {x['content']}\n" for x in history
    ])


def toVO(data, context: dict, lazy=True):
    if isinstance(data, list):
        return [toVO(x, context, lazy) for x in data]

    if not isinstance(data, BaseModel):
        return data

    if lazy:
        if not isinstance(data, AttemptStatus) and not isinstance(data, BatchAttemptStatus):
            return None

    # context
    if isinstance(data, BatchAttemptStatus):
        context['max_retry'] = data.flow_run_request.max_retry

    dict_data: dict = data.model_dump()
    for k, v in data:
        dict_data[k] = toVO(v, context, lazy)

    if isinstance(data, BatchAttemptStatus):
        attempt_type_counter = Counter([x.type for x in data.attempts])
        attempt_type_list = {
            "pass": attempt_type_counter[IterationStatus.Type.PASS],
            "syntax_error": attempt_type_counter[IterationStatus.Type.SYNTAX_ERROR],
            "compile_error": attempt_type_counter[IterationStatus.Type.COMPILE_ERROR],
            "runtime_error": attempt_type_counter[IterationStatus.Type.RUNTIME_ERROR],
            "fail": attempt_type_counter[IterationStatus.Type.FAIL],
        }
        dict_data["duration"] = data.duration
        dict_data["num"] = len(data.attempts)
        dict_data["flow_run_request"] = data.flow_run_request
        start = data.flow_run_request.dataset_start_index
        end = start + data.flow_run_request.dataset_size - 1
        dict_data["no"] = f"{start}-{end}" if start != end else start
        dict_data["status"] = attempt_type_list
        dict_data["start_time"] = datetime.fromtimestamp(data.start_time_ms // 1000).strftime("%Y-%m-%d %H:%M:%S")
        dict_data["end_time"] = datetime.fromtimestamp(data.end_time_ms // 1000).strftime("%Y-%m-%d %H:%M:%S")
        dict_data["duration"] = "{:.2f}s".format(data.duration / 1000)
        dict_data["mode"] = {
            CoverageMode.BRANCH_COVERAGE: "branch",
            CoverageMode.LINE_COVERAGE: "line",
        }[data.mode]

    if isinstance(data, AttemptStatus):
        dict_data["start_time"] = datetime.fromtimestamp((data.start_time_ms or 0) // 1000).strftime("%H:%M:%S")
        dict_data["end_time"] = datetime.fromtimestamp((data.end_time_ms or 0) // 1000).strftime("%H:%M:%S")
        dict_data["duration"] = "{:.2f}s".format(data.duration / 1000)
        dict_data["num"] = len(data.sub_iteration_status or [])
        dict_data["type"] = data.type
        dict_data["exceptions"] = data.exceptions
        covered, total = data.cover_value
        dict_data["value"] = f"{data.value:.2f}"
        dict_data["cover_value"] = f"{covered} / {total}"
        dict_data["history"] = "" if lazy else format_history(data.history)
        dict_data["iteration_status"] = []
        if lazy:
            dict_data["sub_iteration_status"] = []

    if isinstance(data, IterationStatus):
        if lazy:
            return dict_data
        dict_data["start_time"] = datetime.fromtimestamp(data.start_time_ms // 1000).strftime("%H:%M:%S")
        dict_data["end_time"] = datetime.fromtimestamp((data.end_time_ms or 0) // 1000).strftime("%H:%M:%S")
        dict_data["duration"] = "{:.2f}s".format(data.duration / 1000)
        covered, total = data.cover_value
        dict_data["value"] = f"{data.value:.2f}"
        dict_data["cover_value"] = f"{covered} / {total}"
        dict_data["retry"] = f"{data.retry}/{context['max_retry']}"
        dict_data["llm_records"] = [
            {
                'title': f"{x.description} ({x.in_tokens}, {x.out_tokens})",
                'content': f"## prompt \n{format_history(x.prompt)}\n ## response \n{x.response}"
            }
            for x in data.llm_records or []
        ]

    if isinstance(data, TestStatus):
        if lazy:
            return dict_data

        dict_data["branch"] = f"{data.bc} / {data.bt} / {data.br:.2f}"
        dict_data["line"] = f"{data.lc} / {data.lt} / {data.lr:.2f}"
        dict_data[
            "code"] = f"**执行代码：**\n```java\n{data.test_code}\n```\n\n**修复代码**: \n```java\n{data.fixed_test_code}\n```\n"

        code_diff = None
        if data.test_code and data.fixed_test_code:
            code_diff = '\n'.join(
                list(difflib.Differ().compare(data.test_code.splitlines(), data.fixed_test_code.splitlines())))
        dict_data["code_diff"] = f"```java\n{code_diff}\n```"
        dict_data['type'] = {
            TestStatus.Type.SUCCESS: "成功",
            TestStatus.Type.ERROR: "失败",
            TestStatus.Type.FIX_SUCCESS: "修复成功",
            TestStatus.Type.FIX_ERROR: "修复失败",
        }.get(data.type, "")
    return dict_data


CACHED_DATA = ("", None, {})


@app.get("/")
async def get_all_data() -> list[dict]:
    global CACHED_DATA
    context = {}
    key, origin_data, data = CACHED_DATA
    if key == get_db_key():
        print("cached")
    else:
        _t = time.time()
        origin_data = db.get_all()
        print("get_all", time.time() - _t)
        _t = time.time()
        data = toVO(origin_data, context, lazy=True)
        print("toVO", time.time() - _t)
        CACHED_DATA = (get_db_key(), origin_data, data)
    return data


CACHED_ITERATION_STATUS = {}


@app.get("/iteration_status")
async def get_iteration_status(doc_id: int, aid: int) -> list[dict]:
    global CACHED_ITERATION_STATUS, CACHED_DATA
    _key, origin_data, _ = CACHED_DATA
    if get_db_key() != _key:
        CACHED_ITERATION_STATUS = {}
    key = f"{doc_id}-{aid}"
    if key in CACHED_ITERATION_STATUS:
        data = CACHED_ITERATION_STATUS[key]
    else:
        bas = [x for x in origin_data if x.doc_id == doc_id][0]
        attempts = bas.attempts
        attempt = [x for x in attempts if x.idx == aid][0]
        data = attempt.sub_iteration_status

        data = toVO(data, {
            "max_retry": bas.flow_run_request.max_retry
        }, lazy=False)  # cpu heavy

        CACHED_ITERATION_STATUS[key] = data
    return data


from fastapi import UploadFile
import shutil


@app.post("/upload")
async def upload_file(file: UploadFile):
    return await inner_upload_file(file)


async def inner_upload_file(file: UploadFile):
    if file.size == 0:
        return {"msg": "empty file", "code": "400"}
    if file.size / 1024 / 1024 >= 50:
        return {"msg": "not support file size > 50M", "code": "400"}
    origin_name = file.filename.split('.')[0]
    fp = f"{CONFIG.upload_folder}/{origin_name}_upload_{time.time_ns()}.zip"
    if os.path.exists(f"{CONFIG.upload_folder}/{origin_name}.zip"):
        for i in range(2, 100000):
            if not os.path.exists(f"{CONFIG.upload_folder}/{origin_name}_{i}.zip"):
                origin_name = f"{origin_name}_{i}"
                break
    if file.filename.endswith(".zip"):
        with open(fp, 'wb') as buffer:
            shutil.copyfileobj(file.file, buffer)
    elif file.filename.endswith(".java"):
        with zipfile.ZipFile(fp, 'w', zipfile.ZIP_DEFLATED) as new_zip_ref:
            new_zip_ref.writestr(f"/src/main/java/{file.filename}", file.file.read())
    else:
        return {"msg": "not .zip or .java file", "code": "400"}
    try:
        process_zip_dataset(fp, origin_name)

    except Exception as e:
        from traceback import format_exc
        print(format_exc())
        os.remove(fp)
        return {"msg": f"error: {e}", "code": "400"}

    os.remove(fp)  # remove upload file
    return {"msg": origin_name, "code": "200"}


# get dataset list
@app.get("/dataset")
async def get_dataset_list():
    dataset_list = []
    for file in os.listdir(CONFIG.dataset_folder):
        if file.endswith(".json"):
            # 判断是否有同名的pkl和zip文件
            file_name = file.split("_info.")[0]
            pkl_file = f"{CONFIG.dataset_folder}/{file_name}.pkl"
            zip_file = f"{CONFIG.dataset_folder}/{file_name}.zip"
            if os.path.exists(pkl_file) and os.path.exists(zip_file):
                info = [
                    dict(idx=i, **x)
                    for i,x in enumerate(json.loads(open(f"{CONFIG.dataset_folder}/{file}", "r").read()))
                ]
                # 形成dataset信息
                dataset_info = {
                    "name": file_name,
                    "size": os.path.getsize(zip_file) + os.path.getsize(pkl_file),
                    "upload_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(os.path.getctime(zip_file))),
                    "focal_method": len(info),
                    "info": info
                }
                dataset_list.append(dataset_info)

    return dataset_list


# export PYTHONPATH=$PYTHONPATH:~/GPT-Java-Tester
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=25734)
