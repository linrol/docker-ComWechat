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
        time.sleep(1)
        for i in range(30):
            print(f"[{i+1}/30] 正在尝试修改微信版本号...", flush=True)
            try:
                skip_message = subprocess.run(
                    ['wine', '/home/user/.wine/drive_c/users/user/python/python.exe', '/home/user/.wine/drive_c/users/user/skip_wechat_version.py'],
                    capture_output=True,
                    timeout=15
                )
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
                print(f"[{i+1}/30] 执行跳过版本脚本超时(15s)，1 秒后重试...", flush=True)
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

    def run_vnc(self):
        # 根据 VNCPASS 环境变量生成 vncpasswd 文件
        os.makedirs('/root/.vnc', mode=755, exist_ok=True)
        vncpasswd_bin = (
            shutil.which('vncpasswd')
            or shutil.which('tigervncpasswd')
            or ('/usr/bin/tigervncpasswd' if os.path.exists('/usr/bin/tigervncpasswd') else None)
            or ('/usr/bin/vncpasswd' if os.path.exists('/usr/bin/vncpasswd') else None)
        )
        vncserver_bin = (
            shutil.which('vncserver')
            or shutil.which('tigervncserver')
            or ('/usr/bin/tigervncserver' if os.path.exists('/usr/bin/tigervncserver') else None)
            or ('/usr/bin/vncserver' if os.path.exists('/usr/bin/vncserver') else None)
        )
        vnc_pass = os.environ.get('VNCPASS', 'asdfgh123')
        if vncpasswd_bin:
            try:
                passwd_output = subprocess.run([vncpasswd_bin, '-f'], input=vnc_pass.encode(), capture_output=True)
                if passwd_output.stdout:
                    with open('/root/.vnc/passwd', 'wb') as f:
                        f.write(passwd_output.stdout)
                    os.chmod('/root/.vnc/passwd', 0o700)
            except Exception as e:
                print(f"生成 VNC 密码提示/异常: {e}", flush=True)

        if vncserver_bin:
            self.vnc = subprocess.Popen([vncserver_bin, '-localhost', 'no', '-xstartup', '/usr/bin/openbox', ':5'])
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
        self.wechat = subprocess.Popen(['wine','/home/user/.wine/drive_c/Program Files/Tencent/WeChat/WeChat.exe'])
        print("2. 同步卡点修改微信版本号，确保扫码前补丁 100% 生效...", flush=True)
        self.skip_version()

    def run_hook(self):
        print("3. 版本号已就绪，启动 WeChatHook 注入程序...", flush=True)
        self.reg_hook = subprocess.Popen(['wine','/comwechat/http/WeChatHook.exe'])

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
            self.wechat.wait()
        except Exception:
            pass


if __name__ == '__main__' :
    print('---All in one 微信 ComRobot 容器---', flush=True)
    hook = DockerWechatHook()
    hook.run_all_in_one()