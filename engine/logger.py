"""日志模块 —— 同时输出到控制台和文件，方便调试"""

import sys
import os
import traceback
from datetime import datetime

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
LOG_FILE = os.path.join(LOG_DIR, "game.log")


def setup_logging() -> None:
    """初始化日志: 后续所有 print 和未捕获异常都会写入日志文件"""
    os.makedirs(LOG_DIR, exist_ok=True)

    # 打开日志文件
    log_fp = open(LOG_FILE, "a", encoding="utf-8", buffering=1)  # 行缓冲

    # 写入启动分隔线
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_fp.write(f"\n{'='*60}\n")
    log_fp.write(f"  Game started at {timestamp}\n")
    log_fp.write(f"{'='*60}\n")

    # 重定向 stdout 和 stderr 到文件 + 控制台
    class Tee:
        def __init__(self, *files):
            self.files = files

        def write(self, data):
            for f in self.files:
                f.write(data)
                f.flush()

        def flush(self):
            for f in self.files:
                f.flush()

    sys.stdout = Tee(sys.stdout, log_fp)
    sys.stderr = Tee(sys.stderr, log_fp)

    # 全局异常捕获
    def excepthook(exc_type, exc_value, exc_tb):
        tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        print(f"[ERROR] {tb_text}", file=sys.stderr)
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = excepthook

    print(f"[LOG] 日志文件: {LOG_FILE}")
