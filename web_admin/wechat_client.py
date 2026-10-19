import json
import requests
import time

class WeChatClient:
    def __init__(self, host="127.0.0.1", port=18888):
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}/api/"
        self._name_cache = {}  # wxid -> name
        self._cache_time = 0

    def call_api(self, api_type, data=None):
        url = f"{self.base_url}?type={api_type}"
        try:
            if data is not None:
                resp = requests.post(url, data=json.dumps(data), timeout=5)
            else:
                resp = requests.get(url, timeout=5)
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
        """大小写不敏感提取字段值"""
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
                if item.get("db_name") == "MicroMsg.db":
                    db_handle = item.get("handle")
                    break

            if db_handle:
                sql = "SELECT UserName, NickName, Remark, Alias, Type FROM Contact;"
                query_res = self.call_api(34, {"db_handle": db_handle, "sql": sql})
                data_rows = query_res.get("data", [])
                for row in data_rows:
                    user_name = self._extract_field(row, "UserName", "userName", "wxid")
                    if not user_name:
                        continue
                    nick = self._extract_field(row, "NickName", "nickName", "nickname")
                    remark = self._extract_field(row, "Remark", "remark")
                    alias = self._extract_field(row, "Alias", "alias")
                    db_map[user_name] = {
                        "nickname": nick,
                        "remark": remark,
                        "alias": alias
                    }
        except Exception as e:
            print(f"[WeChatClient] 从本地数据库读取联系人异常: {e}", flush=True)
        return db_map

    def get_contacts(self):
        # 1. 尝试从本地数据库读取全量精准群名与备注
        db_map = self.get_contacts_from_db()

        # 2. 调用 API 15 获取通讯录列表
        res = self.call_api(15)
        raw_list = res.get("data", [])

        # 如果 API 15 未返回，但数据库有数据，使用数据库数据
        merged_ids = set()
        items = []

        if isinstance(raw_list, list) and raw_list:
            for it in raw_list:
                wid = self._extract_field(it, "wxid", "UserName", "wx_id")
                if wid:
                    items.append(it)
                    merged_ids.add(wid)

        # 把数据库中存在但 API 15 未列出的联系人补充进来（例如部分群聊）
        for wid, info in db_map.items():
            if wid not in merged_ids and not wid.startswith("gh_"): # 排除公众号
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

            # 优先从数据库缓存提取准确昵称与备注
            db_info = db_map.get(wxid, {})
            nickname = self._extract_field(item, "nickname", "NickName", "nick_name") or db_info.get("nickname", "")
            remark = self._extract_field(item, "remark", "Remark", "remark_name") or db_info.get("remark", "")
            alias = self._extract_field(item, "alias", "Alias", "custom_account") or db_info.get("alias", "")

            # 计算显示名称
            is_chatroom = wxid.endswith("@chatroom")
            if is_chatroom:
                if remark:
                    display_name = remark
                elif nickname:
                    display_name = nickname
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

            # 存入全局名称缓存
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
                # 排除系统特殊号与公众号等无用噪音
                if not wxid.startswith("gh_") and wxid not in ["medianote", "floatbottle", "fmessage", "qmessage"]:
                    friends.append(contact_obj)

        self._cache_time = now
        return {"friends": friends, "chatrooms": chatrooms}

    def resolve_name(self, wxid, chatroom_id=None):
        if not wxid:
            return ""
        if wxid == "filehelper":
            return "文件传输助手"
        if wxid in self._name_cache:
            return self._name_cache[wxid]

        # 尝试查询群成员昵称
        if chatroom_id:
            try:
                res = self.call_api(26, {"chatroom_id": chatroom_id, "wxid": wxid})
                nick = res.get("nickname") or res.get("data")
                if nick:
                    self._name_cache[wxid] = str(nick).strip()
                    return self._name_cache[wxid]
            except Exception:
                pass

        # 尝试从内存缓存查
        try:
            res = self.call_api(18, {"wxid": wxid})
            data = res.get("data", {})
            nick = self._extract_field(data, "NickName", "nickname", "Remark", "remark")
            if nick:
                self._name_cache[wxid] = nick
                return nick
        except Exception:
            pass

        return wxid

wechat_client = WeChatClient()
