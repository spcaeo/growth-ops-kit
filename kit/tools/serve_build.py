#!/usr/bin/env python3
"""Serve a built site (a production build's folder) on 127.0.0.1, so READY can run on the real build and not on a dev server.

  growth serve <dist> [--port 4173]      # foreground; stop it with Ctrl-C (or by its port)

/about answers /about/index.html or /about.html; /about/ answers /about/index.html; a missing page answers 404.html when the
build has one. Stack-neutral: any static output (Astro, Next export, Hugo, Eleventy, a hand-made folder) works. A site
that needs a server at run time (SSR) records its own production command in growth.json "preview_cmd" instead.
"""
from __future__ import annotations

import argparse
import functools
import http.server
import sys
from pathlib import Path


class Handler(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path):
        p = Path(super().translate_path(path))
        if p.is_dir() or p.exists():
            return str(p)
        if not path.split("?")[0].endswith("/") and Path(str(p) + ".html").is_file():
            return str(p) + ".html"
        return str(p)

    def send_error(self, code, message=None, explain=None):
        page = Path(self.directory) / "404.html"
        if code == 404 and page.is_file():
            body = page.read_bytes()
            self.send_response(404)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)
            return
        super().send_error(code, message, explain)

    def log_message(self, *a):
        pass


def make_server(root, port=0):
    return http.server.ThreadingHTTPServer(("127.0.0.1", port), functools.partial(Handler, directory=str(root)))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dist")
    ap.add_argument("--port", type=int, default=4173)
    a = ap.parse_args(argv)
    root = Path(a.dist).expanduser().resolve()
    if not root.is_dir():
        sys.exit(f"{root} is not a folder: build the site first (the production build, not the dev server)")
    srv = make_server(root, a.port)
    print(f"serving the build {root} on http://127.0.0.1:{srv.server_address[1]}/ (Ctrl-C stops it)", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
