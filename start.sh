#!/bin/bash

# 这个脚本用于方便地启动 Docker Compose
# 确保在 Linux/Mac 上给予它执行权限: chmod +x start.sh

echo "正在启动 JCoin (后端 + 前端)..."

# --build: 强制重新构建镜像（如果代码有改动）
# -d: 后台运行 (detached mode)
docker-compose up --build -d

echo "-----------------------------------"
echo "服务已启动！"
echo "你可以通过 http://<你的服务器IP>:8501 访问 JCoin"
echo "使用 'docker-compose logs -f' 查看实时日志"
echo "使用 'docker-compose down' 关闭服务"
