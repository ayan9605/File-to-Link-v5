# gunicorn.conf.py
import multiprocessing
from config import settings

# Server socket
bind = "0.0.0.0:8000"
backlog = 2048

# Worker processes
workers = settings.MAX_WORKERS
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 100
timeout = settings.WORKER_TIMEOUT
graceful_timeout = 30
keepalive = 2

# Security
limit_request_line = 4096
limit_request_fields = 100
limit_request_field_size = 8190

# Debugging
reload = False
spew = False

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# Process naming
proc_name = "filetolink_api"

# Server hooks
def pre_fork(server, worker):
    pass

def post_fork(server, worker):
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def pre_exec(server):
    server.log.info("Forked child, re-executing.")

def when_ready(server):
    server.log.info("Server is ready. Spawning workers")

def worker_int(worker):
    worker.log.info("worker received INT or QUIT signal")

def worker_abort(worker):
    worker.log.info("worker received SIGABRT signal")