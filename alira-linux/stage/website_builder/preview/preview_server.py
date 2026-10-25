# -*- coding: utf-8 -*-
"""ALIRA WebForge — Local Preview Server"""

import http.server, os, socketserver, threading, webbrowser
from pathlib import Path

_active_servers = {}


def _find_free_port(start=8000, end=8100) -> int:
    import socket
    for port in range(start, end):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("", port)); return port
        except OSError:
            continue
    return 8080


def start_preview(project_dir: Path, project_name: str) -> str:
    stop_preview(project_name)
    port     = _find_free_port()
    orig_dir = os.getcwd()

    class Handler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass

    def _serve():
        os.chdir(project_dir)
        with socketserver.TCPServer(("", port), Handler) as httpd:
            _active_servers[project_name] = httpd
            httpd.serve_forever()
        os.chdir(orig_dir)

    threading.Thread(target=_serve, daemon=True).start()
    url = f"http://localhost:{port}"
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    print(f"[Preview] {url}")
    return url


def stop_preview(project_name: str):
    if project_name in _active_servers:
        try: _active_servers[project_name].shutdown()
        except: pass
        del _active_servers[project_name]