import os
import sys
from functools import wraps
from flask import Flask, request, jsonify, render_template, session, redirect

from storage import db
from wechat_client import wechat_client
from rule_engine import rule_engine

app = Flask(__name__, template_folder="templates")
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "wechat_robot_secret_key_8888")

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("logged_in"):
            return jsonify({"code": 401, "msg": "未登录或登录已过期"}), 401
        return f(*args, **kwargs)
    return decorated_function

# ==================== 认证相关接口 ====================

@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    cfg = db.config
    if username == cfg.get("admin_user") and password == cfg.get("admin_pass"):
        session["logged_in"] = True
        session["user"] = username
        return jsonify({"code": 0, "msg": "登录成功", "user": username})
    return jsonify({"code": 400, "msg": "用户名或密码错误"}), 400

@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"code": 0, "msg": "已退出登录"})

@app.route("/api/auth_status", methods=["GET"])
def auth_status():
    logged_in = bool(session.get("logged_in"))
    return jsonify({
        "logged_in": logged_in,
        "user": session.get("user") if logged_in else None
    })

# ==================== 仪表盘与状态接口 ====================

@app.route("/api/status", methods=["GET"])
@login_required
def get_status():
    is_login = wechat_client.is_login()
    self_info = wechat_client.get_self_info() if is_login else {}
    stats = rule_engine.get_stats()
    rules = db.get_rules()

    return jsonify({
        "code": 0,
        "data": {
            "wechat_online": is_login,
            "self_info": self_info,
            "stats": stats,
            "total_rules": len(rules),
            "active_rules": len([r for r in rules if r.get("enabled", True)])
        }
    })

@app.route("/api/contacts", methods=["GET"])
@login_required
def get_contacts():
    contacts = wechat_client.get_contacts()
    return jsonify({"code": 0, "data": contacts})

# ==================== 规则 CRUD 接口 ====================

@app.route("/api/rules", methods=["GET"])
@login_required
def list_rules():
    return jsonify({"code": 0, "data": db.get_rules()})

@app.route("/api/rules", methods=["POST"])
@login_required
def create_rule():
    data = request.get_json() or {}
    name = data.get("name", "").strip()
    pattern = data.get("pattern", "").strip()
    if not name or not pattern:
        return jsonify({"code": 400, "msg": "规则名称和匹配表达式不能为空"}), 400

    new_rule = db.add_rule(data)
    return jsonify({"code": 0, "msg": "规则创建成功", "data": new_rule})

@app.route("/api/rules/<rule_id>", methods=["PUT"])
@login_required
def update_rule(rule_id):
    data = request.get_json() or {}
    updated = db.update_rule(rule_id, data)
    if not updated:
        return jsonify({"code": 404, "msg": "规则不存在"}), 404
    return jsonify({"code": 0, "msg": "规则更新成功", "data": updated})

@app.route("/api/rules/<rule_id>", methods=["DELETE"])
@login_required
def delete_rule(rule_id):
    db.delete_rule(rule_id)
    return jsonify({"code": 0, "msg": "规则删除成功"})

@app.route("/api/rules/<rule_id>/toggle", methods=["POST"])
@login_required
def toggle_rule(rule_id):
    data = request.get_json() or {}
    rule = db.toggle_rule(rule_id, data.get("enabled"))
    if not rule:
        return jsonify({"code": 404, "msg": "规则不存在"}), 404
    return jsonify({"code": 0, "msg": "状态已切换", "data": rule})

@app.route("/api/rules/test", methods=["POST"])
@login_required
def test_rule():
    data = request.get_json() or {}
    sample_text = data.get("sample_text", "").strip()
    sample_group = data.get("sample_group", "运维告警群").strip()
    sample_sender = data.get("sample_sender", "监控小助手").strip()
    rule_data = data.get("rule", {})

    res = rule_engine.test_rule(rule_data, sample_text, sample_group, sample_sender)
    return jsonify({"code": 0, "data": res})

# ==================== 转发日志接口 ====================

@app.route("/api/logs", methods=["GET"])
@login_required
def get_logs():
    limit = int(request.args.get("limit", 100))
    logs = db.get_logs(limit)
    return jsonify({"code": 0, "data": logs})

@app.route("/api/logs", methods=["DELETE"])
@login_required
def clear_logs():
    db.clear_logs()
    return jsonify({"code": 0, "msg": "日志已清空"})

# ==================== 手动发送微信消息接口 ====================

@app.route("/api/send_message", methods=["POST"])
@app.route("/api/send_test", methods=["POST"])
@login_required
def send_message():
    data = request.get_json() or {}
    wxid = data.get("wxid", "").strip()
    msg = data.get("msg", "").strip()
    if not wxid or not msg:
        return jsonify({"code": 400, "msg": "接收人与消息内容不能为空"}), 400

    res = wechat_client.send_text(wxid, msg)
    return jsonify({"code": 0, "msg": "消息发送请求已提交", "data": res})

# ==================== 系统设置接口 ====================

@app.route("/api/settings", methods=["GET"])
@login_required
def get_settings():
    cfg = dict(db.config)
    # 隐藏敏感密码明文，只显示是否已设置
    cfg["has_pass"] = bool(cfg.get("admin_pass"))
    cfg.pop("admin_pass", None)
    return jsonify({"code": 0, "data": cfg})

@app.route("/api/settings", methods=["POST"])
@login_required
def update_settings():
    data = request.get_json() or {}
    update_data = {}
    if "admin_user" in data and data["admin_user"].strip():
        update_data["admin_user"] = data["admin_user"].strip()
    if "admin_pass" in data and data["admin_pass"].strip():
        update_data["admin_pass"] = data["admin_pass"].strip()
    if "default_template" in data:
        update_data["default_template"] = data["default_template"]

    db.save_config(update_data)
    return jsonify({"code": 0, "msg": "设置更新成功"})

# ==================== 前端主页入口 ====================

@app.route("/")
def index():
    return render_template("index.html")

if __name__ == "__main__":
    # 启动后台消息监听与转发引擎
    rule_engine.start()

    port = db.config.get("web_port", 8000)
    print(f"[WebAdmin] 微信机器人管理平台已启动: http://0.0.0.0:{port}", flush=True)
    app.run(host="0.0.0.0", port=port, debug=False)
