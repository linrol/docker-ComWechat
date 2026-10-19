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
                data = conn.recv(4096)
                if not data:
                    break
                buffer += data

                # 兼容以换行符分隔的多包，或者单包
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    line_str = line.decode("utf-8", errors="ignore").strip()
                    if line_str:
                        try:
                            msg_json = json.loads(line_str)
                            rule_engine.process_message(msg_json)
                        except Exception as e:
                            print(f"[RuleEngine] 解析消息 JSON 异常: {e}, 原始内容: {line_str[:200]}", flush=True)

                # 如果没有换行符且 buffer 可以直接解析为 JSON
                if buffer and (buffer.startswith(b"{") and buffer.endswith(b"}")):
                    try:
                        line_str = buffer.decode("utf-8", errors="ignore").strip()
                        msg_json = json.loads(line_str)
                        buffer = b""
                        rule_engine.process_message(msg_json)
                    except Exception:
                        pass

                conn.sendall(b"200 OK")
            except Exception as e:
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
        # 后台健康检查与自动启动 Hook
        kh = threading.Thread(target=self._keep_hook_alive, daemon=True)
        kh.start()

    def _run_server(self):
        try:
            socketserver.TCPServer.allow_reuse_address = True
            self.server = socketserver.ThreadingTCPServer(("127.0.0.1", self.hook_port), MessageHandler)
            print(f"[RuleEngine] 消息监听服务已就绪，正在监听 127.0.0.1:{self.hook_port}", flush=True)
            self.server.serve_forever()
        except Exception as e:
            print(f"[RuleEngine] 消息监听启动异常: {e}", flush=True)

    def _keep_hook_alive(self):
        time.sleep(2)
        while self._running:
            try:
                if wechat_client.is_login():
                    res = wechat_client.start_hook(self.hook_port)
                    # print(f"[RuleEngine] 触发 Hook 注册 (127.0.0.1:{self.hook_port}) => {res}", flush=True)
            except Exception:
                pass
            time.sleep(10)

    def get_stats(self):
        return dict(self._stats)

    def test_rule(self, rule_data, sample_text, sample_group="技术支持群", sample_sender="张三"):
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
            # 支持以逗号或竖线分隔的多关键词（如: 免费,送,保洁,煮饭）
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
        print(f"[RuleEngine] 收到原始 Hook 消息: {json.dumps(msg, ensure_ascii=False)}", flush=True)

        data = msg.get("data") if isinstance(msg.get("data"), dict) else msg

        # 1. 提取消息类型
        msg_type = data.get("type") or data.get("msg_type") or 1
        # 如果嵌套在 msg 字典中
        if isinstance(data.get("msg"), dict):
            inner_msg = data.get("msg")
            msg_type = inner_msg.get("type", msg_type)

        # 仅处理文本消息 (type == 1)
        if msg_type != 1:
            return

        # 2. 提取消息文本内容（兼容 content, msg, message）
        content = ""
        raw_msg_field = data.get("msg") or data.get("content") or data.get("message") or ""
        if isinstance(raw_msg_field, dict):
            content = raw_msg_field.get("content") or raw_msg_field.get("msg") or ""
        elif isinstance(raw_msg_field, str):
            content = raw_msg_field

        if not content:
            return

        # 3. 智能提取群聊 ID（在所有字段中寻找以 @chatroom 结尾的值）
        group_id = ""
        potential_keys = ["receiver", "roomid", "from_group", "chatroom_id", "sender", "wxid", "to_user", "from_user"]
        for k in potential_keys:
            val = data.get(k)
            if isinstance(val, str) and val.endswith("@chatroom"):
                group_id = val
                break

        # 深入内层字典查找
        if not group_id and isinstance(data.get("msg"), dict):
            for k in potential_keys:
                val = data["msg"].get(k)
                if isinstance(val, str) and val.endswith("@chatroom"):
                    group_id = val
                    break

        # 全量遍历查找 @chatroom
        if not group_id:
            for v in data.values():
                if isinstance(v, str) and v.endswith("@chatroom"):
                    group_id = v
                    break

        if not group_id:
            # 非群消息，跳过
            return

        # 4. 提取发信人 ID
        sender_id = ""
        # 常见群消息格式形如: "wxid_xxx:\n消息正文"
        if ":\n" in content:
            parts = content.split(":\n", 1)
            candidate_id = parts[0].strip()
            if candidate_id.startswith("wxid_") or "@" not in candidate_id:
                sender_id = candidate_id
                content = parts[1]

        if not sender_id:
            # 从 sender / from_user 提取非群聊 ID 的发信人
            for k in ["sender", "from_user", "wxid", "from_wxid"]:
                val = data.get(k)
                if isinstance(val, str) and not val.endswith("@chatroom") and val:
                    sender_id = val
                    break

        group_name = wechat_client.resolve_name(group_id)
        sender_name = wechat_client.resolve_name(sender_id, chatroom_id=group_id) if sender_id else "群成员"

        print(f"[RuleEngine] 群消息识别成功 -> 群: {group_name} ({group_id}), 发言人: {sender_name} ({sender_id}), 内容: {content}", flush=True)

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 5. 遍历匹配规则并执行转发
        rules = db.get_rules()
        for rule in rules:
            if not rule.get("enabled", True):
                continue

            # 过滤指定群聊
            group_mode = rule.get("group_mode", "all")
            if group_mode == "specific":
                target_groups = rule.get("groups", [])
                target_ids = [g["id"] if isinstance(g, dict) else g for g in target_groups]
                if group_id not in target_ids:
                    continue

            # 匹配关键词或正则
            matched, match_text = self._match_pattern(rule, content)
            if not matched:
                continue

            self._stats["total_matched"] += 1
            print(f"[RuleEngine] 🎯 命中规则 [{rule.get('name')}] (特征词: {match_text})", flush=True)

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

            # 执行转发
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
                        print(f"[RuleEngine] 🚀 成功转发给: {target_name} ({target_wxid})", flush=True)
                    else:
                        print(f"[RuleEngine] ❌ 转发失败: {res}", flush=True)
                except Exception as ex:
                    print(f"[RuleEngine] 转发异常: {ex}", flush=True)
                    forward_results.append({
                        "target": target_name,
                        "wxid": target_wxid,
                        "status": "failed"
                    })

            # 写入持久化日志
            overall_status = "success" if any(r["status"] == "success" for r in forward_results) else "failed"
            db.add_log({
                "rule_id": rule.get("id"),
                "rule_name": rule.get("name"),
                "group_name": group_name,
                "group_id": group_id,
                "sender_name": sender_name,
                "sender_id": sender_id,
                "match_text": match_text,
                "forward_content": forward_text,
                "targets": forward_results,
                "status": overall_status,
                "time": now_str
            })

rule_engine = RuleEngine()
