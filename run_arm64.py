#!/usr/bin/python3
import subprocess, os, signal, datetime, time
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
        for i in range(30):
            time.sleep(2)
            skip_message = subprocess.run(cmd, capture_output=True, text=True)
            if "好了，可以扫码登录了" in skip_message.stdout:
                print("微信版本号修改成功，可以扫码登录了！", flush=True)
                print(skip_message.stdout, flush=True)
                break
            else:
                print(f"等待微信模块加载中，重试修改版本号 ({i+1}/30)...", flush=True)
        else:
            print("跳过版本号检查超时，请手动检查微信状态！", flush=True)

    def prepare(self):
        # if not os.path.exists("/comwechat/http/SWeChatRobot.dll"):
        if not os.path.exists("/dll_downloaded.txt"):
            COMWECHAT = os.environ['COMWECHAT']
            # NOTE: 当 ComWeChatRobot 的仓库地址变动的话需要修改
            if not COMWECHAT.startswith("https://github.com/ljc545w/ComWeChatRobot/releases/download/"):
                print("你提供的地址不是 COMWECHAT 仓库的 Release 下载地址，程序将自动退出！")
                self.exit_container()
            subprocess.run(['wget', COMWECHAT, '-O', 'comwechat.zip'])
            subprocess.run(['unzip', '-d', 'comwechat', 'comwechat.zip'])
            subprocess.run(['mv', '/WeChatHook.exe', '/comwechat/http/WeChatHook.exe'])
            with open("/dll_downloaded.txt", "w") as f:
                f.write("True\n")

    def run_vnc(self):
        # 根据 VNCPASS 环境变量生成 vncpasswd 文件
        os.makedirs('/root/.vnc', mode=755, exist_ok=True)
        passwd_output = subprocess.run(['/usr/bin/vncpasswd','-f'],input=os.environ['VNCPASS'].encode(),capture_output=True)
        with open('/root/.vnc/passwd', 'wb') as f:
            f.write(passwd_output.stdout)
        os.chmod('/root/.vnc/passwd', 0o700)
        self.vnc = subprocess.Popen(['/usr/bin/vncserver','-localhost', 'no', '-xstartup', '/usr/bin/openbox' ,':5'])

    def run_dbus(self):
        try:
            subprocess.run(['service', 'dbus', 'start'], capture_output=True)
        except Exception:
            pass

    def run_wechat(self):
        print("开始运行微信", flush=True)
        executor.submit(self.skip_version)
        self.wechat = subprocess.Popen(['box86','/home/user/wine/bin/wine','/home/user/.wine/drive_c/Program Files/Tencent/WeChat/WeChat.exe'])

    def run_hook(self):
        print("等待 5 秒再 hook", flush=True)
        time.sleep(5)
        self.reg_hook = subprocess.Popen(['box86','/home/user/wine/bin/wine','/comwechat/http/WeChatHook.exe'])

    def exit_container(self):
        print(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')+ ' 正在退出容器...', flush=True)
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
        print(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')+ ' 感谢使用.', flush=True)


if __name__ == '__main__' :
    print('---All in one 微信 ComRobot 容器---', flush=True)
    hook = DockerWechatHook()
    hook.run_all_in_one()