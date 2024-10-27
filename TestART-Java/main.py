import argparse
import os
from io import BytesIO

from fastapi import UploadFile

from app.constants import CONFIG
from app.flows.main import unit_test_dataset
from app.classes import FlowRunRequest, CoverageMode
import asyncio

if __name__ == '__main__':
    # parser = argparse.ArgumentParser(description='Run unit tests on a dataset.')
    # parser.add_argument('--api_base', required=True, help='API base URL')
    # parser.add_argument('--api_key', required=True, help='API key')
    # parser.add_argument('--cache_key', default='1704609944', help='LLM response cache key')
    # parser.add_argument('--dataset_name', default=None, help='Name of the dataset')
    # parser.add_argument('--dataset_start_index', type=int, required=True, help='Start index of the dataset (include)')
    # parser.add_argument('--dataset_end_index', type=int, required=True, help='End index of the dataset (include)')
    # parser.add_argument('--temperature', type=float, default=0.5, help='Temperature for the model')
    # parser.add_argument('--model', default="gpt-3.5-turbo-0125", help='LLM name')
    # parser.add_argument('--max_iteration', type=int, default=4, help='Maximum number of iterations')
    # parser.add_argument('--max_retry', type=int, default=1, help='Maximum number of retries')
    # parser.add_argument('--max_fix', type=int, default=6, help='Maximum number of fixes')
    # parser.add_argument('--mode', default="branch", help='Coverage mode')
    # parser.add_argument('--auto_fix', type=bool, default=True, help='Whether to auto fix')
    # parser.add_argument('--request_timeout', type=int, default=60, help='LLM Request timeout')
    # parser.add_argument('--output', default=CONFIG.result_folder, help='Output file dir')
    # parser.add_argument('--input', default=None, help='Input filepath (.zip or .java)')

    # args = parser.parse_args()

    request = FlowRunRequest()
    request.llm_config.api_base =  "https://api.deepseek.com"
    request.llm_config.api_key = "X"
    request.cache_key = "123"
    request.dataset_name = "zidingyishujuji"
    request.dataset_start_index = 0
    request.dataset_size = 2
    request.llm_config.temperature = 0
    request.llm_config.model = "deepseek-coder"
    request.max_iteration = 1
    request.max_retry = 0
    request.max_fix = 1
    request.mode = CoverageMode.BRANCH_COVERAGE
    request.auto_fix = True
    request.llm_config.request_timeout = 60
    asyncio.run(unit_test_dataset(request=request))