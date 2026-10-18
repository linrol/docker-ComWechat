# 多架构一次性构建并推送（覆盖 latest）
docker buildx build --platform linux/amd64,linux/arm64 -t linrol/docker-com_wechat_robot:latest --push .

# 单独构建本地当前架构
docker build -t linrol/docker-com_wechat_robot:latest .