"""Serve the page tracker on 127.0.0.1 only (port from growth.json tracker_port) with no-cache headers, so a reload always
gets the newest dashboard code and data. The dashboard's own files (html, css, js) come from the kit; the data files
(data.json, insights*.json, diffs/, report.html) come from the project's page-tracker folder. The database, logs, keys,
caches and code are never served."""
import http.server, os
import config

HIDE = (".db", ".log", "sitemap-cache.json", "config.json", ".py", ".sh", ".env")
DATA_FILES = ("data.json", "insights.json", "insights.md", "insights-digest.json", "cluster-digests.json", "cluster-notes.json", "report.html")


class NoCache(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path):
        rel = path.split("?", 1)[0].split("#", 1)[0].lstrip("/")
        base = config.DATA_DIR if (rel in DATA_FILES or rel.startswith("diffs/")) else config.CODE_DIR
        return os.path.join(base, *[p for p in rel.split("/") if p not in ("", ".", "..")])

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def send_head(self):
        if self.path.split("?", 1)[0].endswith(HIDE) or "/launchd/" in self.path or "__pycache__" in self.path:
            self.send_error(404)
            return None
        return super().send_head()

    def log_message(self, *a):
        pass  # quiet


if __name__ == "__main__":
    http.server.ThreadingHTTPServer(("127.0.0.1", config.PORT), NoCache).serve_forever()
