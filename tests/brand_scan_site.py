"""A made-up site for the brand-scan tests: Brightwave Studio, example.* addresses only. Pages are plain strings, so a test can serve
them from a local http.server or hand them straight to the scanner. No network."""
LIVE = "https://www.brightwave.example"

HOME = """<!doctype html><html lang="en"><head><title>Brightwave Studio | Websites that sell</title>
<meta name="description" content="Brightwave builds fast websites for local shops.">
<meta property="og:site_name" content="Brightwave Studio">
<script type="application/ld+json">{"@context":"https://schema.org","@graph":[
 {"@type":"Organization","name":"Brightwave Studio","legalName":"Brightwave Studio Pvt. Ltd.","url":"https://www.brightwave.example",
  "email":"hello@brightwave.example","telephone":"+1 202-555-0143",
  "address":{"@type":"PostalAddress","streetAddress":"12 Harbour Road","addressLocality":"Ahmedabad","postalCode":"380015","addressCountry":"IN"},
  "sameAs":["https://www.linkedin.com/company/brightwave-studio","https://x.com/brightwave_hq"],
  "contactPoint":[{"@type":"ContactPoint","contactType":"sales","email":"sales@brightwave.example"}]}]}</script></head>
<body>
<header><nav><a href="/">Home</a><a href="/about">About</a><a href="/pricing">Pricing</a><a href="/contact">Contact us</a>
<a class="btn" href="https://calendly.com/brightwave/intro-call?utm_source=site">Book a demo</a></nav></header>
<main><h1>Websites that sell</h1><p>We build websites for local shops.</p>
<a href="/book">Book a demo</a> <button data-href="/quote">Get a quote</button>
<a href="/blog/how-to-write-a-privacy-policy">How to write a privacy policy</a>
<a href="https://www.facebook.com/sharer/sharer.php?u=x">Share</a></main>
<footer><a href="/legal/terms-of-service">Terms of Service</a> <a href="https://www.brightwave.example/privacy-policy">Privacy Policy</a>
<a href="https://www.linkedin.com/company/brightwave-studio">LinkedIn</a> <a href="https://github.com/brightwave-studio">GitHub</a>
<a href="https://www.instagram.com/brightwave.studio/">Instagram</a> <a href="https://www.youtube.com/@brightwavestudio">YouTube</a>
<a href="https://twitter.com/intent/tweet?text=hi">Tweet</a>
<p>&copy; 2026 Brightwave Studio. All rights reserved.</p></footer></body></html>"""

CONTACT = """<html><head><title>Contact</title></head><body><header><a href="/book">Book a demo</a></header><main><h1>Contact us</h1>
<p>Write to <a href="mailto:support@brightwave.example?subject=Help">support@brightwave.example</a> or sales [at] brightwave [dot] example.
Press: <a href="mailto:press@partner-news.example">press@partner-news.example</a>. Careers: jobs(at)brightwave.example</p>
<p>Call us: +1 (202) 555-0143. Fax: +1 202-555-0188. Updated 2026-11-02 and LOGO2X is an image name, not an email.</p>
<address>Brightwave Studio Pvt. Ltd., 12 Harbour Road, Suite 4, Ahmedabad 380015, India</address>
<span class="__cf_email__" data-cfemail="CFEMAIL">[email&#160;protected]</span>
</main></body></html>"""

TERMS = """<html><head><title>Terms of Service</title></head><body><main><h1>Terms of Service</h1>
<p>Last updated: November 3, 2025</p>
<p>These Terms of Service are provided by Brightwave Studio Pvt. Ltd. ("Company"), 12 Harbour Road, Suite 4, Ahmedabad 380015, India.</p>
<p>These terms are governed by the laws of the State of Delaware, without regard to conflict of law rules. Any dispute is subject to the exclusive jurisdiction of the courts in Wilmington, Delaware.</p>
<p>We follow the GDPR and CCPA. Questions: <a href="mailto:legal@brightwave.example">legal@brightwave.example</a></p></main></body></html>"""

PRIVACY = """<html><head><title>Privacy Policy</title></head><body><main><h1>Privacy Policy</h1>
<p>Effective date: 1 March 2026. Brightwave Studio Pvt. Ltd. is the controller of your data and also complies with HIPAA where it applies.</p>
<p>Our Data Protection Officer can be reached at privacy@brightwave.example for any request.</p></main></body></html>"""

ABOUT = """<html><head><title>About</title></head><body><main><h1>About Brightwave</h1><p>Founded in 2016 in Ahmedabad.</p>
<a href="/book">Book a demo</a></main></body></html>"""

BOOK = """<html><head><title>Book a demo</title></head><body><main><h1>Book a demo</h1>
<iframe src="https://calendly.com/brightwave/intro-call"></iframe>
<script>Calendly.initPopupWidget({url: 'https://cal.com/brightwave/30min'});</script>
<a href="https://calendly.com/pricing">Powered by Calendly</a></main></body></html>"""

LLMS = """# Brightwave Studio

> Brightwave builds fast websites for local shops and keeps them fast.

We are a small studio in Ahmedabad.

## Services
- [Website build](https://www.brightwave.example/services/build): A new site in four weeks
- [Care plans](https://www.brightwave.example/services/care): Monthly updates

## Company
- [About](https://www.brightwave.example/about)
"""

LLMS_FULL = "# Brightwave Studio\n\n## Services\n\nWe build sites.\n\n## Company\n\nSmall studio.\n"

SITEMAP = """<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url><loc>https://www.brightwave.example/</loc></url><url><loc>https://www.brightwave.example/about</loc></url>
<url><loc>https://www.brightwave.example/contact</loc></url><url><loc>https://www.brightwave.example/book</loc></url>
<url><loc>https://www.brightwave.example/pricing</loc></url><url><loc>https://www.brightwave.example/legal/terms-of-service</loc></url>
<url><loc>https://www.brightwave.example/privacy-policy</loc></url>
<url><loc>https://www.brightwave.example/blog/how-to-write-a-privacy-policy</loc></url></urlset>"""


def cf_email(addr: str, key: int = 0x2B) -> str:
    return f"{key:02x}" + "".join(f"{ord(ch) ^ key:02x}" for ch in addr)


def pages() -> dict[str, tuple[int, str]]:
    """{path: (status, body)}; every path not listed answers 404."""
    return {
        "/": (200, HOME), "/contact": (200, CONTACT.replace("CFEMAIL", cf_email("billing@brightwave.example")).replace("LOGO2X", "logo" + "@2x.png")),
        "/legal/terms-of-service": (200, TERMS), "/privacy-policy": (200, PRIVACY), "/about": (200, ABOUT), "/book": (200, BOOK),
        "/pricing": (200, "<html><body><main><h1>Pricing</h1><a href='/book'>Book a demo</a></main></body></html>"),
        "/llms.txt": (200, LLMS), "/llms-full.txt": (200, LLMS_FULL), "/sitemap.xml": (200, SITEMAP),
        "/robots.txt": (200, "User-agent: *\nAllow: /\nSitemap: https://www.brightwave.example/sitemap.xml\n"),
    }
