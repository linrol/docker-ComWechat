ARG TARGETARCH

FROM zixia/wine:6.0 AS base-amd64
FROM zixia/wine:arm64 AS base-arm64

FROM base-${TARGETARCH} AS final
ARG TARGETARCH

USER root
WORKDIR /

ENV WINEPREFIX=/home/user/.wine \
    LANG=zh_CN.UTF-8 \
    LC_ALL=zh_CN.UTF-8 \
    DISPLAY=:5 \
    VNCPASS=YourSafeVNCPassword \
    PYTHONUNBUFFERED=1 \
    NO_AT_BRIDGE=1 \
    COMWECHAT=https://github.com/ljc545w/ComWeChatRobot/releases/download/3.7.0.30-0.1.1-pre/3.7.0.30-0.1.1-pre.zip

# 提示 vnc 使用的端口， dll 的端口自行映射
EXPOSE 5905

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
    pulseaudio-utils -y

ADD wine/simsun.ttc /home/user/.wine/drive_c/windows/Fonts/simsun.ttc
ADD wine/微信.lnk /home/user/.wine/drive_c/users/Public/Desktop/微信.lnk
ADD wine/system.reg wine/user.reg wine/userdef.reg /home/user/.wine/
ADD WeChatHook.exe /

# 动态拷贝对应架构的启动脚本，并统一命名为 /run.py
COPY run_${TARGETARCH}.py /run.py

# wine install python3.8 (自动下载 Windows 便携版 Python 环境)
COPY skip_wechat_version.py /home/user/.wine/drive_c/users/user/skip_wechat_version.py
RUN chown -R root:root /home/user/.wine && \
    mkdir -p /home/user/.wine/drive_c/users/user/python && \
    wget --no-check-certificate -O /tmp/python.zip "https://www.python.org/ftp/python/3.8.10/python-3.8.10-embed-win32.zip" && \
    unzip -q /tmp/python.zip -d /home/user/.wine/drive_c/users/user/python && \
    wget --no-check-certificate -O /home/user/.wine/drive_c/users/user/python/get-pip.py "https://bootstrap.pypa.io/pip/3.8/get-pip.py" && \
    sed -i 's/#import site/import site/' /home/user/.wine/drive_c/users/user/python/python38._pth && \
    wine /home/user/.wine/drive_c/users/user/python/python.exe /home/user/.wine/drive_c/users/user/python/get-pip.py && \
    wine /home/user/.wine/drive_c/users/user/python/python.exe -m pip --trusted-host pypi.python.org install Pymem && \
    rm -f /tmp/python.zip

# COPY wine/Tencent.zip /Tencent.zip
RUN wget --no-check-certificate -O /Tencent.zip "https://github.com/tom-snow/docker-ComWechat/releases/download/v0.2_wc3.7.0.30/Tencent.zip" && \
    wget --no-check-certificate -O /bin/dumb-init "https://github.com/Yelp/dumb-init/releases/download/v1.2.5/dumb-init_1.2.5_$(uname -m)" && \
    mkdir -p "/home/user/WeChat Files" "/home/user/.wine/drive_c/users/user/Application Data" && \
    chmod a+x /bin/dumb-init && \
    chmod a+x /run.py && \
    chmod a+x /home/user/.wine/drive_c/users/user/skip_wechat_version.py && \
    rm -rf "/home/user/.wine/drive_c/Program Files/Tencent/" && \
    unzip Tencent.zip && \
    mv wine/Tencent "/home/user/.wine/drive_c/Program Files/" && \
    chown root:root -R /home/user/.wine && \
    apt autoremove -y && \
    apt clean && \
    rm -rf wine Tencent.zip /tmp/*

ENTRYPOINT [ "/bin/dumb-init" ]
CMD ["/run.py", "start"]
