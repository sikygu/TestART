import time

from tinydb import TinyDB, Query
import logging
import argparse
# 创建解析器
parser = argparse.ArgumentParser(description='Process some integers.')
# 添加参数
parser.add_argument('-p', '--param', help='an input parameter')
parser.add_argument('--init', action='store_true', help='an initialization parameter')
# 解析参数
args = parser.parse_args()

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

fh = logging.FileHandler(f'{args.param}_{time.strftime("%H:%M:%S", time.localtime())}.log')
fh.setLevel(logging.DEBUG)

ch = logging.StreamHandler()
ch.setLevel(logging.INFO)

# 定义handler的输出格式
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
ch.setFormatter(formatter)

# 给logger添加handler
logger.addHandler(fh)
logger.addHandler(ch)




if not args.param:
    assert False, "need -p"

# 使用参数
db = TinyDB(f"{args.param}.json")
if args.init:
    logging.warning("init database")
    db.update({"state": False})

data = db.all()


length = len(data)
finished = [x for x in data if x['state']]
unfinished = [x for x in data if not x['state']]
logger.info(f"finished: {len(finished)}")
logger.info(f"unfinished: {len(unfinished)}")
logger.info(f"total: {length}")

import threading

def handle_output(process):
    while True:
        time.sleep(0.02)
        if process.poll() is not None:
            break
        output = process.stdout.readline()
        if output:
            logger.debug(output.strip())

def run_class_task(name: str):
    import subprocess
    process = subprocess.Popen(['mvn', 'chatunitest:class', f'-DselectClass={name}'], stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT)
    # 创建一个线程来处理子进程的输出
    thread = threading.Thread(target=handle_output, args=(process,))
    thread.start()

    # 等待子进程结束
    process.wait()
    # 等待输出处理线程结束
    thread.join(5)


import traceback

for x in unfinished:
    try:
        logger.info("start: " + x['class_name'])
        st = time.time()
        run_class_task(x['class_name'])
        logger.info(f"finished: {x['class_name']}, duration: {time.time() - st}")
        db.update({"state": True}, Query().class_name == x['class_name'])
    except Exception as e:
        logger.error(f"error: {x['class_name']}")
        logger.error(traceback.format_exc())

