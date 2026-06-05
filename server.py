"""RPA 调度可视化后端 — Flask REST API"""
import json
import os
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__, static_folder=".")
DATA_FILE = "server_data.json"

def load_data():
    """从 JSON 文件加载任务数据"""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

def save_data(data):
    """保存任务数据到 JSON 文件"""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

@app.route("/")
def index():
    return send_from_directory(".", "index.html")

@app.route("/api/tasks", methods=["GET"])
def get_tasks():
    """获取所有任务"""
    data = load_data()
    if data:
        return jsonify({"success": True, "data": data})
    return jsonify({"success": False, "data": None})

@app.route("/api/tasks", methods=["POST"])
def post_tasks():
    """保存所有任务"""
    try:
        body = request.get_json(force=True, silent=True)
        if not body:
            return jsonify({"success": False, "message": "无效的JSON数据"}), 400
        tasks = body.get("tasks", [])
        nid = body.get("nid", 1)
        data = {
            "tasks": tasks,
            "nid": nid,
            "updated_at": datetime.now().isoformat()
        }
        save_data(data)
        return jsonify({"success": True, "message": f"保存成功，{len(tasks)} 条任务"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/tasks/backup", methods=["GET"])
def backup():
    """下载备份"""
    data = load_data()
    if data:
        return jsonify(data)
    return jsonify({"tasks": [], "nid": 1})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
