"""Self-test: serves a deliberately bad page and a good page from memory, runs the checker,
and asserts the expected FAIL/OK ids. Run: python3 tools/techseo/selftest.py"""
import http.server
import os
import sys
import threading

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from techseo import c_images, c_index, c_links, c_map, c_meta, c_perf, c_schema, c_social  # noqa: E402
from techseo.net import Fetcher  # noqa: E402
from techseo.page import Page  # noqa: E402
from techseo.report import Report  # noqa: E402

GOOD = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Lawn Mowing Quotes for Small Yards | Zzfixture Mowing</title>
<meta name="description" content="Lawn mowing quotes for small yards: priced by the size of the lawn, with the first visit booked in two minutes.">
<link rel="canonical" href="https://example.com/good"></head><body><a href="#main">Skip to content</a><header><nav><a href="/good">Home</a></nav></header>
<main id="main"><div><script type="application/ld+json">{"@context":"https://schema.org","@type":"WebPage","name":"Good","url":"https://example.com/good","description":"d"}</script></div>
<h1>Lawn mowing quotes</h1><p>%s</p><h2>Second</h2><img src="/a.png" alt="A mower" width="100" height="50"></main><footer>f</footer></body></html>""" % ("word " * 650)
BAD = """<html><head><title>x</title><meta name="robots" content="noindex"></head><body><script type="application/ld+json">{bad json</script>
<h1>One</h1><h1>Two</h1><h4>Skip</h4><a href="#">click here</a><a href="/x?utm_source=a">Read more</a><img src="/a.png"><p>lorem ipsum</p></body></html>"""


class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        body, code = {"/good": (GOOD, 200), "/bad": (BAD, 200)}.get(self.path.split("?")[0], ("nope", 404))
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode())

    do_HEAD = do_GET


def run(path, mode="prod"):
    origin = f"http://127.0.0.1:{srv.server_port}"
    rep = Report(url=origin + path, mode=mode)
    p = Page(Fetcher(origin), rep, origin + path, mode=mode)
    c_index.run_index(p)
    c_index.run_url(p)
    c_meta.run_meta(p)
    c_meta.run_content(p)
    c_links.run_links(p, check_status=False)
    c_images.run_images(p)
    c_schema.run_schema(p, "other")
    c_social.run_social(p)
    c_perf.run_perf(p)
    c_perf.run_mobile(p)
    c_map.run_js(p)
    return {(r.cid, r.level) for r in rep.results}


srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
bad, good = run("/bad"), run("/good")
expect_bad = [("IDX-03", "FAIL"), ("SCH-01", "FAIL"), ("TTL-09", "FAIL"), ("TTL-11", "FAIL"), ("LNK-06", "FAIL"), ("LNK-05", "FAIL"),
              ("LNK-04", "WARN"), ("IMG-02", "FAIL"), ("MOB-01", "FAIL"), ("CNT-01", "FAIL"), ("CNT-03", "FAIL"), ("URL-02", "FAIL")]
expect_good = [("TTL-01", "OK"), ("TTL-09", "OK"), ("TTL-11", "OK"), ("MOB-01", "OK"), ("IMG-02", "OK"), ("CNT-01", "OK"), ("SCH-14", "OK"), ("IDX-03", "OK")]
fails = [f"bad page should give {e}" for e in expect_bad if e not in bad] + [f"good page should give {e}" for e in expect_good if e not in good]
srv.shutdown()
print("selftest:", "PASS" if not fails else "FAIL\n  " + "\n  ".join(fails))
sys.exit(1 if fails else 0)
