#!/usr/bin/env python3
"""Serve the demo site on 127.0.0.1 with clean addresses (/lawn-mowing answers from lawn-mowing.html), using only Python's
http.server. Used by the demo test and by hand:  python3 serve.py 3801   then   growth gate page /lawn-mowing --url http://127.0.0.1:3801/lawn-mowing ..."""
import functools
import http.server
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parent / "site"


class Clean(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path):
        p = super().translate_path(path)
        clean = path.split("?", 1)[0]
        if Path(p + ".html").is_file() and (not Path(p).exists() or (Path(p).is_dir() and not clean.endswith("/"))):
            return p + ".html"
        return p

    def guess_type(self, path):
        t = super().guess_type(path)
        return t + "; charset=utf-8" if t in ("text/html", "text/css", "application/javascript", "text/plain") else t

    def log_message(self, *a):
        pass


def make_server(port=0):
    handler = functools.partial(Clean, directory=str(SITE))
    return http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)


if __name__ == "__main__":
    srv = make_server(int(sys.argv[1]) if len(sys.argv) > 1 else 3801)
    print(f"demo site on http://127.0.0.1:{srv.server_address[1]}/ (Ctrl+C to stop)")
    srv.serve_forever()
