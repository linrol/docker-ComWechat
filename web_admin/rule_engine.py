import re
import json
import time
import socketserver
import threading
from datetime import datetime

from storage import db
from wechat_client import wechat_client

class MessageHandler(socketserver.BaseRequestHandler):
    def handle(self):
        conn = self.request
        buffer = b""
        while True:
            try:
                data = conn.recv(2048)
                if not data:
                    break
                buffer += data
                # 消息以换行符分隔或完整包
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    line_str = line.decode("utf-8", errors="ignore").strip()
                    if line_str:
                        try:
                            msg_json = json.loads(line_str)
                            rule_engine.process_message(msg_json)
                        except Exception as e:
                            pass
                conn.sendall(b"200 OK\n")
            except Exception:
                break
        conn.close()

class RuleEngine:
    def __init__(self, hook_port=10808):
        self.hook_port = hook_port
        self.server = None
        self._running = False
        self._stats = {
            "total_received": 0,
            "total_matched": 0,
            "total_forwarded": 0,
            "start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    def start(self):
        if self._running:
            return
        self._running = True
        t = threading.Thread(target=self._run_server, daemon=True)
        t.start()
        # 后台健康检查与自动重连 Hook
        kh = threading.Thread(target=self._keep_hook_alive, daemon=True)
        kh.start()

    def _run_server(self):
        try:
            # 允许端口复用
            socketserver.TCPServer.allow_reuse_address = True
            self.server = socketserver.ThreadingTCPServer(("127.0.0.1", self.hook_port), MessageHandler)
            print(f"[RuleEngine] 消息监听服务已就绪，正在监听 127.0.0.1:{self.hook_port}", flush=True)
            self.server.serve_forever()
        except Exception as e:
            print(f"[RuleEngine] 消息监听启动异常: {e}", flush=True)

    def _keep_hook_alive(self):
        time.sleep(3)
        while self._running:
            try:
                if wechat_client.is_login():
                    wechat_client.start_hook(self.hook_port)
            except Exception:
                pass
            time.sleep(15)

    def get_stats(self):
        return dict(self._stats)

    def test_rule(self, rule_data, sample_text, sample_group="技术支持群", sample_sender="张三"):
        """用于在前端页面进行规则模拟测试"""
        matched, match_text = self._match_pattern(rule_data, sample_text)
        preview_text = ""
        if matched:
            ctx = {
                "group_name": sample_group,
                "group_id": "test_group@chatroom",
                "sender_name": sample_sender,
                "sender_id": "wxid_sample_sender",
                "content": sample_text,
                "match_text": match_text,
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "rule_name": rule_data.get("name", "未命名规则")
            }
            preview_text = self._render_template(rule_data.get("template", ""), ctx)
        return {
            "matched": matched,
            "match_text": match_text,
            "preview_text": preview_text
        }

    def _match_pattern(self, rule, content):
        match_type = rule.get("match_type", "regex")
        pattern = rule.get("pattern", "")
        if not pattern:
            return False, ""

        if match_type == "exact":
            if content.strip() == pattern.strip():
                return True, content
            return False, ""

        elif match_type == "keyword":
            # 支持以逗号或竖线分隔的多关键词
            keywords = [k.strip() for k in re.split(r"[,|，]", pattern) if k.strip()]
            for kw in keywords:
                if kw in content:
                    return True, kw
            return False, ""

        elif match_type == "regex":
            try:
                flags = re.IGNORECASE if rule.get("case_insensitive", True) else 0
                m = re.search(pattern, content, flags)
                if m:
                    return True, m.group(0)
            except Exception as e:
                print(f"[RuleEngine] 正则匹配错误 ({pattern}): {e}", flush=True)
            return False, ""

        return False, ""

    def _render_template(self, tpl, ctx):
        if not tpl:
            tpl = "【群消息提醒】\n📌 来源群：{group_name}\n👤 发送人：{sender_name}\n⏰ 时间：{time}\n💬 内容：\n{content}"
        rendered = tpl
        for k, v in ctx.items():
            rendered = rendered.replace(f"{{{k}}}", str(v))
        return rendered

    def process_message(self, msg):
        self._stats["total_received"] += 1
        # 消息格式适配：
        # ComWeChatRobot 常用结构: {"from_group": "...", "from_user": "...", "content": "...", "msg_type": 1}
        # 或 {"data": {"from_group": ...}}
        data = msg.get("data", msg)
        msg_type = data.get("msg_type", 1)

        # 仅处理文本消息 (msg_type == 1)
        if msg_type != 1:
            return

        content = data.get("content", "")
        if not content:
            return

        # 判断是否为群消息
        group_id = data.get("from_group") or data.get("chatroom_id") or ""
        # 有些版本私聊时 from_group 为空，群聊时为 xxxx@chatroom
        from_user = data.get("from_user") or data.get("sender") or ""

        if not group_id and from_user.endswith("@chatroom"):
            group_id = from_user

        if not group_id:
            # 不是群消息，跳过
            return

        sender_id = data.get("from_user") if data.get("from_group") else ""
        if not sender_id:
            # 如果群消息直接拼接在 content 中 (形如: "wxid_xxx:\n消息内容")
            if ":\n" in content:
                parts = content.split(":\n", 1)
                sender_id = parts[0]
                content = parts[1]

        group_name = wechat_client.resolve_name(group_id)
        sender_name = wechat_client.resolve_name(sender_id, chatroom_id=group_id) if sender_id else "群友"

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 读取当前生效的规则
        rules = db.get_rules()
        for rule in rules:
            if not rule.get("enabled", True):
                continue

            # 1. 过滤群聊范围
            group_mode = rule.get("group_mode", "all")
            if group_mode == "specific":
                target_groups = rule.get("groups", [])
                target_ids = [g["id"] if isinstance(g, dict) else g for g in target_groups]
                if group_id not in target_ids:
                    continue

            # 2. 匹配消息规则
            matched, match_text = self._match_pattern(rule, content)
            if not matched:
                continue

            self._stats["total_matched"] += 1

            # 3. 渲染转发文本
            ctx = {
                "group_name": group_name,
                "group_id": group_id,
                "sender_name": sender_name,
                "sender_id": sender_id,
                "content": content,
                "match_text": match_text,
                "time": now_str,
                "rule_name": rule.get("name", "未命名规则")
            }
            forward_text = self._render_template(rule.get("template", ""), ctx)

            # 4. 转发给指定目标人
            targets = rule.get("targets", [])
            forward_results = []
            for t in targets:
                target_wxid = t["wxid"] if isinstance(t, dict) else t
                target_name = t.get("name", target_wxid) if isinstance(t, dict) else target_wxid
                try:
                    res = wechat_client.send_text(target_wxid, forward_text)
                    success = res.get("code") == 0 or res.get("is_send") == 1 or res.get("result") == "OK"
                    forward_results.append({
                        "target": target_name,
                        "wxid": target_wxid,
                        "status": "success" if success else "failed"
                    })
                    if success:
                        self._stats["total_forwarded"] += 1
                except Exception as e:
                    forward_results.append({
                        "target": target_name,
                        "wxid": target_wxid,
                        "status": f"error: {e}"
                    })

            # 5. 记录命中转发日志
            log_entry = {
                "rule_id": rule.get("id"),
                "rule_name": rule.get("name"),
                "group_name": group_name,
                "group_id": group_id,
                "sender_name": sender_name,
                "sender_id": sender_id,
                "content": content,
                "match_text": match_text,
                "forward_content": forward_text,
                "targets": forward_results,
                "time": now_str,
                "status": "success" if any(r["status"] == "success" for r in forward_results) else "failed"
            }
            db.add_log(log_entry)
            print(f"[RuleEngine] 命中规则【{rule.get('name')}】并已转发: {group_name} -> {len(targets)}人", flush=True)

rule_engine = RuleEngine()
