#!/usr/bin/python3
import subprocess, os, signal, datetime, time, shutil
from concurrent.futures import ThreadPoolExecutor
executor = ThreadPoolExecutor()


class DockerWechatHook:
    def __init__(self):
        signal.signal(signal.SIGINT, self.now_exit)
        signal.signal(signal.SIGHUP, self.now_exit)
        signal.signal(signal.SIGTERM, self.now_exit)

    def now_exit(self, signum, frame):
        self.exit_container()

    def skip_version(self):
        print("开始轮询执行跳过版本号检查脚本...", flush=True)
        wine_cmd = ['box86', '/home/user/wine/bin/wine'] if os.path.exists('/home/user/wine/bin/wine') else ['wine']
        cmd = wine_cmd + ['/home/user/.wine/drive_c/users/user/python/python.exe', '/home/user/.wine/drive_c/users/user/skip_wechat_version.py']
        time.sleep(1)
        for i in range(30):
            print(f"[{i+1}/30] 正在尝试修改微信版本号...", flush=True)
            try:
                skip_message = subprocess.run(cmd, capture_output=True, timeout=20)
                raw_out = (skip_message.stdout or b"") + (skip_message.stderr or b"")
                try:
                    output = raw_out.decode("utf-8")
                except Exception:
                    output = raw_out.decode("gbk", errors="ignore")
                is_success = (
                    "好了，可以扫码登录了" in output
                    or "好了，可以扫码登录了".encode("utf-8") in raw_out
                    or "好了，可以扫码登录了".encode("gbk") in raw_out
                    or "濂戒簡" in output
                )
                if is_success:
                    print("🎉 微信版本号已成功修改为 3.9.10.19！", flush=True)
                    print(output.strip(), flush=True)
                    return True
                else:
                    last_line = output.strip().split('\n')[-1] if output.strip() else "无输出"
                    print(f"[{i+1}/30] 等待微信就绪 ({last_line})，1 秒后重试...", flush=True)
            except subprocess.TimeoutExpired:
                print(f"[{i+1}/30] 执行跳过版本脚本超时(20s)，1 秒后重试...", flush=True)
            except Exception as e:
                print(f"[{i+1}/30] 执行跳过版本脚本异常: {e}，1 秒后重试...", flush=True)
            time.sleep(1)
        else:
            print("⚠️ 跳过版本号检查超时，请手动检查微信状态！", flush=True)
            return False

    def prepare(self):
        # if not os.path.exists("/comwechat/http/SWeChatRobot.dll"):
        if not os.path.exists("/dll_downloaded.txt"):
            COMWECHAT = os.environ['COMWECHAT']
            subprocess.run(['wget', COMWECHAT, '-O', 'comwechat.zip'])
            subprocess.run(['unzip', '-d', 'comwechat', 'comwechat.zip'])
            subprocess.run(['mv', '/WeChatHook.exe', '/comwechat/http/WeChatHook.exe'])
            with open("/dll_downloaded.txt", "w") as f:
                f.write("True\n")

    @staticmethod
    def _make_vnc_passwd(password: str) -> bytes:
        pw = (password[:8].ljust(8, '\0')).encode('latin1')
        def rev(b):
            b = ((b & 0xF0) >> 4) | ((b & 0x0F) << 4)
            b = ((b & 0xCC) >> 2) | ((b & 0x33) << 2)
            b = ((b & 0xAA) >> 1) | ((b & 0x55) << 1)
            return b
        key_bytes = bytes([rev(b) for b in pw])
        PC1 = [56, 48, 40, 32, 24, 16, 8, 0, 57, 49, 41, 33, 25, 17,
               9, 1, 58, 50, 42, 34, 26, 18, 10, 2, 59, 51, 43, 35,
               62, 54, 46, 38, 30, 22, 14, 6, 61, 53, 45, 37, 29, 21,
               13, 5, 60, 52, 44, 36, 28, 20, 12, 4, 27, 19, 11, 3]
        PC2 = [13, 16, 10, 23, 0, 4, 2, 27, 14, 5, 20, 9,
               22, 18, 11, 3, 25, 7, 15, 6, 26, 19, 12, 1,
               40, 51, 30, 36, 46, 54, 29, 39, 50, 44, 32, 47,
               43, 48, 38, 55, 33, 52, 45, 41, 49, 35, 28, 31]
        SHIFTS = [1, 1, 2, 2, 2, 2, 2, 2, 1, 2, 2, 2, 2, 2, 2, 1]
        IP = [57, 49, 41, 33, 25, 17, 9, 1, 59, 51, 43, 35, 27, 19, 11, 3,
              61, 53, 45, 37, 29, 21, 13, 5, 63, 55, 47, 39, 31, 23, 15, 7,
              56, 48, 40, 32, 24, 16, 8, 0, 58, 50, 42, 34, 26, 18, 10, 2,
              60, 52, 44, 36, 28, 20, 12, 4, 62, 54, 46, 38, 30, 22, 14, 6]
        IP_INV = [39, 7, 47, 15, 55, 23, 63, 31, 38, 6, 46, 14, 54, 22, 62, 30,
                  37, 5, 45, 13, 53, 21, 61, 29, 36, 4, 44, 12, 52, 20, 60, 28,
                  35, 3, 43, 11, 51, 19, 59, 27, 34, 2, 42, 10, 50, 18, 58, 26,
                  33, 1, 41, 9, 49, 17, 57, 25, 32, 0, 40, 8, 48, 16, 56, 24]
        E = [31, 0, 1, 2, 3, 4, 3, 4, 5, 6, 7, 8,
             7, 8, 9, 10, 11, 12, 11, 12, 13, 14, 15, 16,
             15, 16, 17, 18, 19, 20, 19, 20, 21, 22, 23, 24,
             23, 24, 25, 26, 27, 28, 27, 28, 29, 30, 31, 0]
        P = [15, 6, 19, 20, 28, 11, 27, 16, 0, 14, 22, 25, 4, 17, 30, 9,
             1, 7, 23, 13, 31, 26, 2, 8, 18, 12, 29, 5, 21, 10, 3, 24]
        S_BOX = [
            [14, 4, 13, 1, 2, 15, 11, 8, 3, 10, 6, 12, 5, 9, 0, 7, 0, 15, 7, 4, 14, 2, 13, 1, 10, 6, 12, 11, 9, 5, 3, 8, 4, 1, 14, 8, 13, 6, 2, 11, 15, 12, 9, 7, 3, 10, 5, 0, 15, 12, 8, 2, 4, 9, 1, 7, 5, 11, 3, 14, 10, 0, 6, 13],
            [15, 1, 8, 14, 6, 11, 3, 4, 9, 7, 2, 13, 12, 0, 5, 10, 3, 13, 4, 7, 15, 2, 8, 14, 12, 0, 1, 10, 6, 9, 11, 5, 0, 14, 7, 11, 10, 4, 13, 1, 5, 8, 12, 6, 9, 3, 2, 15, 13, 8, 10, 1, 3, 15, 4, 2, 11, 6, 7, 12, 0, 5, 14, 9],
            [10, 0, 9, 14, 6, 3, 15, 5, 1, 13, 12, 7, 11, 4, 2, 8, 13, 7, 0, 9, 3, 4, 6, 10, 2, 8, 5, 14, 12, 11, 15, 1, 13, 6, 4, 9, 8, 15, 3, 0, 11, 1, 2, 12, 5, 10, 14, 7, 1, 10, 13, 0, 6, 9, 8, 7, 4, 15, 14, 3, 11, 5, 2, 12],
            [7, 13, 14, 3, 0, 6, 9, 10, 1, 2, 8, 5, 11, 12, 4, 15, 13, 8, 11, 5, 6, 15, 0, 3, 4, 7, 2, 12, 1, 10, 14, 9, 10, 6, 9, 0, 12, 11, 7, 13, 15, 1, 3, 14, 5, 2, 8, 4, 3, 15, 0, 6, 10, 1, 13, 8, 9, 4, 5, 11, 12, 7, 2, 14],
            [2, 12, 4, 1, 7, 10, 11, 6, 8, 5, 3, 15, 13, 0, 14, 9, 14, 11, 2, 12, 4, 7, 13, 1, 5, 0, 15, 10, 3, 9, 8, 6, 4, 2, 1, 11, 10, 13, 7, 8, 15, 9, 12, 5, 6, 3, 0, 14, 11, 8, 12, 7, 1, 14, 2, 13, 6, 15, 0, 9, 10, 4, 5, 3],
            [12, 1, 10, 15, 9, 2, 6, 8, 0, 13, 3, 4, 14, 7, 5, 11, 10, 15, 4, 2, 7, 12, 9, 5, 6, 1, 13, 14, 0, 11, 3, 8, 9, 14, 15, 5, 2, 8, 12, 3, 7, 0, 4, 10, 1, 13, 11, 6, 4, 3, 2, 12, 9, 5, 15, 10, 11, 14, 1, 7, 6, 0, 8, 13],
            [4, 11, 2, 14, 15, 0, 8, 13, 3, 12, 9, 7, 5, 10, 6, 1, 13, 0, 11, 7, 4, 9, 1, 10, 14, 3, 5, 12, 2, 15, 8, 6, 1, 4, 11, 13, 12, 3, 7, 14, 10, 15, 6, 8, 0, 5, 9, 2, 6, 11, 13, 8, 1, 4, 10, 7, 9, 5, 0, 15, 14, 2, 3, 12],
            [13, 2, 8, 4, 6, 15, 11, 1, 10, 9, 3, 14, 5, 0, 12, 7, 1, 15, 13, 8, 10, 3, 7, 4, 12, 5, 6, 11, 0, 14, 9, 2, 7, 11, 4, 1, 9, 12, 14, 2, 0, 6, 10, 13, 15, 3, 5, 8, 2, 1, 14, 7, 4, 10, 8, 13, 15, 12, 9, 0, 3, 5, 6, 11]
        ]
        def permute(val, table, in_len):
            out = 0
            for bit in table:
                out = (out << 1) | ((val >> (in_len - 1 - bit)) & 1)
            return out

        k_int = int.from_bytes(key_bytes, 'big')
        k_perm = permute(k_int, PC1, 64)
        c, d = (k_perm >> 28) & 0xFFFFFFF, k_perm & 0xFFFFFFF
        subkeys = []
        for shift in SHIFTS:
            c = ((c << shift) & 0xFFFFFFF) | (c >> (28 - shift))
            d = ((d << shift) & 0xFFFFFFF) | (d >> (28 - shift))
            subkeys.append(permute((c << 28) | d, PC2, 56))

        block = permute(0, IP, 64)
        left, right = (block >> 32) & 0xFFFFFFFF, block & 0xFFFFFFFF
        for k in subkeys:
            r_exp = permute(right, E, 32)
            xor_res = r_exp ^ k
            s_out = 0
            for i in range(8):
                chunk = (xor_res >> (42 - 6 * i)) & 0x3F
                row = ((chunk & 0x20) >> 4) | (chunk & 1)
                col = (chunk >> 1) & 0xF
                s_out = (s_out << 4) | S_BOX[i][row * 16 + col]
            f_res = permute(s_out, P, 32)
            left, right = right, left ^ f_res

        cipher = permute((right << 32) | left, IP_INV, 64)
        return cipher.to_bytes(8, 'big')

    def run_vnc(self):
        # 补齐 vncserver 脚本硬编码查找的 tigervncpasswd 软链接
        if os.path.exists('/usr/bin/vncpasswd') and not os.path.exists('/usr/bin/tigervncpasswd'):
            try:
                os.symlink('/usr/bin/vncpasswd', '/usr/bin/tigervncpasswd')
            except Exception:
                pass
        if os.path.exists('/usr/bin/vncserver') and not os.path.exists('/usr/bin/tigervncserver'):
            try:
                os.symlink('/usr/bin/vncserver', '/usr/bin/tigervncserver')
            except Exception:
                pass

        # 确保 VNC 目录存在
        os.makedirs('/root/.vnc', mode=755, exist_ok=True)
        os.makedirs('/root/.config/tigervnc', mode=755, exist_ok=True)

        # 核心：直接用纯 Python 将 VNCPASS 加密写入标准 passwd 文件，100% 独立于外部二进制！
        vnc_pass = os.environ.get('VNCPASS', 'asdfgh123')
        try:
            passwd_bytes = self._make_vnc_passwd(vnc_pass)
            for p in ['/root/.vnc/passwd', '/root/.config/tigervnc/passwd']:
                with open(p, 'wb') as f:
                    f.write(passwd_bytes)
                os.chmod(p, 0o600)
            print(f"🎉 VNC 密码文件已生成就绪 (VNCPASS={vnc_pass})", flush=True)
        except Exception as e:
            print(f"生成 VNC 密码文件提示: {e}", flush=True)

        vncserver_bin = (
            shutil.which('vncserver')
            or shutil.which('tigervncserver')
            or ('/usr/bin/tigervncserver' if os.path.exists('/usr/bin/tigervncserver') else None)
            or ('/usr/bin/vncserver' if os.path.exists('/usr/bin/vncserver') else None)
        )
        if vncserver_bin:
            cmd = [vncserver_bin, '-localhost', 'no', '-xstartup', '/usr/bin/openbox', ':5']
            if not os.path.exists('/root/.vnc/passwd'):
                cmd.extend(['-SecurityTypes', 'None', '--I-KNOW-THIS-IS-INSECURE'])
            self.vnc = subprocess.Popen(cmd)
        else:
            print("警告: 未找到可用 vncserver 二进制文件", flush=True)
            self.vnc = None

    def run_dbus(self):
        try:
            subprocess.run(['service', 'dbus', 'start'], capture_output=True)
        except Exception:
            pass

    def run_wechat(self):
        print("1. 启动微信进程...", flush=True)
        self.wechat = subprocess.Popen(['box86','/home/user/wine/bin/wine','/home/user/.wine/drive_c/Program Files/Tencent/WeChat/WeChat.exe'])
        print("2. 同步卡点修改微信版本号，确保扫码前补丁 100% 生效...", flush=True)
        self.skip_version()

    def run_hook(self):
        print("3. 版本号已就绪，启动 WeChatHook 注入程序...", flush=True)
        self.reg_hook = subprocess.Popen(['box86','/home/user/wine/bin/wine','/comwechat/http/WeChatHook.exe'])

    def run_web_admin(self):
        print("4. 启动微信机器人管理平台 Web 服务 (端口 8000)...", flush=True)
        try:
            self.web_admin = subprocess.Popen(['python3', '/web_admin/app.py'])
        except Exception as e:
            print(f"启动 Web 管理控制台异常: {e}", flush=True)

    def exit_container(self):
        print(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')+ ' 正在退出容器...', flush=True)
        try:
            print(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')+ ' 退出Web控制台...', flush=True)
            os.kill(self.web_admin.pid, signal.SIGTERM)
        except:
            pass
        try:
            print(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')+ ' 退出微信...', flush=True)
            os.kill(self.wechat.pid, signal.SIGTERM)
        except:
            pass
        try:
            print(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')+ ' 退出Hook程序...', flush=True)
            os.kill(self.reg_hook.pid, signal.SIGTERM)
        except:
            pass
        try:
            print(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')+ ' 退出VNC...', flush=True)
            if getattr(self, 'vnc', None):
                os.kill(self.vnc.pid, signal.SIGTERM)
        except:
            pass

    def run_all_in_one(self):
        print(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')+ ' 启动容器中...', flush=True)
        self.run_dbus()
        self.prepare()
        self.run_vnc()
        self.run_wechat()
        self.run_hook()
        self.run_web_admin()
        print(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')+ ' 🎉 容器已完全就绪，请使用 VNC (端口 5905) 扫码登录，并在浏览器访问 http://<服务器IP>:8000 进入管理平台！', flush=True)
        try:
            while True:
                time.sleep(5)
        except (KeyboardInterrupt, SystemExit):
            self.exit_container()


if __name__ == '__main__' :
    print('---All in one 微信 ComRobot 容器---', flush=True)
    hook = DockerWechatHook()
    hook.run_all_in_one()