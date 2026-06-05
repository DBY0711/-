"""JSON 文件读写封装"""
import json
import os
from typing import List, Optional


def _ensure_dir(filepath: str):
    """确保文件所在目录存在"""
    d = os.path.dirname(filepath)
    if d and not os.path.exists(d):
        os.makedirs(d)


def load_json(filepath: str, default=None) -> Optional[list]:
    """读取 JSON 文件，文件不存在时返回 default"""
    if default is None:
        default = []
    if not os.path.exists(filepath):
        return default
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return default


def save_json(filepath: str, data):
    """保存数据到 JSON 文件"""
    _ensure_dir(filepath)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
