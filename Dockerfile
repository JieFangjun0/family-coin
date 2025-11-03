FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 复制 requirements.txt
COPY requirements.txt .

# 安装依赖
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制所有项目文件
COPY . .

# 暴露后端服务端口
EXPOSE 8000

# 设置默认启动命令来运行后端服务
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]