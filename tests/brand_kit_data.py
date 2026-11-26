"""Recorded computed-style data for the brand-kit tests: what snapshot.py returns for a made-up site (Brightwave Studio, example.*
addresses). Plain dicts, so the extraction runs with no browser."""
import copy

BASE = "http://127.0.0.1:9"

REST = {"bg": [11, 110, 79, 1], "color": [255, 255, 255, 1], "border": None, "radius": 8, "padding": [12, 24, 12, 24], "size": 16, "weight": 600,
        "shadow": "", "family": "Inter", "transform": "none", "height": 44}
HOVER = {"bg": [9, 95, 68, 1], "color": [255, 255, 255, 1], "border": None, "radius": 8, "shadow": "", "deco": "none", "weight": 600, "outline": None, "transform": ""}
FOCUS = {**HOVER, "bg": [11, 110, 79, 1], "outline": [[11, 110, 79, 1], 2, 2]}


def snapshot(url=BASE + "/", **over):
    s = {
        "url": url, "title": "Brightwave Studio", "width": 1366, "height": 3000, "pageBg": [250, 250, 247, 1],
        "bg": [{"c": [250, 250, 247, 1], "w": 500000, "tags": {"body": 1}}, {"c": [238, 242, 240, 1], "w": 200000, "tags": {"section": 2}},
               {"c": [11, 110, 79, 1], "w": 30000, "tags": {"a": 3}}, {"c": [12, 111, 80, 1], "w": 1000, "tags": {"a": 1}}],
        "text": [{"c": [26, 32, 29, 1], "w": 9000, "on": []}, {"c": [96, 108, 102, 1], "w": 2500, "on": []}, {"c": [255, 255, 255, 1], "w": 600, "on": []}],
        "link": [{"c": [11, 110, 79, 1], "w": 800}], "border": [{"c": [215, 221, 217, 1], "w": 3000}, {"c": [11, 110, 79, 1], "w": 200}],
        "fonts": [{"family": '"Inter", system-ui, sans-serif', "weight": 400, "w": 8000}, {"family": '"Inter", system-ui, sans-serif', "weight": 600, "w": 1500},
                  {"family": '"Fraunces", Georgia, serif', "weight": 700, "w": 600}, {"family": "ui-monospace, Menlo, monospace", "weight": 400, "w": 50}],
        "type": {"h1": {"size": 48, "lh": 56, "weight": 700, "family": '"Fraunces", Georgia, serif', "ls": -0.5, "color": [26, 32, 29, 1], "transform": "none"},
                 "h2": {"size": 32, "lh": 40, "weight": 700, "family": '"Fraunces", Georgia, serif', "ls": 0, "color": [26, 32, 29, 1], "transform": "none"},
                 "h3": {"size": 22, "lh": 30, "weight": 600, "family": '"Inter", system-ui, sans-serif', "ls": 0, "color": [26, 32, 29, 1], "transform": "none"},
                 "body": {"size": 16, "lh": 24, "weight": 400, "family": '"Inter", system-ui, sans-serif', "ls": 0, "color": [26, 32, 29, 1], "transform": "none"},
                 "small": {"size": 13, "lh": 18, "weight": 400, "family": '"Inter", system-ui, sans-serif', "ls": 0, "color": [96, 108, 102, 1], "transform": "none"}},
        "radius": [{"px": 8, "n": 20, "big": 2}, {"px": 16, "n": 6, "big": 6}, {"px": 999, "n": 3, "big": 0}],
        "shadow": [{"v": "rgba(0, 0, 0, 0.1) 0px 4px 12px 0px", "n": 5}, {"v": "rgba(0, 0, 0, 0.2) 0px 12px 32px 0px", "n": 2}, {"v": "rgba(0, 0, 0, 0.05) 0px 1px 2px 0px", "n": 9}],
        "space": [{"px": 8, "n": 100}, {"px": 16, "n": 120}, {"px": 24, "n": 60}, {"px": 32, "n": 40}, {"px": 4, "n": 30}, {"px": 48, "n": 20}, {"px": 13, "n": 4}],
        "sizes": [], "links": [{"idx": 0, "color": [11, 110, 79, 1], "deco": "underline", "weight": 400, "n": 5,
                               "hover": {"bg": [0, 0, 0, 0], "color": [9, 95, 68, 1], "deco": "underline", "weight": 400, "outline": None, "shadow": "", "transform": "", "border": None, "radius": 0}}],
        "buttons": [
            {"idx": 0, "text": "Book a demo", "texts": ["Book a demo"], "tag": "a", "region": "header", "n": 4, "main": True, "rest": copy.deepcopy(REST), "hover": copy.deepcopy(HOVER), "focus": copy.deepcopy(FOCUS)},
            {"idx": 1, "text": "See pricing", "texts": ["See pricing"], "tag": "a", "region": "main", "n": 2, "main": True,
             "rest": {**REST, "bg": None, "color": [11, 110, 79, 1], "border": [[11, 110, 79, 1], 1, "solid"], "height": 44},
             "hover": {**HOVER, "bg": [238, 242, 240, 1], "color": [11, 110, 79, 1]}, "focus": None},
            {"idx": 2, "text": "Subscribe", "texts": ["Subscribe"], "tag": "button", "region": "footer", "n": 1, "main": False, "rest": {**REST, "bg": [200, 200, 200, 1], "color": [0, 0, 0, 1]},
             "hover": None, "focus": None}],
        "logo": {"kind": "img", "src": BASE + "/img/logo.svg", "alt": "Brightwave", "width": 120, "height": 32, "href": "/", "svg": "", "bg": [250, 250, 247, 1]},
        "icons": [{"rel": "icon", "href": BASE + "/favicon.svg", "sizes": "", "type": "image/svg+xml"}, {"rel": "apple-touch-icon", "href": BASE + "/apple.png", "sizes": "180x180", "type": ""}],
        "meta": {"theme-color": "#0B6E4F", "og:image": "https://cdn.brightwave.example/og.png", "og:site_name": "Brightwave Studio", "description": "Websites for local shops."},
        "vars": {"--brand": "#0b6e4f", "--accent": "#e8a33d", "--success": "#1f8a4c", "--danger": "#c0392b"},
        "varColors": {"--brand": [11, 110, 79, 1], "--accent": [232, 163, 61, 1], "--success": [31, 138, 76, 1], "--danger": [192, 57, 43, 1]},
    }
    s.update(over)
    return s


def second_page():
    return snapshot(BASE + "/about", logo=None, title="About")
