import logging
from typing import List
from prefect import task, get_run_logger
from app.constants import CONFIG

from threading import Lock, Semaphore

import asyncio
from typing import List


class ResourceAllocator:

    def __init__(self):
        self.mvn_path_list: List[str] = CONFIG.maven_project
        self.lock = Lock()
        self.semaphore = Semaphore(len(self.mvn_path_list))
        self.map = {}

    def allocate_project_path(self, flow_id: str):
        get_run_logger().info(f"{flow_id} waiting for resource allocation... {self.semaphore}")
        self.semaphore.acquire()
        with self.lock:
            path = self.mvn_path_list.pop(0)
            self.map[flow_id] = path
            get_run_logger().info(f"resource allocated : {path}, {len(self.mvn_path_list)} left")
            return path

    def release_project_path(self, flow_id: str):
        with self.lock:
            if flow_id not in self.map:
                logging.warning(f"flow_id {flow_id} not in map")
                return
            path = self.map.pop(flow_id)
            self.mvn_path_list.append(path)
        self.semaphore.release()
        logging.info(f"resource released : {path}, {len(self.mvn_path_list)} left")


class AsyncResourceAllocator:

    def __init__(self):
        self.mvn_path_list: List[str] = CONFIG.maven_project
        self.lock = asyncio.Lock()
        self.semaphore = asyncio.Semaphore(len(self.mvn_path_list))
        self.map = {}

    async def allocate_project_path(self, flow_id: str):
        get_run_logger().info(f"{flow_id} waiting for resource allocation... {self.semaphore}")
        await self.semaphore.acquire()
        async with self.lock:
            path = self.mvn_path_list.pop(0)
            self.map[flow_id] = path
            get_run_logger().info(f"resource allocated : {path}, {len(self.mvn_path_list)} left")
            return path

    async def release_project_path(self, flow_id: str):
        async with self.lock:
            if flow_id not in self.map:
                logging.warning(f"flow_id {flow_id} not in map")
                return
            path = self.map.pop(flow_id)
            self.mvn_path_list.append(path)
        self.semaphore.release()
        logging.info(f"resource released : {path}, {len(self.mvn_path_list)} left")


ALLOCATOR = AsyncResourceAllocator()
