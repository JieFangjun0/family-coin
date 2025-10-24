FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 复制 requirements.txt
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制所有项目文件
COPY . .

# 暴露端口
EXPOSE 8000
EXPOSE 8501

CMD ["bash"]