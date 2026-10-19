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

    def get_contacts(self):
        res = self.call_api(15)
        raw_list = res.get("data", [])
        friends = []
        chatrooms = []

        now = time.time()
        for item in raw_list:
            wxid = item.get("wxid", "")
            nickname = item.get("nickname", "")
            remark = item.get("remark", "")
            display_name = remark if remark else (nickname if nickname else wxid)
            if wxid:
                self._name_cache[wxid] = display_name

            contact_obj = {
                "wxid": wxid,
                "nickname": nickname,
                "remark": remark,
                "display_name": display_name
            }
            if wxid.endswith("@chatroom"):
                chatrooms.append(contact_obj)
            else:
                friends.append(contact_obj)

        self._cache_time = now
        return {"friends": friends, "chatrooms": chatrooms}

    def resolve_name(self, wxid, chatroom_id=None):
        # 针对常见内置账号
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
                    self._name_cache[wxid] = nick
                    return nick
            except Exception:
                pass

        return wxid

wechat_client = WeChatClient()
