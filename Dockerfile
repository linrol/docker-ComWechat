ARG TARGETARCH

FROM zixia/wine:6.0 AS base-amd64
FROM zixia/wine:arm64 AS base-arm64

FROM base-${TARGETARCH} AS final
ARG TARGETARCH

USER root
WORKDIR /

ENV WINEPREFIX=/home/user/.wine \
    WINEDEBUG=-all \
    LANG=zh_CN.UTF-8 \
    LC_ALL=zh_CN.UTF-8 \
    DISPLAY=:5 \
    VNCPASS=YourSafeVNCPassword \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    NO_AT_BRIDGE=1 \
    ADMIN_USER=admin \
    ADMIN_PASS=admin123 \
    WEB_PORT=8000 \
    DATA_DIR=/data \
    COMWECHAT=https://github.com/ljc545w/ComWeChatRobot/releases/download/3.7.0.30-0.1.1-pre/3.7.0.30-0.1.1-pre.zip

# 提示 vnc 使用的端口，web 控制台端口
EXPOSE 5905 8000

# 1. 系统依赖与运行环境安装（基础层，永久缓存）
RUN if grep -q "bullseye" /etc/os-release 2>/dev/null; then \
        echo "Acquire::Check-Valid-Until false;" > /etc/apt/apt.conf.d/99no-check-valid-until && \
        sed -i 's|security.debian.org/debian-security|archive.debian.org/debian-security|g' /etc/apt/sources.list && \
        sed -i '/opensuse/d' /etc/apt/sources.list.d/*.list 2>/dev/null || true && \
        rm -f /etc/apt/sources.list.d/*opensuse* 2>/dev/null || true; \
    fi && \
    apt update && \
    apt --no-install-recommends install wget unzip winbind tigervnc-standalone-server tigervnc-common openbox \
    dbus dbus-x11 \
    mesa-utils \
    procps \
    pev \
    pulseaudio-utils \
    python3-flask \
    python3-requests -y && \
    mkdir -p /data

# 2. 进程守护 dumb-init 下载（基础层，永久缓存）
RUN wget --no-check-certificate -O /bin/dumb-init "https://github.com/Yelp/dumb-init/releases/download/v1.2.5/dumb-init_1.2.5_$(uname -m)" && \
    chmod a+x /bin/dumb-init

# 3. 字体与 Windows 注册表初始化（基础层，永久缓存）
ADD wine/simsun.ttc /home/user/.wine/drive_c/windows/Fonts/simsun.ttc
ADD wine/微信.lnk /home/user/.wine/drive_c/users/Public/Desktop/微信.lnk
ADD wine/system.reg wine/user.reg wine/userdef.reg /home/user/.wine/

# 4. 下载并部署 Windows 便携版 Python 环境与 Pymem（基础层，耗时大，严格前置永久缓存）
RUN chown -R root:root /home/user/.wine && \
    mkdir -p /home/user/.wine/drive_c/users/user/python && \
    wget --no-check-certificate -O /tmp/python.zip "https://www.python.org/ftp/python/3.8.10/python-3.8.10-embed-win32.zip" && \
    unzip -q /tmp/python.zip -d /home/user/.wine/drive_c/users/user/python && \
    wget --no-check-certificate -O /home/user/.wine/drive_c/users/user/python/get-pip.py "https://bootstrap.pypa.io/pip/3.8/get-pip.py" && \
    sed -i 's/#import site/import site/' /home/user/.wine/drive_c/users/user/python/python38._pth && \
    wine /home/user/.wine/drive_c/users/user/python/python.exe /home/user/.wine/drive_c/users/user/python/get-pip.py && \
    wine /home/user/.wine/drive_c/users/user/python/python.exe -m pip --trusted-host pypi.python.org install Pymem && \
    rm -f /tmp/python.zip

# 5. 下载并解压微信客户端包（基础层，100MB+，严格前置永久缓存）
RUN wget --no-check-certificate -O /Tencent.zip "https://github.com/tom-snow/docker-ComWechat/releases/download/v0.2_wc3.7.0.30/Tencent.zip" && \
    mkdir -p "/home/user/WeChat Files" "/home/user/.wine/drive_c/users/user/Application Data" && \
    rm -rf "/home/user/.wine/drive_c/Program Files/Tencent/" && \
    unzip Tencent.zip && \
    mv wine/Tencent "/home/user/.wine/drive_c/Program Files/" && \
    apt autoremove -y && \
    apt clean && \
    rm -rf wine Tencent.zip /tmp/*

# =========================================================================
# 6. 业务代码层（频繁修改，全部沉底！修改代码绝不破坏以上 1~5 层的庞大缓存）
# =========================================================================
ADD WeChatHook.exe /
COPY web_admin /web_admin
COPY skip_wechat_version.py /home/user/.wine/drive_c/users/user/skip_wechat_version.py
COPY run_${TARGETARCH}.py /run.py

RUN chmod a+x /run.py && \
    chmod a+x /home/user/.wine/drive_c/users/user/skip_wechat_version.py && \
    ([ -f /usr/bin/tigervncserver ] && ln -sf /usr/bin/tigervncserver /usr/bin/vncserver || true) && \
    ([ -f /usr/bin/tigervncpasswd ] && ln -sf /usr/bin/tigervncpasswd /usr/bin/vncpasswd || true) && \
    chown root:root -R /home/user/.wine

ENTRYPOINT [ "/bin/dumb-init" ]
CMD ["/run.py", "start"]
