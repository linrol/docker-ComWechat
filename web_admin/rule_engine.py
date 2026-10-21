import re
import json
import time
import random
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
        """
        后台健康检查与主动心跳保活引擎：
        1. 状态变迁监听：精准捕获登录/掉线事件并记录毫秒级时间戳日志
        2. 主动探活心跳：定时给 filehelper 发送静默探针，打破凌晨公网 NAT 超时与连接挂死
        3. 微信版本防封伪装：定期复查 API 35 维护最新版本欺骗
        4. Hook 状态维持：确保崩溃或网络抖动后自动重新注入 Hook
        """
        time.sleep(2)
        last_online = None
        last_heartbeat_time = 0
        last_version_spoof_time = 0
        heartbeat_interval = random.randint(300, 600)  # 随机 5~10 分钟，拟真化避开固定周期风控

        while self._running:
            try:
                now_ts = time.time()
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                online = wechat_client.is_login()

                # 1. 登录状态变迁监听与精确警报
                if last_online is not None and online != last_online:
                    if not online:
                        print(f"[RuleEngine] 🚨 [CRITICAL] [{now_str}] 微信检测到已掉线！(内存状态由 在线 变为 离线)", flush=True)
                    else:
                        print(f"[RuleEngine] 🟢 [INFO] [{now_str}] 微信已检测到重新登录上线！", flush=True)
                last_online = online

                if online:
                    # 2. 定期刷新 Hook 挂载
                    wechat_client.start_hook(self.hook_port)

                    # 3. 维护版本号防封伪装 (每小时检查一次)
                    if now_ts - last_version_spoof_time > 3600:
                        try:
                            # 官方 API 35: 修改/维护伪装版本号
                            wechat_client.call_api(35, {"version": "3.9.10.19"})
                            last_version_spoof_time = now_ts
                        except Exception:
                            pass

                    # 4. 主动探活心跳 (打破凌晨 NAT 超时假死，随机 5~10 分钟发送一次)
                    if now_ts - last_heartbeat_time > heartbeat_interval:
                        try:
                            # 向文件传输助手发送静默心跳，强制触发物理网卡向腾讯服务器的数据包往返
                            res = wechat_client.send_text("filehelper", "[Heartbeat] keep-alive")
                            if res.get("result") == "OK" or res.get("msg") == 1:
                                # print(f"[RuleEngine] 💓 [{now_str}] 主动心跳探针发送成功，NAT 映射已刷新，下次间隔: {heartbeat_interval}s", flush=True)
                                last_heartbeat_time = now_ts
                                heartbeat_interval = random.randint(300, 600)  # 重新随机生成下次间隔 (5~10 分钟)
                            else:
                                print(f"[RuleEngine] ⚠️ [{now_str}] 主动心跳发送响应异常: {res}", flush=True)
                        except Exception as e_hb:
                            print(f"[RuleEngine] ⚠️ [{now_str}] 主动心跳异常: {e_hb}", flush=True)
                else:
                    # 处于离线状态时每 10 秒提示一次
                    # print(f"[RuleEngine] 等待微信登录中...", flush=True)
                    pass

            except Exception as e:
                print(f"[RuleEngine] 保活轮询异常: {e}", flush=True)

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

        # 1. 过滤自己发出的消息，避免机器人转发时触发规则导致死循环刷屏
        is_send_msg = data.get("isSendMsg") if "isSendMsg" in data else msg.get("isSendMsg")
        if is_send_msg == 1:
            return

        # 2. 提取消息类型，仅处理文本消息 (type == 1)
        msg_type = data.get("type") or data.get("msg_type") or 1
        if isinstance(data.get("msg"), dict):
            inner_msg = data.get("msg")
            msg_type = inner_msg.get("type", msg_type)

        if msg_type != 1:
            return

        # 3. 提取消息正文（官方优先字段为 message / msg）
        content = ""
        raw_msg_field = data.get("message") or data.get("msg") or data.get("content") or ""
        if isinstance(raw_msg_field, dict):
            content = raw_msg_field.get("content") or raw_msg_field.get("msg") or raw_msg_field.get("message") or ""
        elif isinstance(raw_msg_field, str):
            content = raw_msg_field.strip()

        if not content:
            return

        # 4. 严格按照 ComWeChatRobot 官方规范识别群聊与发言人:
        # 官方协议中：群消息时 sender 为群ID (xxx@chatroom)，wxid 为群内真实发言人 (wxid_xxx)
        raw_sender = str(data.get("sender") or "").strip()
        raw_wxid = str(data.get("wxid") or "").strip()

        group_id = ""
        sender_id = ""

        if raw_sender.endswith("@chatroom"):
            group_id = raw_sender
            sender_id = raw_wxid if not raw_wxid.endswith("@chatroom") else ""
        elif "@chatroom" in raw_sender:
            group_id = raw_sender
            sender_id = raw_wxid
        else:
            # 容错：检查备用字段
            for k in ["roomid", "receiver", "from_group", "chatroom_id"]:
                val = str(data.get(k) or "").strip()
                if val.endswith("@chatroom"):
                    group_id = val
                    sender_id = raw_wxid or raw_sender
                    break

        if not group_id:
            # 非群消息，跳过
            return

        if not sender_id or sender_id.endswith("@chatroom"):
            sender_id = raw_wxid if (raw_wxid and not raw_wxid.endswith("@chatroom")) else "unknown"

        group_name = wechat_client.resolve_name(group_id)
        sender_name = wechat_client.resolve_name(sender_id, chatroom_id=group_id) if sender_id != "unknown" else "群成员"

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

            # 执行多目标批量转发
            targets = rule.get("targets", [])
            forward_results = []
            for idx, t in enumerate(targets):
                target_wxid = t["wxid"] if isinstance(t, dict) else t
                target_name = t.get("name", target_wxid) if isinstance(t, dict) else target_wxid
                try:
                    res = wechat_client.send_text(target_wxid, forward_text)
                    success = res.get("result") == "OK" or res.get("msg") == 1 or res.get("code") == 0 or res.get("is_send") == 1
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

                # 多目标连续发送时加入 0.3 秒间隔，防止底层发送调用过频丢包
                if idx < len(targets) - 1:
                    time.sleep(0.3)

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
