import os
import json
import uuid
import threading
from datetime import datetime

DATA_DIR = os.environ.get("DATA_DIR", "/data")
if not os.path.exists(DATA_DIR):
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
    except Exception:
        DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
        os.makedirs(DATA_DIR, exist_ok=True)

RULES_FILE = os.path.join(DATA_DIR, "forward_rules.json")
LOGS_FILE = os.path.join(DATA_DIR, "forward_logs.json")
CONFIG_FILE = os.path.join(DATA_DIR, "admin_config.json")

class Storage:
    def __init__(self):
        self._lock = threading.Lock()
        self.rules = self._load_rules()
        self.logs = self._load_logs()
        self.config = self._load_config()

    def _load_config(self):
        default_user = os.environ.get("ADMIN_USER", "admin")
        default_pass = os.environ.get("ADMIN_PASS", "admin123")
        env_hb = os.environ.get("ENABLE_HEARTBEAT", "false").lower() in ("true", "1", "yes")
        default_config = {
            "admin_user": default_user,
            "admin_pass": default_pass,
            "web_port": int(os.environ.get("WEB_PORT", 8000)),
            "enable_heartbeat": env_hb,
            "default_template": "【群消息提醒】\n📌 来源群：{group_name}\n👤 发送人：{sender_name}\n⏰ 时间：{time}\n💬 内容：\n{content}"
        }
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    default_config.update(cfg)
            except Exception:
                pass
        return default_config

    def save_config(self, new_config):
        with self._lock:
            self.config.update(new_config)
            try:
                with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                    json.dump(self.config, f, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"[Storage] 保存配置失败: {e}", flush=True)

    def _load_rules(self):
        if os.path.exists(RULES_FILE):
            try:
                with open(RULES_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[Storage] 读取规则文件失败: {e}", flush=True)
        # 默认内置一个示例规则供参考
        sample_rules = [
            {
                "id": "sample_rule_1",
                "name": "紧急告警与BUG监控示例",
                "enabled": True,
                "group_mode": "all",
                "groups": [],
                "match_type": "regex",
                "pattern": "(?i)(告警|故障|紧急|宕机|崩溃|BUG|严重)",
                "targets": [
                    {"wxid": "filehelper", "name": "文件传输助手"}
                ],
                "template": "【群消息监控提醒】\n📌 来源群：{group_name}\n👤 发言人：{sender_name}\n⏰ 接收时间：{time}\n💬 原始内容：\n{content}",
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        ]
        return sample_rules

    def save_rules(self):
        try:
            with open(RULES_FILE, "w", encoding="utf-8") as f:
                json.dump(self.rules, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[Storage] 保存规则文件失败: {e}", flush=True)

    def get_rules(self):
        with self._lock:
            return list(self.rules)

    def add_rule(self, rule_data):
        with self._lock:
            rule_id = "rule_" + uuid.uuid4().hex[:8]
            rule_data["id"] = rule_id
            rule_data["created_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if "enabled" not in rule_data:
                rule_data["enabled"] = True
            self.rules.append(rule_data)
            self.save_rules()
            return rule_data

    def update_rule(self, rule_id, new_data):
        with self._lock:
            for i, r in enumerate(self.rules):
                if r["id"] == rule_id:
                    new_data["id"] = rule_id
                    new_data["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    self.rules[i].update(new_data)
                    self.save_rules()
                    return self.rules[i]
            return None

    def delete_rule(self, rule_id):
        with self._lock:
            self.rules = [r for r in self.rules if r["id"] != rule_id]
            self.save_rules()
            return True

    def toggle_rule(self, rule_id, enabled=None):
        with self._lock:
            for r in self.rules:
                if r["id"] == rule_id:
                    if enabled is None:
                        r["enabled"] = not r.get("enabled", True)
                    else:
                        r["enabled"] = bool(enabled)
                    self.save_rules()
                    return r
            return None

    def _load_logs(self):
        if os.path.exists(LOGS_FILE):
            try:
                with open(LOGS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    def add_log(self, log_item):
        with self._lock:
            log_item["id"] = "log_" + uuid.uuid4().hex[:8]
            if "time" not in log_item:
                log_item["time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # 保持最新的 500 条记录
            self.logs.insert(0, log_item)
            if len(self.logs) > 500:
                self.logs = self.logs[:500]
            try:
                with open(LOGS_FILE, "w", encoding="utf-8") as f:
                    json.dump(self.logs, f, ensure_ascii=False, indent=2)
            except Exception:
                pass

    def get_logs(self, limit=100):
        with self._lock:
            return self.logs[:limit]

    def clear_logs(self):
        with self._lock:
            self.logs = []
            try:
                with open(LOGS_FILE, "w", encoding="utf-8") as f:
                    json.dump([], f)
            except Exception:
                pass

db = Storage()
