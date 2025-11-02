# --- 阶段 1: 构建环境 ---
# 使用一个包含完整 Node.js 环境的镜像来构建项目
FROM node:24-alpine AS builder

# 设置工作目录
WORKDIR /app

# 复制 package.json 和 package-lock.json 来缓存依赖安装步骤
COPY package*.json ./

# 安装项目依赖
RUN npm install

# 复制所有剩余的源代码
COPY . .

# 执行构建命令，这会把 Vue 代码编译成纯粹的 HTML/CSS/JS 静态文件
# 编译后的文件会输出到 /app/dist 目录
RUN npm run build


# --- 阶段 2: 生产环境 ---
# 使用一个非常轻量级的 Nginx 服务器来托管我们构建好的静态文件
FROM nginx:stable-alpine

# 从 'builder' 阶段复制编译好的静态文件到 Nginx 的网站根目录
COPY --from=builder /app/dist /usr/share/nginx/html

# 复制自定义的 Nginx 配置文件
# 我们需要这个文件来正确处理单页应用 (SPA) 的路由
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 暴露 Nginx 的默认端口
EXPOSE 80

# Nginx 镜像会自动运行，所以我们不需要 CMD 指令