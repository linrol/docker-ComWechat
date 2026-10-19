# docker-ComWechat
[![docker 镜像](https://dockeri.co/image/tomsnow1999/docker-com_wechat_robot)](https://hub.docker.com/r/tomsnow1999/docker-com_wechat_robot/tags)

[![镜像大小](https://badgen.net/docker/size/tomsnow1999/docker-com_wechat_robot)](https://hub.docker.com/r/tomsnow1999/docker-com_wechat_robot/tags)

A docker image for [ComWeChatRobot](https://github.com/ljc545w/ComWeChatRobot)


``` shell
docker run \
    --name comwechat  \
    --network host \
    -e VNCPASS=asdfgh123 \
    -e COMWECHAT=https://github.com/ljc545w/ComWeChatRobot/releases/download/3.7.0.30-0.0.5/3.7.0.30-0.0.5.zip \
    -dti  \
    --ipc=host \
    --privileged \
    -v $(pwd)/volume/WeChat\ Files/:'/home/user/.wine/drive_c/users/user/My Documents/WeChat Files/'  \
    -v $(pwd)/volume/Application\ Data:'/home/user/.wine/drive_c/users/user/Application Data/' \
    tomsnow1999/docker-com_wechat_robot
```

### 参数说明
* 端口 5905: VNC 服务的端口(用于连接扫码登录)
* 端口 8000: Web 机器人管理控制台端口 (浏览器直接访问)
* network host: 使用宿主机网络(在 Linux Docker 环境下使用)
* 环境变量 VNCPASS: 连接 VNC 的密码（默认 YourSafeVNCPassword）
* 环境变量 ADMIN_USER: Web 控制台管理账号（默认 admin）
* 环境变量 ADMIN_PASS: Web 控制台管理密码（默认 admin123）
* 环境变量 WEB_PORT: Web 控制台监听端口（默认 8000）
* 环境变量 COMWECHAT: [ComWeChatRobot](https://github.com/ljc545w/ComWeChatRobot/releases) 动态库文件压缩包下载链接
* 目录映射 `./data:/data`: 机器人规则配置及转发日志数据持久化目录

## 如何使用
1. 使用 [docker-compose](./docker-compose.yaml) 启动容器：
   ```bash
   docker-compose up -d
   ```
2. 连接 VNC (宿主机 IP:5905) 扫码登录微信（容器内置自动跳过版本检查补丁，100% 扫码登录成功）。
3. 打开浏览器访问 `http://<服务器IP>:8000` 进入微信机器人管理控制台：
   - 默认账号: `admin`，默认密码: `admin123`
   - **功能特性**：
     - **实时运行看板**：微信在线状态监控、消息收发统计指标；
     - **群消息监控与转发规则**：支持按指定群或全部群监听；支持正则表达式、包含关键词、完全匹配；
     - **自定义转发模板**：支持群名 `{group_name}`、发信人 `{sender_name}`、原始内容 `{content}` 等变量替换；
     - **规则实时测试器**：可在 Web 端直接输入模拟群消息，即时预览正则是否命中及转发渲染效果；
     - **群聊与联系人库**：一键浏览当前微信好友与群聊 ID，支持一键复制；
     - **完整转发流水日志**：记录所有捕获与转发事件。


## 鸣谢
[ljc545w/ComWeChatRobot](https://github.com/ljc545w/ComWeChatRobot): ComWeChatRobot 项目本体

[0honus0/ComWeChat_Inject](https://github.com/0honus0/ComWeChat_Inject): 本镜像所使用的注入器

## 相关项目
[efb-wechat-comwechat-slave](https://github.com/0honus0/efb-wechat-comwechat-slave): 使用 Telegram 来接收&管理微信消息

## 声明
**本项目仅供学习研究，强烈反对商业用途或者滥用(通过程序化控制微信对其他人进行骚扰诈骗等)！使用本项目造成的一切责任与本人无关，一切责任由使用者自行承担！**
