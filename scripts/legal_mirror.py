#!/usr/bin/env python3
"""Build the legal record from the saved, unmodified product pages. No network."""

import argparse
from dataclasses import dataclass, field
from datetime import datetime
from html import escape
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
from urllib.parse import urljoin, urlsplit


ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "data/legal-sources-2026-11-11"
SITE = "https://kerrandcompanyholdings.com"
PRODUCTS = {
    "crisp": ("Crisp", ("crisp-terms.html", "crisp-privacy.html", "crisp-refunds.html")),
    "outlier": ("Outlier", ("outlier-terms.html", "outlier-privacy.html")),
    "check-engine": ("Check Engine", (
        "checkengine-terms.html", "checkengine-privacy.html", "checkengine-refunds.html",
    )),
}
KERR_DOMAINS = {
    "crispvideo.app", "outlier.host", "checkengineseo.com", "docketseo.app",
    "builtbykerr.com", "matthewkerr.dev",
    "adplaybook.app", "kerrco.workers.dev",
}
VOID = set("area base br col embed hr img input link meta param source track wbr".split())
# These are product-site navigation, sales boxes, subscription boxes and footers.
CHROME_CLASSES = {"crumb", "back", "pbox", "cta", "sublist", "foot"}
DROP_TAGS = {
    "head", "nav", "header", "footer", "script", "style", "form", "button",
    "img", "picture", "svg", "input", "select", "textarea", "iframe",
}
CONTENT_TAGS = set((
    "h1 h2 h3 h4 h5 h6 p div section article main body ul ol li dl dt dd "
    "table caption colgroup col thead tbody tfoot tr th td strong b em i u s "
    "small a code pre blockquote br hr time abbr sup sub span"
).split())


@dataclass
class Node:
    tag: str
    attrs: dict = field(default_factory=dict)
    children: list = field(default_factory=list)


class Tree(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.root = Node("")
        self.stack = [self.root]
        self.feed(html)
        self.close()

    def handle_starttag(self, tag, attrs):
        node = Node(tag, dict(attrs))
        self.stack[-1].children.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def nodes(node):
    yield node
    for child in node.children:
        if isinstance(child, Node):
            yield from nodes(child)


def is_kerr_link(href, base):
    if urlsplit(href).scheme.lower() == "mailto":
        return False
    host = (urlsplit(urljoin(base, href)).hostname or "").lower().rstrip(".")
    return any(host == domain or host.endswith("." + domain) for domain in KERR_DOMAINS)


def link_attrs(attrs, base):
    attrs = dict(attrs)
    if "href" in attrs:
        href = attrs["href"]
        if urlsplit(href).scheme.lower() != "mailto":
            attrs["href"] = urljoin(base, href)
        if urlsplit(attrs["href"]).hostname == urlsplit(SITE).hostname:
            rel = [token for token in attrs.get("rel", "").split()
                   if token.lower() != "nofollow"]
            if rel:
                attrs["rel"] = " ".join(rel)
            else:
                attrs.pop("rel", None)
        if is_kerr_link(attrs["href"], base):
            rel = attrs.get("rel", "").split()
            if "nofollow" not in rel:
                rel.append("nofollow")
            attrs["rel"] = " ".join(rel)
    return attrs


def attributes(attrs):
    return "".join(
        " " + key if value is None else f' {key}="{escape(value, quote=True)}"'
        for key, value in attrs.items()
    )


def mirror_node(node, base):
    if isinstance(node, str):
        return escape(node, quote=False)
    classes = set(node.attrs.get("class", "").split())
    if (node.tag in DROP_TAGS or classes & CHROME_CLASSES
            or "data-founding" in node.attrs or "hidden" in node.attrs):
        return ""
    content = "".join(mirror_node(child, base) for child in node.children)
    if node.tag not in CONTENT_TAGS or node.tag in {"main", "body", "article"}:
        return content
    if node.tag == "div" and "wrap" in classes:
        return content
    tag = node.tag
    if re.fullmatch(r"h[1-6]", tag):
        level = int(tag[1]) + 1
        if level > 6:
            raise ValueError("Cannot demote a source h6 without losing heading structure")
        tag = f"h{level}"
    attrs = {key: value for key, value in node.attrs.items() if key in {
        "href", "rel", "target", "title", "id", "datetime", "lang", "dir",
        "colspan", "rowspan", "scope", "headers", "start", "reversed", "value",
    }}
    if tag == "a":
        attrs = link_attrs(attrs, base)
    start = f"<{tag}{attributes(attrs)}>"
    return start if tag in VOID else start + content + f"</{tag}>"


def source_info(filename):
    html = (SOURCES / filename).read_text(encoding="utf-8")
    match = re.fullmatch(
        r"<!-- source: (https://\S+) ; read (\d{4}-\d\d-\d\d) between "
        r"(\S+) and (\S+) ; title: (.*?) -->", html.splitlines()[0],
    )
    if not match:
        raise ValueError(f"Missing source record: {filename}")
    url, date, start, end, title = match.groups()
    read_at = (SOURCES / "read-at.txt").read_text(encoding="utf-8").splitlines()
    if read_at[0] != start or read_at[-1] != end:
        raise ValueError(f"Source window differs from read-at.txt: {filename}")
    if not (start.startswith(date) and end.startswith(date)):
        raise ValueError(f"Source window crosses dates: {filename}")
    return {"url": url, "start": start, "end": end, "title": title, "html": html}


def read_window(info):
    def formatted(stamp):
        date = datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ")
        return f"{date.day} {date:%B %Y at %H:%M:%S} UTC"
    return (
        f'read between <time datetime="{info["start"]}">{formatted(info["start"])}</time>'
        f' and <time datetime="{info["end"]}">{formatted(info["end"])}</time>'
    )


GOVERNS = "If this copy and the product's own page ever differ, the product's page governs."
REFUND_NOTE = 'Outlier has no separate refund page. Its refund wording is in the "Payment + refunds" section of its terms above.'


def company_line():
    about = Tree((ROOT / "about/index.html").read_text(encoding="utf-8")).root
    paragraph = next(n for n in nodes(about) if n.tag == "p" and n.children
                     and isinstance(n.children[0], str)
                     and n.children[0].startswith("Kerr & Company LLC is "))
    return paragraph.children[0].split(". ", 1)[0] + "."


def mirror_body(slug):
    name, files = PRODUCTS[slug]
    coverage = "terms and privacy policy" if slug == "outlier" else "terms, privacy policy and refund policy"
    intro = f"This page mirrors {name}'s {coverage}."
    parts = []
    for filename in files:
        info = source_info(filename)
        tree = Tree(info["html"]).root
        if sum(n.tag == "h1" for n in nodes(tree)) != 1:
            raise ValueError(f"Expected one legal title: {filename}")
        parts.append(
            f'<section data-source="{filename}">\n'
            f'<p class="source">Mirrored from <a href="{info["url"]}" rel="nofollow">'
            f'{info["url"]}</a>, {read_window(info)}. {GOVERNS}</p>\n'
            f'<div class="mirrored-text">{mirror_node(tree, info["url"])}</div>\n'
            '</section>'
        )
    if slug == "outlier":
        parts.append(f"<p>{escape(REFUND_NOTE, quote=False)}</p>")
    return intro, "\n".join(parts)


INDEX_LINES = (
    ("/legal/site-terms/", "Site terms", "Terms for using this company website."),
    ("/privacy/", "Site privacy", "What the company website collects and who sees it."),
    ("/security/", "Security", "How to report a security problem with our websites or apps."),
    ("/terms/", "Post Desk terms", "Terms for using Post Desk."),
    ("/about/", "Company details", "Who Kerr & Company LLC is and how to contact us."),
    ("/legal/crisp/", "Crisp legal mirror", "Crisp's terms, privacy policy and refund policy."),
    ("/legal/outlier/", "Outlier legal mirror", "Outlier's terms and privacy policy, with refunds in its terms."),
    ("/legal/check-engine/", "Check Engine legal mirror", "Check Engine's terms, privacy policy and refund policy."),
)


def page(title, description, route, intro, content, noindex=False):
    shell = (ROOT / "privacy/index.html").read_text(encoding="utf-8")
    before, rest = shell.split('<main id="main">', 1)
    _, after = rest.split("</main>", 1)
    # The offer bar is sales chrome, not part of the legal page shell.
    before = re.sub(r'<div class="offer">.*?</div>\n', "", before)
    before = re.sub(r"<title>.*?</title>", f"<title>{escape(title)} | Kerr &amp; Company LLC</title>", before)
    before = re.sub(
        r'(<meta (?:name="(?:description|twitter:description)"|property="og:description") content=")[^"]*',
        lambda m: m[1] + escape(description, quote=True), before,
    )
    before = before.replace('content="Privacy | Kerr &amp; Company LLC"',
                            f'content="{escape(title)} | Kerr &amp; Company LLC"')
    before = before.replace(SITE + "/privacy/", SITE + route)
    before = re.sub(r'(<meta property="og:image:alt" content=")[^"]*',
                    r'\g<1>Kerr &amp; Company LLC, Grand Rapids, Michigan.', before)
    if noindex:
        before = before.replace('content="index,follow"', 'content="noindex, follow"')
        # Extend the shell's document spacing to the nested, preserved headings.
        before = before.replace("</head>", '''<style>
.doc > section + section{margin-top:3rem;padding-top:1.5rem;border-top:1px solid var(--rule-2)}
.mirrored-text h2{font-size:var(--fs-xl);margin:1.5rem 0 .8rem}
.mirrored-text h3,.mirrored-text h4{margin:2rem 0 .8rem}
.mirrored-text ul,.mirrored-text ol{margin-bottom:1rem}
.source a{overflow-wrap:anywhere}
</style>
</head>''')
    schema = {
        "@context": "https://schema.org", "@type": "WebPage", "name": title,
        "url": SITE + route,
        "isPartOf": {"@type": "WebSite", "name": "Kerr & Company LLC", "url": SITE + "/"},
        "about": {"@type": "Organization", "name": "Kerr & Company LLC", "url": SITE + "/"},
    }
    before = re.sub(r'(<script type="application/ld\+json">).*?(</script>)',
                    lambda m: m[1] + json.dumps(schema, separators=(",", ":")) + m[2], before)
    main = f'''<main id="main">
<section class="page-head">
  <div class="wrap">
    <p class="eyebrow">Kerr &amp; Company LLC &middot; Grand Rapids, Michigan</p>
    <h1>{escape(title)}</h1>
    <p>{escape(company_line())}</p>
    <p class="lead">{escape(intro, quote=False)}</p>
  </div>
</section>
<div class="wrap doc">
{content}
</div>
</main>'''
    return before + main + after


def build_pages():
    content = "<ul>\n" + "\n".join(
        f'  <li><a href="{route}">{escape(label)}</a>: {escape(line, quote=False)}</li>'
        for route, label, line in INDEX_LINES
    ) + "\n</ul>"
    pages = {"legal/index.html": page(
        "Legal", "Company pages and saved copies of product legal pages.", "/legal/",
        "Company pages and copies of our products' legal pages are listed below.", content,
    )}
    for slug, (name, _) in PRODUCTS.items():
        intro, content = mirror_body(slug)
        pages[f"legal/{slug}/index.html"] = page(
            f"{name} legal mirror", f"A saved copy of {name}'s legal pages.",
            f"/legal/{slug}/", intro, content, noindex=True,
        )
    return pages


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Compare without writing files")
    args = parser.parse_args(argv)
    failed = False
    for filename, expected in build_pages().items():
        target = ROOT / filename
        if args.check:
            if not target.exists() or target.read_text(encoding="utf-8") != expected:
                print(f"DRIFT: {filename}; run python3 scripts/legal_mirror.py", file=sys.stderr)
                failed = True
            else:
                print(f"OK: {filename}")
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(expected, encoding="utf-8")
            print(f"Built {filename}")
    return int(failed)


if __name__ == "__main__":
    sys.exit(main())
