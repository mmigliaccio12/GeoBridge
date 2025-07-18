import os

# Get port from environment variable (Railway sets this automatically)
bind = f"0.0.0.0:{os.environ.get('PORT', 5001)}"

# Worker configuration for better performance
workers = int(os.environ.get('GUNICORN_WORKERS', 2))
worker_class = "sync"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 100

# Logging configuration
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Security and performance
preload_app = True
keepalive = 2
timeout = 120

# For Railway deployment
forwarded_allow_ips = "*"
proxy_allow_from = "*" 