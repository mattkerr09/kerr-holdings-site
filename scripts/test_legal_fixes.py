#!/usr/bin/env python3
"""Offline regression checks for the CEO's 11 November 2026 legal fixes."""

from contextlib import redirect_stdout
from html import unescape
import importlib.util
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True
from test_legal_mirror import Audit
import legal_mirror as mirror


ROOT = Path(__file__).resolve().parents[1]
BASE = "c96ed46"
SITE = "https://kerrandcompanyholdings.com"
OLD_NAME = "Do" + "cket"
OLD_URL = "https://" + "doc" + "ketseo.app/"
NEW_URL = "https://checkengineseo.com/"
ALLOWED = (
    "index.html", "about/index.html", "privacy/index.html", "affiliates/index.html",
    "post-desk/index.html", "terms/index.html", "404.html", "llms.txt",
    "legal/index.html", "legal/site-terms/index.html", "legal/terms.html",
    "legal/privacy.html", "security/index.html", ".well-known/security.txt",
    "scripts/build-redirects.py", "scripts/legal_mirror.py",
    "scripts/test_legal_mirror.py", "scripts/test_legal_fixes.py", "sitemap.xml",
)
# Each substantive paragraph, followed by its saved source clause and an excerpt.
# Paragraph 2 also applies the company-information scope required by job item 4.
# Paragraph 8 is the update date described by Outlier's Changes clause.
SOURCES = {
    1: ("crisp-terms.html", "Quick answer", "These terms govern your use of the Crisp application"),
    2: ("checkengine-terms.html", "Opening agreement", "By downloading or using Check Engine you agree to these terms."),
    3: ("crisp-terms.html", "6. No warranty", 'Crisp is provided "as is" and "as available"'),
    4: ("crisp-terms.html", "7. Limitation of liability", "limited to the amount you actually paid for it."),
    5: ("outlier-terms.html", "Governing law", "state or federal courts located in Kent County, Michigan."),
    6: ("outlier-terms.html", "Changes", 'Continued use after a material change means you accept the updated terms.'),
    7: ("crisp-terms.html", "12. Contact", "support@crispvideo.app"),
    8: ("outlier-terms.html", "Changes", 'bump the "Last updated" date.'),
}
TERMS_PARAGRAPHS = (
    "These terms govern your use of kerrandcompanyholdings.com. The website is run by Kerr & Company LLC, a Michigan limited liability company in Grand Rapids.",
    "This website provides company information. Each app has its own terms. You can find those terms on our legal page.",
    'This website is provided "as is" and "as available", without any express or implied warranty. This includes warranties of fitness for a particular purpose and non-infringement.',
    "To the extent the law allows, Kerr & Company LLC is not liable for indirect or consequential losses, or loss of data, profits or revenue, arising from your use of this website. Our total liability for any claim about this website is limited to the amount you paid to use it.",
    "These terms are governed by the laws of the State of Michigan, United States. Disputes will be resolved in the state or federal courts in Kent County, Michigan.",
    "If we make a major change to these terms, we will note it here and update the date below. If you keep using this website after that change, you accept the updated terms.",
    "If you have questions about these terms, email matthew@kerrandcompanyholdings.com.",
    "Last updated 11 November 2026.",
)


def baseline(filename):
    result = subprocess.run(
        ["git", "show", f"{BASE}:{filename}"], cwd=ROOT,
        capture_output=True, text=True, check=True,
    )
    return result.stdout


def main_html(html):
    return html.split('<main id="main">', 1)[1].split("</main>", 1)[0]


def clause_text(filename, heading):
    raw = (ROOT / "data/legal-sources-2026-11-11" / filename).read_text(encoding="utf-8")
    if heading == "Quick answer":
        return Audit(raw.split('<div class="quick">', 1)[1].split("</div>", 1)[0]).text
    if heading == "Opening agreement":
        return Audit("<p>By downloading" + raw.split("<p>By downloading", 1)[1].split("<h2>", 1)[0]).text
    for section in re.split(r"<h2>", raw)[1:]:
        title, body = section.split("</h2>", 1)
        if Audit(f"<div>{title}</div>").text == heading:
            return Audit(body).text
    raise AssertionError(f"Missing source clause {filename} / {heading}")


class LegalFixes(unittest.TestCase):
    def test_product_rename_prices_and_link_rel(self):
        tracked = subprocess.run(
            ["git", "ls-tree", "-r", "--name-only", BASE], cwd=ROOT,
            capture_output=True, text=True, check=True,
        ).stdout.splitlines()
        for filename in ALLOWED:
            with self.subTest(file=filename):
                raw = (ROOT / filename).read_text(encoding="utf-8")
                self.assertNotIn(OLD_URL, raw)
                # Stable element IDs and the live launch code retain their spelling.
                names = re.sub(r'\b(?:id|aria-labelledby)="[^"]*"|href="#[^"]*"', "", raw)
                self.assertNotRegex(names, rf"(?i)\b{OLD_NAME}(?:\s+SEO)?\b")
                if filename not in tracked:
                    continue
                previous = baseline(filename)
                if filename in {"index.html", "about/index.html", "privacy/index.html",
                                "affiliates/index.html", "404.html", "llms.txt"}:
                    renamed = previous.replace(OLD_NAME + " SEO", "Check Engine SEO")
                    renamed = re.sub(rf"\b{OLD_NAME}\b", "Check Engine", renamed)
                    renamed = renamed.replace(OLD_URL, NEW_URL)
                    renamed = renamed.replace("Visit " + OLD_URL.removeprefix("https://").rstrip("/"),
                                              "Visit checkengineseo.com")
                    self.assertEqual(raw, renamed)
                self.assertEqual(re.findall(r"\$\d[\d,]*(?:\.\d+)?", raw),
                                 re.findall(r"\$\d[\d,]*(?:\.\d+)?", previous))
                self.assertEqual(raw.count("FOUNDINGDOCKET"), previous.count("FOUNDINGDOCKET"))
                if not filename.endswith(".html"):
                    continue
                old_links = Audit(previous).links
                new_links = Audit(raw).links
                if filename == "legal/index.html":
                    new_links = [link for link in new_links
                                 if link["href"] not in {"/legal/site-terms/", "/security/"}]
                self.assertEqual(len(old_links), len(new_links))
                for old, new in zip(old_links, new_links):
                    href = old["href"].replace(OLD_URL, NEW_URL)
                    if filename == "legal/terms.html":
                        href = "/legal/"
                    if filename == "legal/privacy.html":
                        href = "/privacy/"
                    self.assertEqual(new["href"], href)
                    self.assertEqual(new.get("rel"), old.get("rel"))
                # Check raw rel spelling too, including whitespace and token order.
                old_rel = re.findall(r'\brel\s*=\s*("[^"]*"|\x27[^\x27]*\x27)', previous)
                new_rel = re.findall(r'\brel\s*=\s*("[^"]*"|\x27[^\x27]*\x27)', raw)
                self.assertEqual(new_rel, old_rel)

    def test_local_redirects_and_builder_rerun(self):
        for filename, route in [("legal/terms.html", "/legal/"), ("legal/privacy.html", "/privacy/")]:
            raw = (ROOT / filename).read_text(encoding="utf-8")
            self.assertIn(f'<link rel="canonical" href="{route}">', raw)
            self.assertIn(f'<meta http-equiv="refresh" content="0; url={route}">', raw)
            self.assertEqual([link["href"] for link in Audit(raw).links], [route])
            self.assertNotIn("builtbykerr.com", raw)
        spec = importlib.util.spec_from_file_location("redirects", ROOT / "scripts/build-redirects.py")
        redirects = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(redirects)
        listing = "index.html\nlegal/terms.html\nlegal/privacy.html\nlegal/disclaimer.html\nservices/example.html\n"
        result = subprocess.CompletedProcess([], 0, stdout=listing, stderr="")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "legal").mkdir()
            for filename in ["legal/terms.html", "legal/privacy.html"]:
                (root / filename).write_text("Keep local stub", encoding="utf-8")
            with patch.object(redirects, "ROOT", root), patch.object(redirects.subprocess, "run", return_value=result), patch.object(sys, "argv", ["build-redirects.py", "--services-repo", directory]), redirect_stdout(io.StringIO()):
                self.assertEqual(redirects.main(), 0)
            for filename in ["legal/terms.html", "legal/privacy.html"]:
                self.assertEqual((root / filename).read_text(), "Keep local stub")
            for filename in ["legal/disclaimer.html", "services/example.html"]:
                self.assertIn("https://builtbykerr.com/" + filename, (root / filename).read_text())
        self.assertEqual((ROOT / "legal/disclaimer.html").read_text(), baseline("legal/disclaimer.html"))
        self.assertRegex((ROOT / "scripts/build-redirects.py").read_text(), r"11 Nov 2026, the CEO")

    def test_security_page_and_security_txt(self):
        raw = (ROOT / "security/index.html").read_text(encoding="utf-8")
        text = Audit(main_html(raw)).text
        self.assertIn("admin@kerrandcompanyholdings.com", text)
        self.assertIn("mailto:admin@kerrandcompanyholdings.com", raw)
        for phrase in ["any Kerr & Company website or app", "website URL", "app name and version", "steps to see", "expected to happen", "before we have had a chance to fix"]:
            self.assertIn(phrase, text)
        self.assertNotRegex(text.lower(), r"respond within|bount(?:y|ies)|reward|safe harbour|guarantee")
        fields = dict(line.split(": ", 1) for line in (ROOT / ".well-known/security.txt").read_text(encoding="utf-8").splitlines())
        self.assertEqual(fields, {
            "Contact": "mailto:admin@kerrandcompanyholdings.com",
            "Expires": "2027-11-11T00:00:00.000Z",
            "Policy": SITE + "/security/",
            "Preferred-Languages": "en",
            "Canonical": SITE + "/.well-known/security.txt",
        })

    def test_site_terms_and_source_mapping(self):
        raw = main_html((ROOT / "legal/site-terms/index.html").read_text(encoding="utf-8"))
        text = Audit(raw).text
        self.assertGreaterEqual(len(text.split()), 150)
        self.assertLessEqual(len(text.split()), 400)
        self.assertNotRegex(text.lower(), r"guarantee|uptime|within\s+\d+\s+days|refund")
        paragraphs = [Audit(f"<p>{p}</p>").text
                      for p in re.findall(r'<p(?:\s[^>]*)?>(.*?)</p>', raw, flags=re.S)]
        self.assertEqual(paragraphs.pop(0), "Kerr & Company LLC · Grand Rapids, Michigan")
        self.assertEqual(paragraphs, list(TERMS_PARAGRAPHS))
        self.assertEqual(set(SOURCES), set(range(1, len(paragraphs) + 1)))
        for number, (filename, clause, excerpt) in SOURCES.items():
            with self.subTest(paragraph=number, source=filename, clause=clause):
                self.assertIn(excerpt, clause_text(filename, clause))
        about = Audit((ROOT / "about/index.html").read_text(encoding="utf-8")).text
        self.assertIn("matthew@kerrandcompanyholdings.com", about)
        self.assertIn('<a href="/legal/">', raw)
        for filename in ["crisp-terms.html", "outlier-terms.html", "checkengine-terms.html"]:
            law = clause_text(filename, "11. Governing law" if filename == "crisp-terms.html" else "Governing law")
            self.assertIn("State of Michigan", law)
        print(f"Site terms: {len(text.split())} words including headings and date.")

    def test_new_page_shells_and_metadata(self):
        shell = (ROOT / "privacy/index.html").read_text(encoding="utf-8")
        for filename, title, route in [("security/index.html", "Security", "/security/"), ("legal/site-terms/index.html", "Site terms", "/legal/site-terms/")]:
            raw = (ROOT / filename).read_text(encoding="utf-8")
            before, rest = raw.split('<main id="main">', 1)
            _, after = rest.split("</main>", 1)
            self.assertEqual(before.split("</head>", 1)[1], shell.split("</head>", 1)[1].split('<main id="main">', 1)[0])
            self.assertEqual(after, shell.split("</main>", 1)[1])
            self.assertNotRegex(unescape(raw), "[\u2013\u2014]")
            self.assertIn(f'<link rel="canonical" href="{SITE + route}">', before)
            self.assertIn(f'<title>{title} | Kerr &amp; Company LLC</title>', before)
            self.assertIn(f'<meta property="og:url" content="{SITE + route}">', before)
            schema = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', before)[1])
            self.assertEqual(schema["url"], SITE + route)
            self.assertEqual(schema["name"], title)
            self.assertEqual(sum(tag == "h1" for tag, _ in Audit(raw).elements), 1)
            self.assertIn('<a href="/#contact">Contact</a>', before)
        self.assertIn('id="contact"', (ROOT / "index.html").read_text())

    def test_sitemap_adds_exactly_two_urls(self):
        raw = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
        ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        entries = ET.fromstring(raw).findall("s:url", ns)
        for route in ["/legal/site-terms/", "/security/"]:
            matching = [entry for entry in entries if entry.findtext("s:loc", namespaces=ns) == SITE + route]
            self.assertEqual(len(matching), 1)
            self.assertEqual(matching[0].findtext("s:lastmod", namespaces=ns), "2026-11-11")
        previous, count = re.subn(r"  <url>\n    <loc>https://kerrandcompanyholdings.com/(?:legal/site-terms/|security/)</loc>\n.*?  </url>\n", "", raw, flags=re.S)
        self.assertEqual(count, 2)
        self.assertEqual(previous, baseline("sitemap.xml"))

    def test_only_allowed_paths_and_no_new_dashes(self):
        result = subprocess.run(["git", "diff", "--name-only", BASE], cwd=ROOT, capture_output=True, text=True, check=True)
        self.assertLessEqual(set(result.stdout.splitlines()), set(ALLOWED))
        untracked = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"], cwd=ROOT,
            capture_output=True, text=True, check=True,
        )
        self.assertLessEqual(set(untracked.stdout.splitlines()), set(ALLOWED))
        result = subprocess.run(["git", "diff", "--unified=0", BASE, "--", *ALLOWED], cwd=ROOT, capture_output=True, text=True, check=True)
        for line in result.stdout.splitlines():
            if line.startswith("+") and not line.startswith("+++"):
                self.assertNotRegex(unescape(line), "[\u2013\u2014]")


if __name__ == "__main__":
    unittest.main(verbosity=2)
