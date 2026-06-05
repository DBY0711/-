"""RPA 调度可视化后端 — Flask REST API + Webhook 触发 + 影刀集成"""
import json
import os
import time
import threading
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
import urllib.request
import urllib.error

app = Flask(__name__, static_folder=".")
DATA_FILE = "server_data.json"
LOG_FILE = "webhook_logs.json"

# 影刀 API 配置
YINGDAO_BASE = "https://api.yingdao.com"
YINGDAO_AK = "yz9Pq6BFnjCUgdwH@platform"
YINGDAO_SK = "gk7VC2BzvEuNTQR6ePKtF1hpndYxHcD9"
_yd_token = None
_yd_token_time = 0

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

# ========== 影刀回调日志 ==========
CALLBACK_LOG = "callback_log.json"

def load_cb_log():
    if os.path.exists(CALLBACK_LOG):
        with open(CALLBACK_LOG, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_cb_log(entry):
    logs = load_cb_log()
    logs.append(entry)
    logs = logs[-500:]
    with open(CALLBACK_LOG, "w", encoding="utf-8") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)

@app.route("/api/yingdao/callback", methods=["POST"])
def yd_callback():
    """接收影刀运行结果回调 → 自动匹配任务 → 失败则重跑"""
    try:
        body = request.get_json(force=True, silent=True) or {}
        entry = {
            "time": datetime.now().isoformat(),
            "body": body
        }
        save_cb_log(entry)

        # 解析回调：影刀回调含 task 级别 status + jobList 数组
        # 实际格式: {"dataType":"task","taskUuid":"...","status":"finish","jobList":[{...}]}
        task_status = body.get("status", "")
        job_list = body.get("jobList", [body])  # 兼容无 jobList 的扁平格式

        for job in job_list:
            app_name = job.get("robotName") or job.get("appName") or ""
            app_uuid = job.get("robotUuid") or job.get("appUuid") or ""
            job_uuid = job.get("jobUuid") or body.get("jobUuid") or ""
            run_status = job.get("status") or task_status
            is_failed = run_status in ["error", "fail", "timeout", "stopped", "cancel"]

            msg = f"[回调] {app_name}: {run_status}"
            if is_failed: msg += " ❌"
            print(msg)

            # 失败则检查是否自动重跑
            if is_failed and job_uuid:
                data = load_data()
                if data:
                    for t in data.get("tasks", []):
                        if t.get("autoRerun") and (
                            t.get("process") == app_name or
                            t.get("robotName", "").lower() in app_name.lower() or
                            app_name.lower() in t.get("process", "").lower()
                        ):
                            print(f"[回调] 自动重跑: {t['process']} → job/retry {job_uuid}")
                            threading.Thread(
                                target=lambda j=job_uuid: yd_api("/oapi/dispatch/v2/job/retry", {"jobUuid": j}),
                                daemon=True
                            ).start()
                            entry["autoRerun"] = {"taskId": t["id"], "process": t["process"], "jobUuid": job_uuid}
                            save_cb_log(entry)
                            break

        return jsonify({"success": True, "message": "回调已接收"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/yingdao/callbacks", methods=["GET"])
def yd_callbacks():
    """查看回调日志"""
    logs = load_cb_log()
    return jsonify({"success": True, "logs": logs[-100:]})

# ========== 影刀 API 集成 ==========

def yd_token():
    """获取影刀 accessToken，缓存 1 小时"""
    global _yd_token, _yd_token_time
    if _yd_token and time.time() - _yd_token_time < 3500:
        return _yd_token
    try:
        url = f"{YINGDAO_BASE}/oapi/token/v2/token/create?accessKeyId={YINGDAO_AK}&accessKeySecret={YINGDAO_SK}"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        _yd_token = data.get("data", {}).get("data", {}).get("accessToken") or data.get("data", {}).get("accessToken")
        _yd_token_time = time.time()
        return _yd_token
    except Exception as e:
        print(f"[影刀] 获取 token 失败: {e}")
        return None

def yd_api(path, body=None, method="POST"):
    """调用影刀 API"""
    token = yd_token()
    if not token:
        return {"success": False, "message": "影刀鉴权失败，请检查 API Key"}
    try:
        url = f"{YINGDAO_BASE}{path}"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        data = json.dumps(body).encode("utf-8") if body else None
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=30) as resp:
            return {"success": True, "data": json.loads(resp.read().decode("utf-8"))}
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="ignore")[:500]
        return {"success": False, "message": f"HTTP {e.code}: {err}"}
    except Exception as e:
        return {"success": False, "message": str(e)}

@app.route("/api/yingdao/sync", methods=["POST"])
def yd_sync():
    """同步影刀最新运行记录"""
    result = yd_api("/oapi/dispatch/v2/task/newest/list")
    if not result["success"]:
        return jsonify(result), 500
    data = result["data"]
    records = []
    try:
        items = data.get("data", data).get("list", []) or data.get("data", data).get("records", [])
        if isinstance(items, dict): items = list(items.values())
        for item in items:
            st = item.get("status", "")
            records.append({
                "process": item.get("appName") or item.get("name", ""),
                "pc": item.get("robotName") or item.get("computerName", ""),
                "status": st,
                "lastRun": item.get("startTime") or item.get("executeTime") or "",
                "error": item.get("errorMessage") or item.get("failReason") or "",
                "jobUuid": item.get("jobUuid") or item.get("uuid", ""),
                "robotUuid": item.get("robotUuid") or "",
                "scheduleUuid": item.get("scheduleUuid") or ""
            })
    except Exception as e:
        return jsonify({"success": False, "message": f"解析失败: {e}", "raw": str(data)[:500]}), 500
    return jsonify({"success": True, "records": records})

@app.route("/api/yingdao/rerun", methods=["POST"])
def yd_rerun():
    """重跑失败的影刀任务（使用 job/retry）"""
    body = request.get_json(force=True, silent=True) or {}
    job_uuid = body.get("jobUuid")
    if not job_uuid:
        return jsonify({"success": False, "message": "缺少 jobUuid"}), 400
    result = yd_api("/oapi/dispatch/v2/job/retry", {"jobUuid": job_uuid})
    return jsonify(result)

@app.route("/api/yingdao/start", methods=["POST"])
def yd_start():
    """启动影刀任务（调度任务）"""
    body = request.get_json(force=True, silent=True) or {}
    schedule_uuid = body.get("scheduleUuid")
    if schedule_uuid:
        result = yd_api("/oapi/dispatch/v2/task/start", {"scheduleUuid": schedule_uuid})
    else:
        robot_uuid = body.get("robotUuid")
        if not robot_uuid:
            return jsonify({"success": False, "message": "需要 scheduleUuid 或 robotUuid"}), 400
        result = yd_api("/oapi/dispatch/v2/job/start", {"robotUuid": robot_uuid})
    return jsonify(result)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
