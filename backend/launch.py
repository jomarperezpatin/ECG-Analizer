"""Managed loopback backend. Binds its own socket, then reports the assigned port."""
import os
import socket
import sys
import threading
import time
import uvicorn
from main import app

if __name__ == '__main__':
    if not os.environ.get('ECG_API_TOKEN'):
        raise SystemExit('ECG_API_TOKEN requerido para arranque administrado')
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('127.0.0.1', 0))
    sock.listen(128)
    print(f'ECG_PORT={sock.getsockname()[1]}', flush=True)
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', log_level='warning', access_log=False))
    def watch_parent():
        # Electron owns the write end. EOF also occurs if Electron crashes.
        sys.stdin.buffer.read()
        from bench import bench
        with bench.lock:
            job=bench.job
            if job: job['cancel'].set()
        end=time.monotonic()+4
        while job and job['state'] in ('connecting','running') and time.monotonic()<end:
            time.sleep(.1)
        server.should_exit=True
    threading.Thread(target=watch_parent, daemon=True).start()
    server.run(sockets=[sock])
