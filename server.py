"""RPA 调度可视化 — Flask 后端 + 影刀集成 + 回调重试 + 运行历史"""
import json
import os
import time
import threading
import uuid
import hashlib
import hmac
from datetime import datetime
from functools import wraps
from flask import Flask, request, jsonify, send_from_directory, session, redirect

import requests

app = Flask(__name__, static_folder=".")
app.secret_key = os.environ.get("SECRET_KEY", "rpa-schedule-secret-" + str(uuid.uuid4())[:8])

# ============================================================
# 配置（敏感信息优先从环境变量读取）
# ============================================================
DATA_FILE = "server_data.json"
RUN_HISTORY_FILE = "run_history.json"
CALLBACK_LOG_FILE = "callback_log.json"

YINGDAO_BASE = "https://api.yingdao.com"
YINGDAO_AK = os.environ.get("YINGDAO_AK", "2pTMyf0WR4U8xSHD@platform")
YINGDAO_SK = os.environ.get("YINGDAO_SK", "MAzEKXWJ5a7g9FfDCs4qu1BNQd2xtebS")
API_TOKEN = os.environ.get("API_TOKEN", "rpa-schedule-token-2026")
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "rpa2026!")
TOKEN_TTL = 7100

_token_cache = {"token": None, "expires_at": 0}
_token_lock = threading.Lock()

# 简易速率限制
_rate_limit = {}  # {ip: [(time, path), ...]}
RATE_LIMIT = 60  # 每分钟最多 60 次请求


def _check_token(f):
    """装饰器：验证 API Token"""
    @wraps(f)
    def wrapper(*a, **kw):
        token = request.headers.get("X-API-Token") or request.args.get("token") or ""
        if token != API_TOKEN:
            return jsonify({"success": False, "message": "未授权：缺少有效 API Token"}), 401
        return f(*a, **kw)
    return wrapper


def _rate_check():
    """简易速率限制（内存版）"""
    ip = request.remote_addr or "unknown"
    now = time.time()
    if ip not in _rate_limit:
        _rate_limit[ip] = []
    _rate_limit[ip] = [t for t in _rate_limit[ip] if now - t[0] < 60]
    if len(_rate_limit[ip]) >= RATE_LIMIT:
        return False
    _rate_limit[ip].append((now, request.path))
    return True


def _login_required(f):
    """装饰器：需要登录"""
    @wraps(f)
    def wrapper(*a, **kw):
        if not session.get("logged_in"):
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"success": False, "message": "请先登录"}), 401
            return redirect("/login.html")
        return f(*a, **kw)
    return wrapper


def _verify_yingdao_sign():
    """验证影刀回调签名"""
    body = request.get_json(force=True, silent=True) or {}
    params = body.get("params", {})
    sign = params.get("sign", "")
    if not sign:
        return True  # 无签名时放行（兼容旧格式）
    body_md5 = params.get("bodyMd5", "")
    timestamp = params.get("timestamp", "")
    payload = body.get("body", {})
    payload_str = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    computed_md5 = hashlib.md5(payload_str.encode()).hexdigest()
    sign_str = f"{computed_md5}\n{timestamp}"
    computed_sign = hmac.new(
        YINGDAO_SK.encode(), sign_str.encode(), hashlib.sha1
    ).hexdigest()
    return hmac.compare_digest(computed_sign, sign)


# ============================================================
# 通用 JSON 读写
# ============================================================
def _read_json(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def _write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ============================================================
# 任务数据
# ============================================================
def load_tasks():
    data = _read_json(DATA_FILE, {"tasks": [], "nid": 1})
    if "nid" not in data:
        data["nid"] = max((t.get("id", 0) for t in data.get("tasks", [])), default=0) + 1
    return data


def save_tasks(data):
    data["updated_at"] = datetime.now().isoformat()
    _write_json(DATA_FILE, data)


# ============================================================
# 运行历史
# ============================================================
def load_run_history():
    return _read_json(RUN_HISTORY_FILE, [])


def save_run_history(records):
    _write_json(RUN_HISTORY_FILE, records[-2000:])


# ============================================================
# 回调日志 & Webhook 日志
# ============================================================
def load_callback_log():
    return _read_json(CALLBACK_LOG_FILE, [])


def save_callback_log(entry):
    logs = load_callback_log()
    logs.append(entry)
    _write_json(CALLBACK_LOG_FILE, logs[-500:])


# ============================================================
# 数据迁移：旧格式 → 新格式
# ============================================================
def _migrate_old_data():
    data = load_tasks()
    needs_save = False
    for t in data.get("tasks", []):
        if "retryEnabled" not in t:
            t["retryEnabled"] = t.pop("autoRerun", False)
            needs_save = True
        if "maxRetry" not in t:
            t["maxRetry"] = 3
            needs_save = True
        if "retryCount" not in t:
            t["retryCount"] = 0
            needs_save = True
        if "scheduleUuid" not in t:
            t["scheduleUuid"] = ""
            needs_save = True
        if "robotUuid" not in t:
            t["robotUuid"] = ""
            needs_save = True
        if "robotName" not in t:
            t["robotName"] = ""
            needs_save = True
        if "lastRun" not in t:
            t["lastRun"] = ""
            needs_save = True
        if "runTimes" not in t:
            t["runTimes"] = 0
            needs_save = True
        if "sourceType" not in t:
            t["sourceType"] = ""
            needs_save = True
        if "retryDate" not in t:
            t["retryDate"] = ""
            needs_save = True
        if "taskType" not in t:
            t["taskType"] = "yingdao"
            needs_save = True
        if "triggerMethod" not in t:
            t["triggerMethod"] = ""
            needs_save = True
        if "operationScope" not in t:
            t["operationScope"] = ""
            needs_save = True
    if needs_save:
        save_tasks(data)
        print("[迁移] 已将旧数据格式升级到新版本")


_migrate_old_data()


# ============================================================
# 影刀 API 客户端
# ============================================================
def _get_token():
    """获取影刀 accessToken，线程安全，自动缓存"""
    with _token_lock:
        now = time.time()
        if _token_cache["token"] and now < _token_cache["expires_at"] - 300:
            return _token_cache["token"]

        url = f"{YINGDAO_BASE}/oapi/token/v2/token/create"
        try:
            resp = requests.get(url, params={
                "accessKeyId": YINGDAO_AK,
                "accessKeySecret": YINGDAO_SK
            }, timeout=15)
            resp.raise_for_status()
            body = resp.json()
            token = (
                body.get("data", {}).get("data", {}).get("accessToken")
                or body.get("data", {}).get("accessToken")
            )
            if not token:
                raise RuntimeError("无法从影刀响应中提取 accessToken")
            _token_cache["token"] = token
            _token_cache["expires_at"] = now + TOKEN_TTL
            return token
        except Exception as e:
            print(f"[影刀] 获取 token 失败: {e}")
            return None


def _yd_api(path, body=None, method="POST"):
    """通用影刀 API 调用"""
    token = _get_token()
    if not token:
        return {"success": False, "message": "影刀鉴权失败，请检查 API Key"}

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    url = f"{YINGDAO_BASE}{path}"
    try:
        if method == "POST":
            resp = requests.post(url, json=body, headers=headers, timeout=30)
        else:
            resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        return {"success": True, "data": resp.json()}
    except requests.exceptions.HTTPError as e:
        err_body = e.response.text[:500] if e.response else ""
        return {"success": False, "message": f"HTTP {e.response.status_code if e.response else '?'}: {err_body}"}
    except Exception as e:
        return {"success": False, "message": str(e)}


def _today():
    return datetime.now().strftime("%Y-%m-%d")


def _parse_text_report(text):
    """解析文本格式错误报告：时间：...；运行机器人：...；运行异常计划：..."""
    import re
    result = {}
    parts = re.split(r'[;；]', text)
    for part in parts:
        part = part.strip().rstrip('。.')
        if not part:
            continue
        kv = re.split(r'[：:]', part, maxsplit=1)
        if len(kv) == 2:
            key = kv[0].strip()
            val = kv[1].strip()
            result[key] = val
    return result


def _daily_reset(task):
    """如果不在当天，重置重试次数"""
    if task.get("retryDate") != _today():
        task["retryCount"] = 0
        task["retryDate"] = _today()


def _map_status(yd_status):
    """影刀状态 → 中文"""
    m = {
        "waiting": "等待中", "running": "运行中", "finish": "已完成",
        "error": "错误", "stopped": "已停止", "stopping": "停止中",
        "cancel": "已取消", "timeout": "超时",
    }
    return m.get(str(yd_status).lower(), str(yd_status))


def _extract_client(item):
    """从 taskClients 提取第一个客户端的详细信息"""
    clients = item.get("taskClients", [])
    if clients:
        c = clients[0]
        return {
            "pc": c.get("robotClientName", ""),
            "robotName": c.get("currentRobotName", ""),
            "robotUuid": c.get("currentRobotUuid", ""),
            "clientStatus": c.get("clientStatus", ""),
        }
    return {}

def _t2m(s):
    """HH:MM → 分钟数"""
    try:
        h, m = str(s).split(":")
        return int(h) * 60 + int(m)
    except Exception:
        return 0


def _m2t(m):
    """分钟数 → HH:MM"""
    m = m % 1440
    return f"{m // 60:02d}:{m % 60:02d}"


def _auto_time(schedule_uuid, index=0):
    """根据 scheduleUuid 自动分配开始时间，使任务均匀分布在 24 小时"""
    if schedule_uuid:
        h = hash(schedule_uuid) % 1440
    else:
        h = (index * 37 + 480) % 1440  # 从 08:00 开始分布
    m = (h // 10) * 10  # 对齐到 10 分钟
    return f"{m // 60:02d}:{m % 60:02d}"
    return str(status).lower() in ("error", "fail", "timeout", "cancel")


# ============================================================
# Flask 路由
# ============================================================

# ---------- 登录 ----------
@app.route("/login.html")
def login_page():
    return send_from_directory(".", "login.html")


@app.route("/api-docs.html")
def api_docs():
    return send_from_directory(".", "api-docs.html")


@app.route("/api/login", methods=["POST"])
def api_login():
    body = request.get_json(force=True, silent=True) or {}
    user = body.get("username", "").strip()
    pwd = body.get("password", "")
    if user == ADMIN_USER and pwd == ADMIN_PASS:
        session["logged_in"] = True
        session["user"] = user
        return jsonify({"success": True, "message": "登录成功"})
    return jsonify({"success": False, "message": "用户名或密码错误"}), 401


@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"success": True, "message": "已退出"})


@app.route("/api/check-login")
def api_check_login():
    return jsonify({"logged_in": bool(session.get("logged_in")), "user": session.get("user", "")})


# ---------- 主页 ----------
@app.route("/")
@_login_required
def index():
    return send_from_directory(".", "index.html")


# ---------- 任务 CRUD ----------
@app.route("/api/tasks", methods=["GET"])
@_login_required
def api_get_tasks():
    data = load_tasks()
    return jsonify({"success": True, "data": data})


@app.route("/api/tasks", methods=["POST"])
@_check_token
def api_save_tasks():
    try:
        body = request.get_json(force=True, silent=True)
        if not body:
            return jsonify({"success": False, "message": "无效的JSON数据"}), 400
        tasks = body.get("tasks", [])
        nid = body.get("nid", 1)
        data = {"tasks": tasks, "nid": nid}
        save_tasks(data)
        return jsonify({"success": True, "message": f"保存成功，{len(tasks)} 条任务"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/tasks/backup", methods=["GET"])
def api_backup():
    return jsonify(load_tasks())




# ---------- 影刀：同步 ----------
@app.route("/api/yingdao/sync", methods=["POST"])
@_login_required
def api_yingdao_sync():
    """从影刀 schedule/list(全部计划) + task/newest/list(运行详情) 合并"""
    # 1. 获取全部计划列表（含从未运行过的）
    sched_result = _yd_api("/oapi/dispatch/v2/schedule/list", {"page": 1, "size": 200})
    schedules = []
    if sched_result["success"]:
        raw = sched_result["data"]
        items = raw.get("data", raw)
        if isinstance(items, dict):
            items = items.get("list", []) or items.get("records", [])
        if isinstance(items, list):
            schedules = items

    # 2. 获取最新运行记录（含 taskClients 详情）
    runs_result = _yd_api("/oapi/dispatch/v2/task/newest/list", {"page": 1, "size": 200})
    runs = []
    if runs_result["success"]:
        raw = runs_result["data"]
        items = raw.get("data", raw)
        if isinstance(items, dict):
            items = items.get("list", []) or items.get("records", [])
        if isinstance(items, list):
            runs = items

    # 3. 建立 sourceUuid → 运行记录 索引
    run_map = {}
    for r in runs:
        su = r.get("sourceUuid") or ""
        if su and su not in run_map:
            run_map[su] = r

    # 4. 以计划列表为主，运行记录补充详情
    data = load_tasks()
    existing = {t.get("scheduleUuid"): t for t in data["tasks"] if t.get("scheduleUuid")}
    merged = []
    idx = 0

    for s in schedules:
        sched_uuid = s.get("scheduleUuid", "")
        if not sched_uuid:
            continue

        process = s.get("scheduleName", "")
        enabled = s.get("enabled", True)
        sched_type = s.get("scheduleType", "")  # period / manual

        # 从运行记录补充详情
        run = run_map.get(sched_uuid, {})
        client = _extract_client(run) if run else {}
        robot_uuid = client.get("robotUuid", "")
        robot_name = client.get("robotName", "")
        pc = client.get("pc", "")
        run_time = run.get("timeout") or 600
        # 状态 = 启用/未启用（来自计划配置）
        status = "已启用" if enabled else "已禁用"
        last_run = run.get("updateTime") or run.get("createTime") or ""
        run_times = run.get("runTimes", 0)
        source_type = run.get("sourceType") or sched_type or ""
        # 从 cronInterface 提取计划运行时间
        cron = s.get("cronInterface", {})
        next_time = cron.get("nextTime", "")  # "2026-06-06 01:30:00"
        if next_time:
            # 提取 HH:MM
            try:
                auto_start = next_time.split(" ")[1][:5]  # "01:30"
            except Exception:
                auto_start = _auto_time(sched_uuid, idx)
        else:
            auto_start = _auto_time(sched_uuid, idx)
        idx += 1

        if sched_uuid in existing:
            t = existing[sched_uuid]
            t["process"] = process or t["process"]
            t["robotUuid"] = robot_uuid or t.get("robotUuid", "")
            t["robotName"] = robot_name or t.get("robotName", "")
            t["pc"] = pc or t["pc"]
            if not t.get("runtime"):
                t["runtime"] = run_time
            if t.get("start") in ("09:00", "", None):
                t["start"] = auto_start
                t["end"] = _m2t(_t2m(auto_start) + max(t["runtime"] // 60, 1))
            t["status"] = status
            t["lastRun"] = last_run
            t["runTimes"] = run_times
            t["sourceType"] = source_type or t.get("sourceType", "")
            if run.get("status") in ("finish", "success"):
                t["retryCount"] = 0
                t["retryDate"] = _today()
            merged.append(t)
            del existing[sched_uuid]
        else:
            end_min = _t2m(auto_start) + max(run_time // 60, 1)
            nt = {
                "id": data["nid"],
                "scheduleUuid": sched_uuid,
                "process": process,
                "robotUuid": robot_uuid,
                "robotName": robot_name,
                "pc": pc,
                "start": auto_start,
                "end": f"{end_min // 60:02d}:{end_min % 60:02d}",
                "runtime": run_time,
                "status": status,
                "lastRun": last_run,
                "runTimes": run_times,
                "category": "",
                "retryEnabled": False,
                "maxRetry": 3,
                "retryCount": 0,
                "sourceType": source_type,
                "taskType": "yingdao",
                "triggerMethod": "",
                "operationScope": "",
            }
            data["nid"] += 1
            merged.append(nt)

    # 保留手动创建的无 scheduleUuid 的本地任务
    for t in existing.values():
        merged.append(t)

    data["tasks"] = merged
    save_tasks(data)

    enabled_count = sum(1 for s in schedules if s.get("enabled"))
    return jsonify({
        "success": True,
        "message": f"同步完成，{len(merged)} 条任务（已启用 {enabled_count}）",
        "runCount": len(runs),
        "schedCount": len(schedules),
        "enabledCount": enabled_count,
    })


# ---------- 影刀：启动 ----------
@app.route("/api/yingdao/start", methods=["POST"])
@_check_token
def api_yingdao_start():
    """启动任务 — 先查 schedule/detail 获取 robotUuid，再用 job/start"""
    body = request.get_json(force=True, silent=True) or {}
    schedule_uuid = body.get("scheduleUuid", "")
    robot_uuid = body.get("robotUuid", "")
    pc = body.get("pc", "")

    # 从 schedule/detail 获取正确的 robotUuid 和 pc
    if schedule_uuid:
        detail = _yd_api("/oapi/dispatch/v2/schedule/detail", {"scheduleUuid": schedule_uuid})
        if detail["success"]:
            d = detail["data"].get("data", detail["data"])
            robots = d.get("robotList", [])
            clients = d.get("robotClientList", [])
            if robots:
                robot_uuid = robots[0].get("robotUuid", "") or robot_uuid
            if clients:
                pc = clients[0].get("robotClientName", "") or pc

    if not robot_uuid:
        return jsonify({"success": False, "message": "缺少 robotUuid，且 schedule/detail 也未返回"}), 400

    # 用 job/start 启动
    req_body = {"robotUuid": robot_uuid}
    if pc:
        req_body["accountName"] = pc
    result = _yd_api("/oapi/dispatch/v2/job/start", req_body)

    # 记录运行历史
    now = datetime.now().isoformat()
    process = body.get("process", "")
    record = {
        "id": str(uuid.uuid4()),
        "time": now,
        "source": "manual_start",
        "dataType": "job",
        "scheduleUuid": schedule_uuid,
        "taskUuid": "",
        "jobUuid": result.get("data", {}).get("data", {}).get("jobUuid", ""),
        "process": process,
        "pc": pc,
        "status": "started",
        "msg": "手动启动",
        "startTime": now,
        "endTime": "",
        "retryTriggered": False,
        "retryCount": 0,
        "retryJobUuid": "",
    }
    records = load_run_history()
    records.append(record)
    save_run_history(records)

    # 标记对应告警为手动重试
    if process:
        alerts = load_alerts()
        for a in alerts:
            if a.get("process") == process and a.get("status") == "异常":
                a["retryType"] = "manual"
                save_alerts(alerts)
                break

    return jsonify(result)


# ---------- 影刀：手动重跑 ----------
@app.route("/api/yingdao/rerun", methods=["POST"])
@_check_token
def api_yingdao_rerun():
    body = request.get_json(force=True, silent=True) or {}
    job_uuid = body.get("jobUuid")
    if not job_uuid:
        return jsonify({"success": False, "message": "缺少 jobUuid"}), 400

    result = _yd_api("/oapi/dispatch/v2/job/retry", {"jobUuid": job_uuid})

    # 记录手动重跑
    record = {
        "id": str(uuid.uuid4()),
        "time": datetime.now().isoformat(),
        "source": "manual_rerun",
        "dataType": "job",
        "scheduleUuid": body.get("scheduleUuid", ""),
        "taskUuid": "",
        "jobUuid": job_uuid,
        "process": body.get("process", ""),
        "pc": body.get("pc", ""),
        "status": "retry_queued" if result["success"] else "retry_failed",
        "msg": "手动触发重跑" if result["success"] else f"重跑失败: {result.get('message', '')}",
        "startTime": "",
        "endTime": "",
        "retryTriggered": False,
        "retryCount": 0,
        "retryJobUuid": "",
    }
    records = load_run_history()
    records.append(record)
    save_run_history(records)

    return jsonify(result)


# ---------- 影刀：回调（核心） ----------
@app.route("/api/yingdao/callback", methods=["POST"])
def api_yingdao_callback():
    """接收影刀运行结果回调 → 记录运行历史 → 按规则自动重试"""
    raw = request.get_json(force=True, silent=True) or {}

    # 验证影刀签名
    if not _verify_yingdao_sign():
        return jsonify({"success": False, "message": "签名验证失败"}), 403

    # 保存原始回调日志
    save_callback_log({"time": datetime.now().isoformat(), "body": raw})

    # 真实回调格式: {"headers":{...}, "params":{...}, "body":{...job data...}}
    # 兼容直接 POST job 数据的扁平格式
    job = raw.get("body", raw)
    # 如果是 task 级别回调（有 jobList），取第一条 job
    if job.get("dataType") == "task" and job.get("jobList"):
        job = job["jobList"][0]

    job_uuid = job.get("jobUuid", "")
    robot_name = job.get("robotName", "")
    robot_uuid = job.get("robotUuid", "")
    pc = job.get("robotClientName", "")
    status = job.get("status", "")
    msg = job.get("msg", "")
    start_time = job.get("startTime", "")
    end_time = job.get("endTime", "")

    if not job_uuid:
        return jsonify({"success": False, "message": "回调缺少 jobUuid"}), 400

    # ---- 创建运行历史记录 ----
    record = {
        "id": str(uuid.uuid4()),
        "time": datetime.now().isoformat(),
        "source": "yingdao_callback",
        "dataType": job.get("dataType", "job"),
        "scheduleUuid": "",
        "taskUuid": "",
        "jobUuid": job_uuid,
        "process": robot_name,
        "pc": pc,
        "status": _map_status(status),
        "msg": msg,
        "startTime": str(start_time) if start_time else "",
        "endTime": str(end_time) if end_time else "",
        "retryTriggered": False,
        "retryCount": 0,
        "retryJobUuid": "",
    }
    records = load_run_history()
    records.append(record)
    save_run_history(records)

    # ---- 任务匹配与重试逻辑 ----
    local_data = load_tasks()
    tasks = local_data.get("tasks", [])

    # 匹配本地任务：process 精确 > robotUuid > process 模糊
    def _match_task(name):
        nl = name.lower().strip()
        # 1. 精确匹配 process（scheduleName 唯一）
        for t in tasks:
            if (t.get("process") or "").lower().strip() == nl:
                return t
        # 2. robotUuid 精确匹配
        if robot_uuid:
            for t in tasks:
                if t.get("robotUuid") == robot_uuid:
                    return t
        # 3. 精确匹配 robotName（可能多个，返回第一个启用了重试的）
        fallback = None
        for t in tasks:
            if (t.get("robotName") or "").lower().strip() == nl:
                if t.get("retryEnabled"):
                    return t
                if not fallback:
                    fallback = t
        if fallback:
            return fallback
        # 4. 模糊匹配：回调名包含在 process 中
        for t in tasks:
            if nl and nl in (t.get("process") or "").lower():
                return t
        return None

    matched = _match_task(robot_name)

    is_fail = str(status).lower() in ("error", "fail", "timeout", "cancel")
    is_success = str(status).lower() == "finish"

    if is_fail:
        _add_alert(robot_name, pc, msg, "yingdao_callback", "异常", "auto")

    if is_fail and matched:
        _daily_reset(matched)
        # 更新任务状态
        matched["status"] = _map_status(status) if matched.get("taskType") != "manual" else matched["status"]
        matched["lastRun"] = end_time or datetime.now().isoformat()

        # 只有勾选自动重试 && 未超过最大次数才重试
        if matched.get("retryEnabled") and matched.get("retryCount", 0) < matched.get("maxRetry", 3):
            retry_result = _yd_api("/oapi/dispatch/v2/job/retry", {"jobUuid": job_uuid})
            if retry_result["success"]:
                matched["retryCount"] = matched.get("retryCount", 0) + 1
                record["retryTriggered"] = True
                record["retryCount"] = matched["retryCount"]
                retry_data = retry_result.get("data", {})
                if isinstance(retry_data, dict):
                    record["retryJobUuid"] = retry_data.get("jobUuid", "")
                print(f"[回调] 自动重试: {matched['process']} jobUuid={job_uuid} 第{matched['retryCount']}次")
            else:
                print(f"[回调] 重试失败: {matched['process']} — {retry_result.get('message', '')}")
        else:
            reason = "未启用重试" if not matched.get("retryEnabled") else f"已达上限({matched['retryCount']}/{matched['maxRetry']})"
            print(f"[回调] 跳过重试: {matched['process']} — {reason}")

        save_run_history(records)

    elif is_success and matched:
        # 成功 → 重置重试计数
        matched["retryCount"] = 0
        matched["retryDate"] = _today()
        matched["status"] = "已启用"
        matched["lastRun"] = end_time or datetime.now().isoformat()
        save_run_history(records)

    save_tasks(local_data)
    return jsonify({"success": True, "message": "回调已接收"})


# ---------- 影刀：运行历史 ----------
@app.route("/api/yingdao/run-history", methods=["GET"])
@_login_required
def api_run_history():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    status_filter = request.args.get("status", "").strip()
    search = request.args.get("search", "").strip()

    all_records = load_run_history()

    if status_filter:
        all_records = [r for r in all_records if r.get("status") == status_filter]
    if search:
        s = search.lower()
        all_records = [r for r in all_records
                       if s in (r.get("process") or "").lower()
                       or s in (r.get("pc") or "").lower()
                       or s in (r.get("msg") or "").lower()]

    total = len(all_records)
    # 最新在前
    all_records = all_records[::-1]
    start = (page - 1) * per_page
    end = start + per_page
    page_records = all_records[start:end]

    return jsonify({
        "success": True,
        "records": page_records,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": max(1, (total + per_page - 1) // per_page),
    })


# ---------- 异常告警记录 ----------
ALERTS_FILE = "alerts.json"


def load_alerts():
    return _read_json(ALERTS_FILE, [])


def save_alerts(alerts):
    _write_json(ALERTS_FILE, alerts[-500:])


@app.route("/api/alerts", methods=["GET"])
@_login_required
def api_get_alerts():
    status = request.args.get("status", "")
    alerts = load_alerts()
    if status:
        alerts = [a for a in alerts if a.get("status") == status]
    return jsonify({"success": True, "alerts": alerts[::-1]})  # 最新在前


@app.route("/api/alerts/<alert_id>", methods=["PUT"])
@_login_required
def api_update_alert(alert_id):
    body = request.get_json(force=True, silent=True) or {}
    alerts = load_alerts()
    for a in alerts:
        if a.get("id") == alert_id:
            if "checked" in body:
                a["checked"] = body["checked"]
            if "note" in body:
                a["note"] = body["note"]
            if "status" in body:
                a["status"] = body["status"]
            if "retryType" in body:
                a["retryType"] = body["retryType"]
            save_alerts(alerts)
            return jsonify({"success": True})
    return jsonify({"success": False, "message": "未找到"}), 404


@app.route("/api/alerts/<alert_id>", methods=["DELETE"])
@_login_required
def api_delete_alert(alert_id):
    alerts = load_alerts()
    alerts = [a for a in alerts if a.get("id") != alert_id]
    save_alerts(alerts)
    return jsonify({"success": True})


def _add_alert(process, pc, msg, source, status="异常", retry_type=""):
    """自动添加告警记录（由回调/error-report触发）"""
    alerts = load_alerts()
    alerts.append({
        "id": str(uuid.uuid4()),
        "time": datetime.now().isoformat(),
        "process": process,
        "pc": pc,
        "status": status,
        "msg": msg[:300] if msg else "",
        "source": source,
        "retryType": retry_type,
        "checked": False,
        "note": "",
    })
    save_alerts(alerts)


# ---------- 外部失败报告 ----------
@app.route("/api/error-report", methods=["POST"])
@_check_token
def api_error_report():
    """接收外部失败报告 → 匹配任务 → 判断是否重试"""
    content_type = request.content_type or ""
    body = {}

    raw_text = ""
    if "json" in content_type:
        body = request.get_json(force=True, silent=True) or {}
        # 数据可能在 body.body.message（回调包装格式）或 body.message
        inner = body.get("body", {})
        raw_text = inner.get("message", "") or body.get("message", "")
    else:
        raw_text = request.get_data(as_text=True) or ""

    # 如果 body 中没有直接字段，从文本解析
    process = body.get("process", "").strip()
    msg = body.get("msg", body.get("error", ""))
    pc = body.get("pc", "").strip()
    job_uuid = body.get("jobUuid", "")

    if raw_text and not process:
        parsed = _parse_text_report(raw_text)
        process = parsed.get("运行异常计划") or parsed.get("运行异常应用") or process
        pc = parsed.get("运行机器人") or pc
        msg = parsed.get("错误信息") or msg or raw_text[:500]
        if not body.get("reportTime"):
            body["reportTime"] = parsed.get("时间", "")

    if not process:
        return jsonify({"success": False, "message": "缺少 process 参数"}), 400

    # 匹配本地任务
    local_data = load_tasks()
    tasks = local_data.get("tasks", [])
    matched = None
    nl = process.lower()
    # 精确匹配 process
    for t in tasks:
        if (t.get("process") or "").lower().strip() == nl:
            matched = t
            break
    # 模糊匹配
    if not matched:
        for t in tasks:
            if nl in (t.get("process") or "").lower():
                matched = t
                break

    # 自动告警
    retry_type = body.get("retryType", "manual")
    _add_alert(process, pc or (matched.get("pc", "") if matched else ""), msg, "manual_report", "异常", retry_type)

    # 创建运行记录
    record = {
        "id": str(uuid.uuid4()),
        "time": datetime.now().isoformat(),
        "source": "manual_report",
        "dataType": "job",
        "scheduleUuid": matched.get("scheduleUuid", "") if matched else "",
        "taskUuid": "",
        "jobUuid": job_uuid,
        "process": process,
        "pc": pc or (matched.get("pc", "") if matched else ""),
        "status": "错误",
        "msg": msg,
        "startTime": datetime.now().isoformat(),
        "endTime": "",
        "retryTriggered": False,
        "retryCount": 0,
        "retryJobUuid": "",
    }
    records = load_run_history()
    records.append(record)

    if not matched:
        save_run_history(records)
        return jsonify({"success": True, "message": f"未匹配到任务: {process}", "matched": False, "retried": False})

    _daily_reset(matched)
    # 判断是否重试
    if matched.get("retryEnabled") and matched.get("retryCount", 0) < matched.get("maxRetry", 3):
        if job_uuid:
            # 有 jobUuid → 重跑
            retry_result = _yd_api("/oapi/dispatch/v2/job/retry", {"jobUuid": job_uuid})
        else:
            # 无 jobUuid → 启动新任务
            sched_uuid = matched.get("scheduleUuid", "")
            robot_uuid = matched.get("robotUuid", "")
            task_pc = matched.get("pc", "")
            if sched_uuid:
                detail = _yd_api("/oapi/dispatch/v2/schedule/detail", {"scheduleUuid": sched_uuid})
                if detail["success"]:
                    d = detail["data"].get("data", detail["data"])
                    robots = d.get("robotList", [])
                    clients = d.get("robotClientList", [])
                    if robots:
                        robot_uuid = robots[0].get("robotUuid", "") or robot_uuid
                    if clients:
                        task_pc = clients[0].get("robotClientName", "") or task_pc
            if robot_uuid:
                req_body = {"robotUuid": robot_uuid}
                if task_pc:
                    req_body["accountName"] = task_pc
                retry_result = _yd_api("/oapi/dispatch/v2/job/start", req_body)
            else:
                retry_result = {"success": False, "message": "缺少 robotUuid"}

        if retry_result["success"]:
            matched["retryCount"] = matched.get("retryCount", 0) + 1
            record["retryTriggered"] = True
            record["retryCount"] = matched["retryCount"]
            retry_data = retry_result.get("data", {})
            if isinstance(retry_data, dict):
                record["retryJobUuid"] = retry_data.get("jobUuid", "")
            save_tasks(local_data)
            save_run_history(records)
            return jsonify({
                "success": True,
                "message": f"已触发重试: {process}（第{matched['retryCount']}次）",
                "matched": True, "retried": True, "retryCount": matched["retryCount"]
            })
        else:
            save_run_history(records)
            return jsonify({
                "success": False,
                "message": f"重试失败: {retry_result.get('message', '')}",
                "matched": True, "retried": False
            })

    save_run_history(records)
    reason = "未启用重试" if not matched.get("retryEnabled") else f"已达上限({matched.get('retryCount',0)}/{matched.get('maxRetry',3)})"
    return jsonify({
        "success": True,
        "message": f"已记录但跳过重试: {reason}",
        "matched": True, "retried": False
    })


# ---------- 影刀：回调日志 ----------
@app.route("/api/yingdao/callbacks", methods=["GET"])
def api_yingdao_callbacks():
    logs = load_callback_log()
    return jsonify({"success": True, "logs": logs[-100:]})


@app.route("/api/yingdao/callbacks/<log_id>", methods=["DELETE"])
def api_yingdao_callback_delete(log_id):
    """删除单条回调日志"""
    logs = load_callback_log()
    logs = [l for l in logs if l.get("time") != log_id]
    _write_json(CALLBACK_LOG_FILE, logs)
    return jsonify({"success": True, "message": "已删除"})


@app.route("/api/yingdao/callbacks", methods=["DELETE"])
def api_yingdao_callbacks_clear():
    """清空全部回调日志"""
    _write_json(CALLBACK_LOG_FILE, [])
    return jsonify({"success": True, "message": "已清空"})


# ---------- 运行历史：删除 ----------
@app.route("/api/yingdao/run-history/<record_id>", methods=["DELETE"])
def api_run_history_delete(record_id):
    """删除单条运行记录"""
    records = load_run_history()
    records = [r for r in records if r.get("id") != record_id]
    save_run_history(records)
    return jsonify({"success": True, "message": "已删除"})


@app.route("/api/yingdao/run-history", methods=["DELETE"])
def api_run_history_clear():
    """清空全部运行记录"""
    save_run_history([])
    return jsonify({"success": True, "message": "已清空"})




# ============================================================
# 启动
# ============================================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
