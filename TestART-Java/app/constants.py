from enum import Enum
from typing import List
import os
from pydantic import BaseModel
import json

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(APP_ROOT)


class Config(BaseModel):
    maven_project: List[str] = [
        f"{PROJECT_ROOT}/project/TestJavaCode",
        f"{PROJECT_ROOT}/project/TestJavaCode2",
        f"{PROJECT_ROOT}/project/TestJavaCode3",
    ]
    bc_template_folder: str = f"{PROJECT_ROOT}/template/bc"
    lc_template_folder: str = f"{PROJECT_ROOT}/template/lc"
    streamlit_folder: str = f"{PROJECT_ROOT}/streamlit"
    dataset_folder: str = f"{PROJECT_ROOT}/dataset"
    db_path: str = f"{PROJECT_ROOT}/db.zlib"
    upload_folder: str = dataset_folder
    result_folder: str = f"{PROJECT_ROOT}/result"

    def __init__(self, **data):
        super().__init__(**data)


class MessageRole(Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"

    def __str__(self):
        return self.value


class ResponseType(Enum):
    NORMAL = "chat.completion"
    CHUNK = "chat.completion.chunk"

    def __str__(self):
        return self.value


class ExceptionCode(Enum):
    LLM_ERROR = "LLM_ERROR"
    TEST_ERROR = "TEST_ERROR"
    INIT_ERROR = "INIT_ERROR"
    RUN_ERROR = "RUN_ERROR"
    REPORT_ERROR = "REPORT_ERROR"
    FIX_ERROR = "FIX_ERROR"
    TEMPLATE_ERROR = "TEMPLATE_ERROR"
    COMPILE_ERROR = "COMPILE_ERROR"
    SYNTAX_ERROR = "SYNTAX_ERROR"
    RUNTIME_ERROR = "RUNTIME_ERROR"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"

    def __str__(self):
        return self.value


class CoverageMode(Enum):
    BRANCH_COVERAGE = "BRANCH_COVERAGE"
    LINE_COVERAGE = "LINE_COVERAGE"

    def __str__(self):
        return self.value


CONFIG = Config()
