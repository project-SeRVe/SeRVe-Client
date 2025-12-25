# SeRVe Edge Server - All-in-One Docker Image
# Includes: Suricata IDS + FastAPI Proxy + Streamlit Dashboard

FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    suricata \
    nginx \
    supervisor \
    curl \
    net-tools \
    && rm -rf /var/lib/apt/lists/*

# Create necessary directories
RUN mkdir -p /app/src \
    /app/serve_sdk \
    /app/SeRVe-Client \
    /var/log/edge-server \
    /var/log/suricata \
    /var/log/supervisor \
    /var/log/nginx \
    /etc/suricata/rules \
    /app/local_vectorstore

# Set working directory
WORKDIR /app

# 1. Copy Requirements & Install Dependencies
# 먼저 의존성 파일을 복사해서 설치 (캐싱 효율화)
COPY SeRVe-Client/src/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# 2. Copy Source Code & SDK
# main.py에서 serve_sdk를 import 할 수 있도록 /app/serve_sdk에 복사
COPY SeRVe-Client/serve_sdk /app/serve_sdk
COPY SeRVe-Client/src /app/src
COPY SeRVe-Client/robot_simulator.py /app/
COPY SeRVe-Client/setup_edge_account.py /app/

# 3. Copy Configuration files
COPY SeRVe-Client/supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY SeRVe-Client/nginx.conf /etc/nginx/nginx.conf
COPY SeRVe-Client/suricata/custom.rules /etc/suricata/rules/custom.rules

# 4. Set Environment Variables
# /app 경로를 파이썬 경로에 추가하여 serve_sdk import 가능하게 함
ENV PYTHONPATH=/app

# Configure Suricata
RUN suricata-update && \
    echo "include: /etc/suricata/rules/custom.rules" >> /etc/suricata/suricata.yaml

# Configure Suricata to monitor loopback interface
RUN sed -i 's/interface: eth0/interface: lo/g' /etc/suricata/suricata.yaml || true

# Expose ports
EXPOSE 9000 8501

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:9001/api/status || exit 1

# Start supervisord
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
