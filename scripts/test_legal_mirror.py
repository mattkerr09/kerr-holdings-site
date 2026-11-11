#!/usr/bin/env python3
"""Offline checks with a streaming text oracle independent of the builder tree."""

import difflib
from collections import Counter
from contextlib import redirect_stderr
import hashlib
from html.parser import HTMLParser
import io
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urljoin, urlsplit
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True
import legal_mirror as mirror


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "data/legal-sources-2026-11-11"
HASHES = {
    "checkengine-legal-index.html": "51b059552c9bf6010c00b4c0ff1acdb312455b6cee14cd20f7077d1a35928012",
    "checkengine-privacy.html": "90ecec5962d3ff79b5174aee5070154432369fb7b7ef0397db6a9dc02e9e1011",
    "checkengine-refunds.html": "8b5f48dfc5de440bd4220413cb95c049f9acb24eb668e619e4605fdf8503ff74",
    "checkengine-terms.html": "0eaa38f0910eef7f1a26de262a71787b5c0d1b8243db2d94aad39fe109eb21e8",
    "crisp-legal-index.html": "5ebeb8579e75c6b7fdac390ccb1f329808542536caf6da8baa86a80f76da0e04",
    "crisp-privacy.html": "35bcc945087f14f60c3ee721cae66bb3354407fdfa76a5495a4ea3d8a52f1527",
    "crisp-refunds.html": "a48fc22436bdf9f94213390e9475d79e6f38ceef3f1ceb2fbfab595eaf6b0431",
    "crisp-terms.html": "c725d1b2df4a649da4e4a63172ca7850266d97ec4f3ef1f8710b2b27d6128d57",
    "outlier-privacy.html": "b4f0f5d606463260288d1eeb2ab27a7c5b35c1f55f535581a62806c90b4d9b15",
    "outlier-terms.html": "caea72ef8361baea109d26343dc707acfda96cc2c718d2bb87a2f1a4a28bfaca",
    "read-at.txt": "5896384a4043850987a238f917e5ef44a602273c894052bf340295428326ab7e",
}
# Independent domain list: other Kerr sites and worker hosts require nofollow.
DOMAINS = {
    "crispvideo.app", "outlier.host", "checkengineseo.com", "docketseo.app",
    "matthewkerr.dev", "builtbykerr.com",
    "adplaybook.app", "kerrco.workers.dev",
}
SOURCE_FILES = {
    "crisp": ["crisp-terms.html", "crisp-privacy.html", "crisp-refunds.html"],
    "outlier": ["outlier-terms.html", "outlier-privacy.html"],
    "check-engine": ["checkengine-terms.html", "checkengine-privacy.html", "checkengine-refunds.html"],
}
VOID = set("area base br col embed hr img input link meta param source track wbr".split())
BLOCK = set((
    "html body main article section div p h1 h2 h3 h4 h5 h6 ul ol li dl dt dd "
    "table caption thead tbody tfoot tr th td pre blockquote br hr header footer nav aside"
).split())
STRUCTURE = set("h1 h2 h3 h4 h5 h6 p ul ol li dl dt dd table caption colgroup col thead tbody tfoot tr th td".split())


class Audit(HTMLParser):
    """Read visible text, links and structure, optionally within one saved section."""

    def __init__(self, html, source=False, filename=None, authored=False, attribution=False):
        super().__init__(convert_charrefs=True)
        self.source = source
        self.filename = filename
        self.authored = authored
        self.attribution = attribution
        self.stack = []
        self.parts = []
        self.links = []
        self.structure = []
        self.elements = []
        self.feed(html)
        self.close()
        self.text = " ".join("".join(self.parts).split())

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = set(attrs.get("class", "").split())
        parent = self.stack[-1] if self.stack else None
        skipped = bool(parent and parent[2])
        skipped |= tag in {"head", "script", "style", "svg", "form", "button", "img", "picture", "input", "select", "textarea", "iframe"}
        skipped |= "hidden" in attrs or attrs.get("aria-hidden") == "true"
        if self.source:
            skipped |= tag in {"header", "footer", "nav"}
            # Only the identified product navigation and sales/subscription chrome.
            skipped |= bool(classes & {"crumb", "back", "pbox", "cta", "sublist", "foot"})
            skipped |= "data-founding" in attrs
        if self.authored:
            skipped |= "mirrored-text" in classes
        section = attrs.get("data-source") or (parent[4] if parent else None)
        selected = bool(parent and parent[3])
        if self.filename:
            marker = "source" if self.attribution else "mirrored-text"
            selected |= marker in classes and section == self.filename
        else:
            selected = True
        state = (tag, attrs, skipped, selected, section)
        if tag not in VOID:
            self.stack.append(state)
        if not skipped and selected:
            self.elements.append((tag, attrs))
            if tag in BLOCK:
                self.parts.append(" ")
            if tag in STRUCTURE:
                self.structure.append(tag)
            if tag == "a":
                self.links.append(attrs)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                _, _, skipped, selected, _ = self.stack[index]
                if not skipped and selected and tag in BLOCK:
                    self.parts.append(" ")
                del self.stack[index:]
                break

    def handle_data(self, data):
        if self.stack and not self.stack[-1][2] and self.stack[-1][3]:
            self.parts.append(data)


def is_kerr(href, base=mirror.SITE):
    if href.lower().startswith("mailto:"):
        return False
    host = (urlsplit(urljoin(base, href)).hostname or "").lower().rstrip(".")
    return any(host == domain or host.endswith("." + domain) for domain in DOMAINS)


def assert_words(case, expected, actual, label):
    if expected != actual:
        diff = "\n".join(difflib.unified_diff(
            expected.split(), actual.split(), fromfile=label + " source",
            tofile=label + " mirror", lineterm="",
        ))
        case.fail("Visible text differs:\n" + diff)


class LegalMirrors(unittest.TestCase):
    def test_evidence_unchanged(self):
        self.assertEqual({p.name for p in EVIDENCE.iterdir()}, set(HASHES))
        for filename, digest in HASHES.items():
            with self.subTest(source=filename):
                self.assertEqual(hashlib.sha256((EVIDENCE / filename).read_bytes()).hexdigest(), digest)

    def test_words_structure_links_and_provenance(self):
        for slug, filenames in SOURCE_FILES.items():
            html = (ROOT / f"legal/{slug}/index.html").read_text(encoding="utf-8")
            self.assertEqual(re.findall(r'<section data-source="([^"]+)"', html), filenames)
            page_en = page_em = 0
            for filename in filenames:
                with self.subTest(page=slug, source=filename):
                    raw = (EVIDENCE / filename).read_text(encoding="utf-8")
                    expected = Audit(raw, source=True)
                    actual = Audit(html, filename=filename)
                    assert_words(self, expected.text, actual.text, filename)
                    demoted = [f"h{int(tag[1]) + 1}" if re.fullmatch("h[1-6]", tag) else tag
                               for tag in expected.structure]
                    self.assertEqual(actual.structure, demoted)
                    source_url, start, end = re.search(
                        r"source: (\S+) ; read \S+ between (\S+) and (\S+) ;", raw.splitlines()[0],
                    ).groups()
                    source_links = [link["href"] if link["href"].startswith("mailto:")
                                    else urljoin(source_url, link["href"]) for link in expected.links]
                    self.assertEqual([a["href"] for a in actual.links], source_links)
                    attribution = Audit(html, filename=filename, attribution=True)
                    self.assertIn("Mirrored from " + source_url, attribution.text)
                    self.assertIn("read between 11 November 2026 at 13:59:48 UTC and 11 November 2026 at 14:00:17 UTC", attribution.text)
                    self.assertIn("If this copy and the product's own page ever differ, the product's page governs.", attribution.text)
                    self.assertEqual([attrs["datetime"] for tag, attrs in attribution.elements if tag == "time"], [start, end])
                    self.assertLess(html.index('class="source"', html.index(f'data-source="{filename}"')),
                                    html.index('<h2>', html.index(f'data-source="{filename}"')))
                    words = len(actual.text.split())
                    self.assertGreater(words, 0)
                    print(f"/{'legal/' + slug}/ {filename}: source {len(expected.text.split())} words; mirror {words} words; {source_url}")
                    page_en += actual.text.count("\u2013")
                    page_em += actual.text.count("\u2014")
                    self.assertFalse(any(tag in {"script", "form", "button", "img"} for tag, _ in actual.elements))
            print(f"/legal/{slug}/ source dashes: en={page_en}, em={page_em}")
            if slug == "outlier":
                self.assertIn('Outlier has no separate refund page. Its refund wording is in the "Payment + refunds" section of its terms above.', Audit(html, authored=True).text)
                self.assertIn("Payment + refunds", Audit(html, filename="outlier-terms.html").text)

    def test_pages_links_metadata_and_authored_copy(self):
        def shell_anchors(html):
            before, rest = html.split('<main id="main">', 1)
            _, after = rest.split('</main>', 1)
            # Legal pages already omit the offer bar, outside the header and menu.
            before = re.sub(r'<div class="offer">.*?</div>\n', "", before)
            return re.findall(r'<a\b[^>]*>.*?</a>', before + after, flags=re.S)

        shell = (ROOT / "privacy/index.html").read_text(encoding="utf-8")
        for slug in [None, *SOURCE_FILES]:
            route = "/legal/" + (slug + "/" if slug else "")
            html = (ROOT / (route.strip("/") + "/index.html")).read_text(encoding="utf-8")
            audit = Audit(html)
            pairs = Counter()
            for link in audit.links:
                url = urlsplit(urljoin(mirror.SITE + route, link["href"]))
                host = (url.hostname or url.scheme).lower().rstrip(".")
                nofollow = "nofollow" in link.get("rel", "").lower().split()
                pairs[host, nofollow] += 1
                if host == "kerrandcompanyholdings.com":
                    self.assertFalse(nofollow, (route, link))
                if is_kerr(link["href"]):
                    self.assertTrue(nofollow, (route, link))
            print(f"{route} link pairs (host, nofollow):")
            for (host, nofollow), count in sorted(pairs.items()):
                print(f"  ({host}, {nofollow}): {count}")
            self.assertEqual(shell_anchors(html), shell_anchors(shell), route)
            robots = re.findall(r'<meta name="robots" content="([^"]+)">', html)
            self.assertEqual(robots, ["noindex, follow" if slug else "index,follow"])
            self.assertIn(f'<link rel="canonical" href="{mirror.SITE + route}">', html)
            self.assertEqual(sum(tag == "h1" for tag, _ in audit.elements), 1)
            self.assertIn('src="https://plausible.io/js/pa-ghRhArMvH76L24u8nWrRp.js"', html)
            self.assertIn('<link rel="stylesheet" href="/assets/site.css">', html)
            authored = Audit(html, authored=True).text
            self.assertNotRegex(authored, "[\u2013\u2014]")
            self.assertNotRegex(authored, r"(?i)Black Friday|% off|half price")
            self.assertIn("Kerr & Company LLC is a small software company in Grand Rapids, Michigan.", authored)
            self.assertNotIn('class="offer"', html)
            main = html.split('<main id="main">')[1].split('</main>')[0]
            self.assertNotRegex(Audit(main, authored=True).text, r"(?i)\bbuy\b|\$\d")
            self.assertNotIn("<button", main)
            # Metadata is also written copy and must not inherit a sales description.
            head = html.split("</head>")[0]
            self.assertNotRegex(head, "[\u2013\u2014]")
            self.assertNotRegex(head, r"(?i)Black Friday|% off|half price|\bbuy\b|\$\d")

    def test_index_text(self):
        html = (ROOT / "legal/index.html").read_text(encoding="utf-8")
        body = html.split('<div class="wrap doc">')[1].split("</main>")[0]
        expected = [
            ("/legal/site-terms/", "Site terms: Terms for using this company website."),
            ("/privacy/", "Site privacy: What the company website collects and who sees it."),
            ("/security/", "Security: How to report a security problem with our websites or apps."),
            ("/terms/", "Post Desk terms: Terms for using Post Desk."),
            ("/about/", "Company details: Who Kerr & Company LLC is and how to contact us."),
            ("/legal/crisp/", "Crisp legal mirror: Crisp's terms, privacy policy and refund policy."),
            ("/legal/outlier/", "Outlier legal mirror: Outlier's terms and privacy policy, with refunds in its terms."),
            ("/legal/check-engine/", "Check Engine legal mirror: Check Engine's terms, privacy policy and refund policy."),
        ]
        self.assertEqual([a["href"] for a in Audit(body).links], [route for route, _ in expected])
        self.assertEqual(Audit(body).text, " ".join(line for _, line in expected))
        print("/legal/ index lines:")
        for route, line in expected:
            print(f"  {line} [{route}]")

    def test_sitemap_only_adds_approved_legal_pages(self):
        raw = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
        ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        entries = ET.fromstring(raw).findall("s:url", ns)
        legal = [entry for entry in entries if entry.findtext("s:loc", namespaces=ns) == mirror.SITE + "/legal/"]
        self.assertEqual(len(legal), 1)
        self.assertEqual(legal[0].findtext("s:lastmod", namespaces=ns), "2026-11-11")
        for slug in SOURCE_FILES:
            self.assertNotIn(mirror.SITE + f"/legal/{slug}/", raw)
        baseline, removed = re.subn(
            r"  <url>\n    <loc>https://kerrandcompanyholdings.com/(?:legal/|legal/site-terms/|security/)</loc>\n.*?  </url>\n",
            "", raw, flags=re.S,
        )
        self.assertEqual(removed, 3)
        # SHA-256 of sitemap.xml at job base 2a716c9, including whitespace.
        self.assertEqual(hashlib.sha256(baseline.encode()).hexdigest(),
                         "a773a657a1c3f6e919f11ab72e3c8e6ef7e2a23647cfce53b8c2dde4200ce1c5")

    def test_preserves_tables_and_resolves_links(self):
        source = '''<article><h1>Terms</h1><p>A<strong>bold</strong> word.</p>
<h2>Details</h2><table><caption>Seats</caption><thead><tr><th scope="col">App</th></tr></thead>
<tbody><tr><td colspan="2">Crisp &amp; Outlier</td></tr></tbody></table><ol start="2"><li>Keep this</li></ol>
<p><a href="../privacy/">Privacy</a><a href="//mcp.outlier.host/">Helper</a>
<a href="https://kerr-affiliate-hub.kerrco.workers.dev/">Worker</a>
<a href="https://crispvideo.app.example.org/">Other</a><a href="mailto:a@crispvideo.app">Email</a>
<a href="#details">Details</a></p><aside class="pbox"><p>Sales</p></aside>
<script>no()</script><form><p>Subscribe</p></form><button>Go</button><img src="x"></article>'''
        base = "https://crispvideo.app/legal/terms/"
        html = mirror.mirror_node(mirror.Tree(source).root, base)
        assert_words(self, Audit(source, source=True).text, Audit(html).text, "table fixture")
        self.assertIn('<th scope="col">', html)
        self.assertIn('<td colspan="2">', html)
        self.assertIn('<ol start="2">', html)
        self.assertIn('<h2>Terms</h2>', html)
        self.assertIn('<h3>Details</h3>', html)
        self.assertEqual([a["href"] for a in Audit(html).links], [
            "https://crispvideo.app/legal/privacy/", "https://mcp.outlier.host/",
            "https://kerr-affiliate-hub.kerrco.workers.dev/", "https://crispvideo.app.example.org/",
            "mailto:a@crispvideo.app", base + "#details",
        ])
        for a in Audit(html).links:
            self.assertEqual("nofollow" in a.get("rel", "").split(), is_kerr(a["href"]))
        self.assertNotRegex(html, r"<(script|form|button|img)\b")

    def test_company_links_and_other_rel_tokens(self):
        for href in ["/privacy/", "#main", "https://kerrandcompanyholdings.com/legal/"]:
            with self.subTest(href=href):
                attrs = mirror.link_attrs({"href": href, "rel": "noopener nofollow"}, mirror.SITE)
                self.assertEqual(attrs["rel"], "noopener")
                attrs = mirror.link_attrs({"href": href, "rel": "nofollow"}, mirror.SITE)
                self.assertNotIn("rel", attrs)
        for host in sorted(DOMAINS):
            attrs = mirror.link_attrs({"href": f"https://{host}/", "rel": "noopener"}, mirror.SITE)
            self.assertEqual(attrs["rel"], "noopener nofollow")
        for host in ["dodopayments.com", "polar.sh", "cloudflare.com"]:
            attrs = {"href": f"https://{host}/", "rel": "noopener"}
            self.assertEqual(mirror.link_attrs(attrs, mirror.SITE), attrs)

    def test_check_and_drift_detection(self):
        result = subprocess.run([sys.executable, str(ROOT / "scripts/legal_mirror.py"), "--check"],
                                cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        # Confirm --check fails on a changed page and never repairs it.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "legal/index.html"
            target.parent.mkdir()
            target.write_text("hand edit", encoding="utf-8")
            error = io.StringIO()
            with patch.object(mirror, "ROOT", root), patch.object(mirror, "build_pages", return_value={"legal/index.html": "expected"}), redirect_stderr(error):
                self.assertEqual(mirror.main(["--check"]), 1)
            self.assertIn("DRIFT: legal/index.html", error.getvalue())
            self.assertEqual(target.read_text(encoding="utf-8"), "hand edit")


if __name__ == "__main__":
    unittest.main(verbosity=2)
