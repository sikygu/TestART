"""
目的在于记录每次实验的结果

"""
import os.path
import time
from typing import TypeVar, Callable, Any, cast, List

from pydantic import BaseModel
from tinydb import TinyDB, Query, Storage
from app.classes import BatchAttemptStatus, AttemptStatus, IterationStatus
from functools import wraps
import orjson as json
import zlib

from app.constants import CONFIG, ExceptionCode, CoverageMode

T = TypeVar('T')


def singleton(cls: Callable[..., T]) -> Callable[..., T]:
    instances = {}

    @wraps(cls)
    def wrapper(*args: Any, **kwargs: Any) -> T:
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return cast(T, instances[cls])

    return wrapper


class CompressedJsonStorage(Storage):
    def __init__(self, filename):  # (1)
        self.filename = filename

    def read(self):
        if not os.path.exists(self.filename):
            return {}
        with open(self.filename, "rb") as handle:
            _t = time.time()
            content = handle.read()
            print("read time:", time.time() - _t)
            _t = time.time()
            data = zlib.decompress(content)
            print("decompress time:", time.time() - _t)
            _t = time.time()
            obj = json.loads(data)
            print("loads time:", time.time() - _t)
            return obj

    def write(self, data):
        with open(self.filename, 'wb') as handle:
            # handle.write(zlib.compress(json.dumps(data)))
            _t = time.time()
            obj = json.dumps(data)
            print("dumps time:", time.time() - _t)
            _t = time.time()
            compressed_data = zlib.compress(obj)
            print("compress time:", time.time() - _t)
            _t = time.time()
            handle.write(compressed_data)
            print("write time:", time.time() - _t)

    def close(self):
        pass


def get_db_key() -> str:
    """
    判断是否需要更新, 如果需要更新, 返回True, 否则返回False
    :param key: 上一次的key
    :return:
    """
    import os
    # not exists
    if not os.path.exists(CONFIG.db_path):
        db = TinyDB(CONFIG.db_path, storage=CompressedJsonStorage)
        db.truncate()
        print("init database")
    stat = os.stat(CONFIG.db_path)
    key = f"{stat.st_size}{stat.st_mtime}"
    return key


@singleton
class Database:
    def __init__(self):
        self.__db = TinyDB(CONFIG.db_path, storage=CompressedJsonStorage)

    def insert(self, data: BatchAttemptStatus):
        return self.__db.insert(data.model_dump())

    def get_by_id(self, doc_id) -> BatchAttemptStatus:
        d = self.__db.get(doc_id=doc_id)
        x = dict(d)
        x["doc_id"] = d.doc_id
        return BatchAttemptStatus(**x)

    def get_last(self) -> BatchAttemptStatus:
        last = self.__db.all()[-1]
        return BatchAttemptStatus(**last, doc_id=last.doc_id)

    def get_all(self) -> list[BatchAttemptStatus]:
        li = []
        for x in self.__db.all():
            d = dict(x)
            d["doc_id"] = x.doc_id
            li.append(d)
        _t = time.time()
        data =  [BatchAttemptStatus(**x) for x in li]
        print("assembling time:", time.time() - _t)
        return data


    def delete_last(self):
        _all = self.__db.all()
        last_doc_id = _all[-1].doc_id
        self.__db.remove(doc_ids=[last_doc_id])

    def clear(self):
        self.__db.truncate()

    def delete(self, doc_ids: List[int]):
        """
        删除指定的doc_id
        :param doc_ids:
        :return:
        """
        self.__db.remove(doc_ids=doc_ids)

    def update(self, doc_id: int, attempts: List[AttemptStatus]):
        """
        更新指定的doc_id
        :param doc_id:
        :param data:
        :return:
        """
        # 获取原始数据
        bas: BatchAttemptStatus = self.get_by_id(doc_id)
        attempts_map = {x.idx: x for x in attempts}

        # 更新数据
        for (i, attempt) in enumerate(bas.attempts):
            if attempt.idx in attempts_map:
                bas.attempts[i] = attempts_map[attempt.idx]

        # 保存数据
        self.insert(bas)

    # 合并数据
    def merge(self, doc_ids: List[int]):
        """
        合并指定的doc_id
        :param doc_ids:
        :return:
        """
        # 获取原始数据
        bas_list: List[BatchAttemptStatus] = [x for x in self.get_all() if x.doc_id in doc_ids]
        print("merging the data")
        # 合并数据
        first_batch = bas_list[0]
        new_batch = first_batch
        total_time = 0
        for bas in bas_list[1:]:
            new_batch.attempts.extend(bas.attempts)
            new_batch.attempts.sort(key=lambda x: x.idx)
            total_time += bas.duration

        new_batch.flow_run_request.dataset_start_index = first_batch.flow_run_request.dataset_start_index
        new_batch.flow_run_request.dataset_size = len(new_batch.attempts)

        first_batch.end_time_ms += total_time

        print("writing the new data")
        # 保存新数据
        self.insert(first_batch)
        print("cleaning the old data")
        # 删除旧数据
        self.delete(doc_ids)

    def get_ids_by_type(self, doc_id, _type: IterationStatus.Type | List[IterationStatus.Type]):
        if isinstance(_type, list):
            return [x.idx for x in self.get_by_id(doc_id).attempts if x.type in _type]
        return [x.idx for x in self.get_by_id(doc_id).attempts if x.type == _type]

    def get_pass_by_value(self, doc_id, value: float, mode: CoverageMode):
        attempts = self.get_by_id(doc_id).attempts
        # pass
        attempts = [x for x in attempts if x.type == IterationStatus.Type.PASS]
        for a in attempts:
            a.mode = mode
            a.iteration_status.test_status.mode = mode
        attempts = [x for x in attempts if x.iteration_status.test_status.value <= value]
        return [x.idx for x in attempts]

    def get_pass_by_iter(self, doc_id, iter_num: int):
        attempts = self.get_by_id(doc_id).attempts
        # pass
        attempts = [x for x in attempts if x.type == IterationStatus.Type.PASS]
        return [x.idx for x in attempts if len(x.sub_iteration_status) >= iter_num]

    def get_ids_by_error(self, doc_id, error: ExceptionCode):
        return [x.idx for x in self.get_by_id(doc_id).attempts if error in x.exceptions]


if __name__ == '__main__':
    st = time.time()

    db = Database()
    db.delete([131])

    print(time.time() - st)
