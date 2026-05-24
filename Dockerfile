# NetGuard Docker 镜像
# 构建: docker build -t netguard .
# 使用: docker compose run netguard <子命令>
FROM python:3.13-slim

WORKDIR /app

# 先装依赖（利用 Docker 层缓存，改代码不需要重装包）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目文件
COPY . .

# 预创运行时目录
RUN mkdir -p backups_config reports logs

ENTRYPOINT ["python", "main.py"]
