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

    def fix_wechat_directories(self):
        print("检查并初始化微信数据保存目录与权限...", flush=True)
        dirs = [
            "/root/Documents",
            "/home/user/Documents",
            "/home/user/WeChat Files",
            "/home/user/.wine/drive_c/users/user/My Documents",
            "/home/user/.wine/drive_c/users/user/Documents",
            "/home/user/.wine/drive_c/users/user/My Documents/WeChat Files",
            "/home/user/.wine/drive_c/users/user/Documents/WeChat Files",
            "/home/user/.wine/drive_c/users/user/Application Data",
            "/home/user/.wine/drive_c/users/user/Local Settings/Application Data",
            "/home/user/.wine/drive_c/users/root/My Documents",
            "/home/user/.wine/drive_c/users/root/Documents",
            "/home/user/.wine/drive_c/users/root/My Documents/WeChat Files",
            "/home/user/.wine/drive_c/users/root/Documents/WeChat Files",
            "/home/user/.wine/drive_c/users/root/Application Data",
            "/home/user/.wine/drive_c/users/root/Local Settings/Application Data",
        ]
        for d in dirs:
            try:
                if os.path.islink(d) and not os.path.exists(d):
                    print(f"清理断裂符号链接: {d}", flush=True)
                    os.unlink(d)
                os.makedirs(d, mode=0o777, exist_ok=True)
                os.chmod(d, 0o777)
            except Exception as e:
                print(f"初始化目录 {d} 提示: {e}", flush=True)

        try:
            subprocess.run(['chmod', '-R', '777', '/home/user/.wine/drive_c/users'], capture_output=True)
            subprocess.run(['chmod', '-R', '777', '/root/Documents'], capture_output=True)
            subprocess.run(['chmod', '-R', '777', '/home/user/Documents'], capture_output=True)
            subprocess.run(['chmod', '-R', '777', '/home/user/WeChat Files'], capture_output=True)
        except Exception:
            pass
        print("微信数据目录与权限已全部就绪！", flush=True)

    def run_vnc(self):
        # 根据 VNCPASS 环境变量生成 vncpasswd 文件
        os.makedirs('/root/.vnc', mode=755, exist_ok=True)
        vncpasswd_bin = shutil.which('vncpasswd') or '/usr/bin/vncpasswd'
        vncserver_bin = shutil.which('vncserver') or '/usr/bin/vncserver'
        passwd_output = subprocess.run([vncpasswd_bin, '-f'], input=os.environ['VNCPASS'].encode(), capture_output=True)
        with open('/root/.vnc/passwd', 'wb') as f:
            f.write(passwd_output.stdout)
        os.chmod('/root/.vnc/passwd', 0o700)
        self.vnc = subprocess.Popen([vncserver_bin, '-localhost', 'no', '-xstartup', '/usr/bin/openbox', ':5'])

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
        self.fix_wechat_directories()
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