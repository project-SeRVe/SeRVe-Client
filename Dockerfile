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
    /app/SeRVe-Client \
    /var/log/edge-server \
    /var/log/suricata \
    /var/log/supervisor \
    /var/log/nginx \
    /etc/suricata/rules \
    /app/local_vectorstore

# Set working directory
WORKDIR /app

# Copy SeRVe-Client code (serve_sdk, vision_engine, app.py)
COPY SeRVe-Client /app/SeRVe-Client

# Copy edge server source code
COPY edge-server/src/ /app/src/

# Copy configuration files
COPY edge-server/supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY edge-server/nginx.conf /etc/nginx/nginx.conf
COPY edge-server/suricata/custom.rules /etc/suricata/rules/custom.rules

# Create requirements.txt for edge server
RUN echo "fastapi>=0.104.0" > /app/requirements.txt && \
    echo "uvicorn[standard]>=0.24.0" >> /app/requirements.txt && \
    echo "pydantic>=2.0.0" >> /app/requirements.txt && \
    echo "requests>=2.31.0" >> /app/requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r /app/requirements.txt
RUN pip install --no-cache-dir -r /app/SeRVe-Client/requirements.txt

# Configure Suricata
RUN suricata-update && \
    echo "include: /etc/suricata/rules/custom.rules" >> /etc/suricata/suricata.yaml

# Configure Suricata to monitor loopback interface
RUN sed -i 's/interface: eth0/interface: lo/g' /etc/suricata/suricata.yaml || true

# Expose ports
# 9000: Robot data ingress (nginx → Suricata → FastAPI)
# 8501: Streamlit dashboard
EXPOSE 9000 8501

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:9001/api/status || exit 1

# Start supervisord (manages Suricata, FastAPI, Streamlit, Nginx)
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
