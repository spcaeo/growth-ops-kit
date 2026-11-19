"""Setup detects the stack, sitemap shape, trailing-slash form, language copies, redirects and content folders (#35)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import detect  # noqa: E402
from wizard_helpers import make_site  # noqa: E402


def test_detects_an_astro_repo_with_redirects_and_content_folders(tmp_path):
    repo, _ = make_site(tmp_path)
    s = detect.detect_stack(repo)
    assert s["framework"] == "astro" and s["stack"] == "static" and s["build_cmd"] == "npm run build" and s["preview_cmd"] == "npm run preview"
    lay = detect.detect_layout(repo)
    assert lay["redirects"] == ["public/_redirects"] and "src/content" in lay["content_dirs"]


def test_detects_nextjs_hugo_and_nothing(tmp_path):
    (tmp_path / "a").mkdir(); (tmp_path / "a" / "next.config.mjs").write_text("export default {}")
    assert detect.detect_stack(tmp_path / "a")["stack"] == "nextjs"
    (tmp_path / "b").mkdir(); (tmp_path / "b" / "hugo.toml").write_text("")
    assert detect.detect_stack(tmp_path / "b")["framework"] == "hugo"
    (tmp_path / "c").mkdir()
    assert detect.detect_stack(tmp_path / "c") == {}


def test_sitemap_index_slash_form_and_language_copy(tmp_path):
    _, index = make_site(tmp_path)
    sm = detect.detect_sitemap(str(index))
    assert sm == {"shape": "index", "children": 2, "pages": 5, "trailing_slash": "slash", "languages": ["en-us"], "hreflang": True}


def test_plain_urlset_without_slashes(tmp_path):
    f = tmp_path / "s.xml"
    f.write_text('<urlset><url><loc>https://x.example/a</loc></url><url><loc>https://x.example/b/c</loc></url></urlset>')
    sm = detect.detect_sitemap(str(f))
    assert sm["shape"] == "urlset" and sm["trailing_slash"] == "no-slash" and sm["languages"] == [] and sm["hreflang"] is False
    f.write_text('<urlset><url><loc>https://x.example/a</loc></url><url><loc>https://x.example/b/</loc></url></urlset>')
    assert detect.detect_sitemap(str(f))["trailing_slash"] == "mixed"


def test_unreadable_sitemap_is_reported_not_raised(tmp_path):
    out = detect.detect_all(None, str(tmp_path / "nope.xml"), get=lambda u: (404, ""))
    assert "sitemap_error" in out


def test_cli_prints_json(tmp_path):
    from wizard_helpers import growth
    repo, index = make_site(tmp_path)
    r = growth(tmp_path, "detect", "--repo", str(repo), "--sitemap", str(index))
    data = json.loads(r.stdout)
    assert data["stack"]["framework"] == "astro" and data["sitemap"]["children"] == 2
