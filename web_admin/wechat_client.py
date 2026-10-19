import json
import requests
import time

class WeChatClient:
    def __init__(self, host="127.0.0.1", port=18888):
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}/api/"
        self._name_cache = {}  # wxid -> display_name
        self._cache_time = 0

    def call_api(self, api_type, data=None):
        url = f"{self.base_url}?type={api_type}"
        payload = data if data is not None else {}
        try:
            resp = requests.post(url, data=json.dumps(payload), timeout=8)
            return resp.json()
        except Exception as e:
            return {"code": -1, "msg": str(e), "is_login": 0}

    def is_login(self):
        res = self.call_api(0)
        return res.get("is_login") == 1

    def get_self_info(self):
        res = self.call_api(1)
        return res.get("data", res)

    def send_text(self, wxid, text):
        data = {"wxid": wxid, "msg": text}
        return self.call_api(2, data)

    def start_hook(self, socket_port=10808):
        data = {"port": socket_port}
        return self.call_api(9, data)

    def stop_hook(self):
        return self.call_api(10, {})

    @staticmethod
    def _extract_field(item, *keys):
        """大小写不敏感提取字段值，兼顾 dict 结构"""
        if not isinstance(item, dict):
            return ""
        for k in keys:
            if k in item and item[k]:
                return str(item[k]).strip()
        lower_map = {k.lower(): v for k, v in item.items() if v}
        for k in keys:
            lk = k.lower()
            if lk in lower_map and lower_map[lk]:
                return str(lower_map[lk]).strip()
        return ""

    def get_contacts_from_db(self):
        """从微信本地数据库 MicroMsg.db 读取全量群聊与联系人信息"""
        db_map = {}
        try:
            dbs = self.call_api(32)
            handles = dbs.get("data", [])
            db_handle = None
            for item in handles:
                if isinstance(item, dict) and item.get("db_name") == "MicroMsg.db":
                    db_handle = item.get("handle")
                    break

            if db_handle:
                # 1. 查询 Contact 联系人与已命名群聊
                sql = "SELECT UserName, NickName, Remark, Alias FROM Contact;"
                query_res = self.call_api(34, {"db_handle": db_handle, "sql": sql})
                data_rows = query_res.get("data", [])

                for row in data_rows:
                    user_name, nick, remark, alias = "", "", "", ""
                    if isinstance(row, dict):
                        user_name = self._extract_field(row, "UserName", "userName", "wxid")
                        nick = self._extract_field(row, "NickName", "nickName", "nickname")
                        remark = self._extract_field(row, "Remark", "remark")
                        alias = self._extract_field(row, "Alias", "alias")
                    elif isinstance(row, (list, tuple)) and len(row) >= 4:
                        # 兼容数据库返回二维数组的情况: [UserName, NickName, Remark, Alias]
                        user_name = str(row[0]).strip() if row[0] else ""
                        nick = str(row[1]).strip() if row[1] else ""
                        remark = str(row[2]).strip() if row[2] else ""
                        alias = str(row[3]).strip() if row[3] else ""

                    if user_name:
                        db_map[user_name] = {
                            "nickname": nick,
                            "remark": remark,
                            "alias": alias
                        }

                print(f"[WeChatClient] 成功从 MicroMsg.db 加载 {len(db_map)} 个联系人/群聊信息", flush=True)
            else:
                print(f"[WeChatClient] 未找到 MicroMsg.db 数据库句柄，返回值: {dbs}", flush=True)
        except Exception as e:
            print(f"[WeChatClient] 从本地数据库读取联系人异常: {e}", flush=True)
        return db_map

    def get_chatroom_member_names(self, chatroom_id, max_count=3):
        """对未命名群聊，获取其前几位成员昵称以生成友好群名"""
        try:
            res = self.call_api(25, {"chatroom_id": chatroom_id})
            members_raw = res.get("data") or res.get("member_list") or []
            member_wxids = []
            if isinstance(members_raw, list):
                for m in members_raw:
                    wid = m if isinstance(m, str) else (m.get("wxid") if isinstance(m, dict) else "")
                    if wid:
                        member_wxids.append(wid)
            elif isinstance(members_raw, str):
                member_wxids = [x.strip() for x in members_raw.split("^G") if x.strip()] or members_raw.split(",")

            names = []
            for wid in member_wxids[:max_count]:
                nick = self.resolve_name(wid, chatroom_id=chatroom_id)
                if nick and nick != wid:
                    names.append(nick)
            if names:
                return "、".join(names)
        except Exception:
            pass
        return ""

    def get_contacts(self):
        # 1. 优先尝试从本地数据库读取全量精准群名与备注
        db_map = self.get_contacts_from_db()

        # 2. 调用 API 15 获取当前通讯录列表
        res = self.call_api(15)
        raw_list = res.get("data", [])

        merged_ids = set()
        items = []

        if isinstance(raw_list, list) and raw_list:
            for it in raw_list:
                wid = self._extract_field(it, "wxid", "UserName", "wx_id")
                if wid:
                    items.append(it)
                    merged_ids.add(wid)

        # 把数据库中存在但 API 15 未列出的联系人补充进来
        for wid, info in db_map.items():
            if wid not in merged_ids and not wid.startswith("gh_"):
                items.append({
                    "wxid": wid,
                    "nickname": info.get("nickname", ""),
                    "remark": info.get("remark", ""),
                    "alias": info.get("alias", "")
                })
                merged_ids.add(wid)

        friends = []
        chatrooms = []
        now = time.time()

        for item in items:
            wxid = self._extract_field(item, "wxid", "UserName", "wx_id", "user_name")
            if not wxid:
                continue

            db_info = db_map.get(wxid, {})
            nickname = self._extract_field(item, "nickname", "NickName", "nick_name") or db_info.get("nickname", "")
            remark = self._extract_field(item, "remark", "Remark", "remark_name") or db_info.get("remark", "")
            alias = self._extract_field(item, "alias", "Alias", "custom_account") or db_info.get("alias", "")

            is_chatroom = wxid.endswith("@chatroom")

            # 3. 如果昵称仍为空，尝试通过 API 18 从内存缓存精准点查
            if not nickname and not remark:
                try:
                    cache_res = self.call_api(18, {"wxid": wxid})
                    c_data = cache_res.get("data", {})
                    if isinstance(c_data, dict):
                        nickname = self._extract_field(c_data, "NickName", "nickname") or nickname
                        remark = self._extract_field(c_data, "Remark", "remark") or remark
                        alias = self._extract_field(c_data, "Alias", "alias") or alias
                except Exception:
                    pass

            # 4. 计算友好显示名称
            if is_chatroom:
                if remark:
                    display_name = remark
                elif nickname:
                    display_name = nickname
                else:
                    # 尝试用群成员名称拼装成如: "群聊 (张三、李四)"
                    member_summary = self.get_chatroom_member_names(wxid)
                    if member_summary:
                        display_name = f"群聊 ({member_summary})"
                    else:
                        display_name = f"群聊 ({wxid.split('@')[0]})"
            else:
                if remark and nickname:
                    display_name = f"{remark} ({nickname})"
                elif remark:
                    display_name = remark
                elif nickname:
                    display_name = nickname
                elif alias:
                    display_name = alias
                else:
                    display_name = wxid

            # 刷新全局名称缓存，供规则引擎与模板解析使用
            self._name_cache[wxid] = display_name

            contact_obj = {
                "wxid": wxid,
                "nickname": nickname,
                "remark": remark,
                "alias": alias,
                "display_name": display_name
            }

            if is_chatroom:
                chatrooms.append(contact_obj)
            else:
                # 排除系统内置号与公众号
                if not wxid.startswith("gh_") and wxid not in ["medianote", "floatbottle", "fmessage", "qmessage"]:
                    friends.append(contact_obj)

        self._cache_time = now
        return {"friends": friends, "chatrooms": chatrooms}

    def resolve_name(self, wxid, chatroom_id=None):
        if not wxid:
            return ""
        if wxid == "filehelper":
            return "文件传输助手"
        if wxid in self._name_cache and not self._name_cache[wxid].startswith("wxid_"):
            return self._name_cache[wxid]

        # 尝试查询群成员昵称 (API 26)
        if chatroom_id:
            try:
                res = self.call_api(26, {"chatroom_id": chatroom_id, "wxid": wxid})
                nick = res.get("nickname") or res.get("data")
                if nick and str(nick).strip():
                    name_str = str(nick).strip()
                    self._name_cache[wxid] = name_str
                    return name_str
            except Exception:
                pass

        # 尝试通过 API 18 从内存缓存查
        try:
            res = self.call_api(18, {"wxid": wxid})
            data = res.get("data", {})
            if isinstance(data, dict):
                nick = self._extract_field(data, "NickName", "nickname", "Remark", "remark")
                if nick:
                    self._name_cache[wxid] = nick
                    return nick
        except Exception:
            pass

        return wxid

wechat_client = WeChatClient()
