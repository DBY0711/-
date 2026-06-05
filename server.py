"""RPA 调度可视化后端 — Flask REST API + Webhook 触发"""
import json
import os
import threading
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
import urllib.request
import urllib.error

app = Flask(__name__, static_folder=".")
DATA_FILE = "server_data.json"
LOG_FILE = "webhook_logs.json"

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

# ========== Webhook 触发 ==========

def load_logs():
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_logs(logs):
    # 保留最近 200 条
    logs = logs[-200:]
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)
    return logs

@app.route("/api/webhook/trigger", methods=["POST"])
def trigger_webhook():
    """手动触发单个任务的 Webhook"""
    try:
        body = request.get_json(force=True, silent=True)
        task_id = body.get("id")
        url = body.get("url", "").strip()

        if not url:
            return jsonify({"success": False, "message": "Webhook URL 未配置"}), 400

        # 异步发送请求，不阻塞主线程
        def do_request():
            try:
                req = urllib.request.Request(
                    url,
                    data=json.dumps({"task_id": task_id, "triggered_at": datetime.now().isoformat()}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    status = resp.status
                    body_text = resp.read().decode("utf-8", errors="ignore")[:200]
                result = {"task_id": task_id, "url": url, "time": datetime.now().isoformat(),
                          "success": True, "status": status, "response": body_text}
            except Exception as e:
                result = {"task_id": task_id, "url": url, "time": datetime.now().isoformat(),
                          "success": False, "status": 0, "response": str(e)[:200]}
            logs = load_logs()
            logs.append(result)
            save_logs(logs)

        threading.Thread(target=do_request, daemon=True).start()

        return jsonify({"success": True, "message": "Webhook 已触发，正在请求..."})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/webhook/logs", methods=["GET"])
def get_logs():
    """获取 Webhook 触发日志"""
    logs = load_logs()
    return jsonify({"success": True, "logs": logs[-50:]})  # 最近 50 条

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
