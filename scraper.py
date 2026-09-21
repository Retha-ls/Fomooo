import argparse
import re
import sqlite3
import time
import urllib.robotparser
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE = "https://selibeng.com"
SOURCE = "selibeng"

CATEGORIES = {
    "jobs": "/category/opportunities/jobs/",
    "consultancy": "/category/opportunities/consultancy/",
    "tenders": "/category/opportunities/tenders/",
    "scholarships": "/category/opportunities/scholarships/",
    "entrepreneurs": "/category/opportunities/entrepreneurs/",
    "competitions": "/category/opportunities/competitions/",
    "international": "/category/opportunities/international/",
    "training": "/category/opportunities/training/",
    "freelance": "/category/opportunities/freelance/",
}

HEADERS = {"User-Agent": "OpportunityTracker/0.1 (personal project)"}
FOLDER = Path(__file__).parent
DB_PATH = FOLDER / "opportunities.db"
SCHEMA_PATH = FOLDER / "schema.sql"
DEBUG_PATH = FOLDER / "debug_listing.html"
DETAIL_DELAY = 2

CONTENT_SELECTORS = ["div.td-post-content", "div.entry-content", "div.post-content", "article"]
BLOCK_TAGS = ["p", "li", "ul", "ol", "div", "h1", "h2", "h3", "h4", "h5", "h6", "tr"]
DATE_RE = re.compile(r"[A-Z][a-z]+ \d{1,2}, \d{4}")
POSITIONS_RE = re.compile(r"(?<![A-Za-z0-9])[x×]\s?(\d+)(?!\d)", re.I)
TITLE_RE = re.compile(r"^(.*\S)\s+at\s+(.+)$")


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def fetch(url, attempts=3):
    for attempt in range(1, attempts + 1):
        try:
            response = SESSION.get(url, timeout=20)
            response.raise_for_status()
            return response.text
        except requests.RequestException:
            if attempt == attempts:
                raise
            time.sleep(3 * attempt)


def load_robots():
    parser = urllib.robotparser.RobotFileParser()
    try:
        response = requests.get(BASE + "/robots.txt", headers=HEADERS, timeout=20)
        if response.status_code == 200:
            parser.parse(response.text.splitlines())
            parser.modified()
            return parser
    except requests.RequestException:
        pass
    return None


def allowed(parser, url):
    if parser is None:
        return True
    return parser.can_fetch(HEADERS["User-Agent"], url)


def to_iso(text):
    try:
        return datetime.strptime(text, "%B %d, %Y").date().isoformat()
    except ValueError:
        return None


def find_date(heading):
    node = heading.parent
    while node is not None and len(node.find_all("h3")) == 1:
        time_tag = node.find("time")
        if time_tag is not None:
            match = DATE_RE.search(time_tag.get_text(" ", strip=True))
            if match:
                return to_iso(match.group())
            if time_tag.get("datetime"):
                return time_tag["datetime"][:10]
        match = DATE_RE.search(node.get_text(" ", strip=True))
        if match:
            return to_iso(match.group())
        node = node.parent
    return None


def parse_listing(html):
    soup = BeautifulSoup(html, "html.parser")
    items = []
    seen = set()
    for heading in soup.find_all("h3"):
        link = heading.find("a", href=True)
        if link is None:
            continue
        url = link["href"].split("#")[0]
        if not url.startswith(BASE + "/") or "/category/" in url or url in seen:
            continue
        seen.add(url)
        items.append({
            "url": url,
            "title": link.get_text(" ", strip=True),
            "date": find_date(heading),
        })
    return items


def parse_detail(html):
    soup = BeautifulSoup(html, "html.parser")
    for selector in CONTENT_SELECTORS:
        node = soup.select_one(selector)
        if node is None:
            continue
        for tag in node(["script", "style"]):
            tag.decompose()
        for br in node.find_all("br"):
            br.replace_with("\n")
        for tag in node.find_all(BLOCK_TAGS):
            tag.append("\n")
        text = clean_text(node.get_text())
        if len(text) > 80:
            return text
    return None


def clean_text(text):
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" ?\n ?", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_title(title):
    match = TITLE_RE.match(title)
    company = match.group(2).strip() if match else None
    positions = sum(int(n) for n in POSITIONS_RE.findall(title)) or 1
    return company, positions


def make_title_key(title):
    cleaned = POSITIONS_RE.sub("", title.lower())
    return re.sub(r"[^a-z0-9]+", " ", cleaned).strip()


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_PATH.read_text())
    return conn


def already_saved(conn, url):
    row = conn.execute("SELECT 1 FROM opportunities WHERE source_url = ?", (url,)).fetchone()
    return row is not None


def save(conn, category, item, description, backfill):
    company, positions = split_title(item["title"])
    key = make_title_key(item["title"])
    original = conn.execute(
        "SELECT id FROM opportunities WHERE title_key = ? AND duplicate_of IS NULL ORDER BY id LIMIT 1",
        (key,),
    ).fetchone()
    duplicate_of = original["id"] if original is not None else None
    conn.execute(
        """INSERT INTO opportunities
           (source, source_url, source_category, title, company, positions, description,
            date_posted, title_key, duplicate_of, is_backfill, first_seen_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (SOURCE, item["url"], category, item["title"], company, positions, description,
         item["date"], key, duplicate_of, 1 if backfill else 0, now()),
    )
    conn.commit()
    return duplicate_of


def run_once(conn, robots, categories, pages, debug):
    started = now()
    count = conn.execute("SELECT COUNT(*) FROM opportunities").fetchone()[0]
    backfill = pages > 1 or count == 0
    found = 0
    added = 0
    error = None

    try:
        for category in categories:
            for page in range(1, pages + 1):
                path = CATEGORIES[category] + ("" if page == 1 else "page/%d/" % page)
                url = BASE + path
                if not allowed(robots, url):
                    print("[%s] blocked by robots.txt: %s" % (category, url))
                    break
                html = fetch(url)
                if debug:
                    DEBUG_PATH.write_text(html, encoding="utf-8")
                items = parse_listing(html)
                if len(items) == 0:
                    print("[%s] page %d: no listings parsed" % (category, page))
                    DEBUG_PATH.write_text(html, encoding="utf-8")
                    break
                found += len(items)
                for item in items:
                    if already_saved(conn, item["url"]):
                        continue
                    time.sleep(DETAIL_DELAY)
                    description = None
                    if allowed(robots, item["url"]):
                        try:
                            description = parse_detail(fetch(item["url"]))
                        except requests.RequestException as exc:
                            print("  skipped, will retry next run: %s (%s)" % (item["url"], type(exc).__name__))
                            continue
                    if description is None:
                        print("  warning: no description parsed for " + item["url"])
                    duplicate_of = save(conn, category, item, description, backfill)
                    added += 1
                    tag = "REPOST of #%d" % duplicate_of if duplicate_of else "NEW"
                    print("%s [%s] %s (%s)" % (tag, category, item["title"], item["date"]))
    except Exception as exc:
        error = str(exc)
        print("run error: " + error)

    conn.execute(
        "INSERT INTO scrape_runs (source, started_at, finished_at, listings_found, new_found, error) VALUES (?, ?, ?, ?, ?, ?)",
        (SOURCE, started, now(), found, added, error),
    )
    conn.commit()
    print("run done: %d listings seen, %d new" % (found, added))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--categories", default="jobs", help="comma separated, or 'all'")
    parser.add_argument("--pages", type=int, default=1, help="pages per category (use more for a backfill)")
    parser.add_argument("--watch", action="store_true", help="keep running and re-check on an interval")
    parser.add_argument("--interval", type=int, default=600, help="seconds between checks in watch mode")
    parser.add_argument("--debug", action="store_true", help="save the raw listing html to debug_listing.html")
    args = parser.parse_args()

    if args.categories == "all":
        categories = list(CATEGORIES)
    else:
        categories = [c.strip() for c in args.categories.split(",")]
    for category in categories:
        if category not in CATEGORIES:
            raise SystemExit("unknown category: " + category)

    conn = connect()
    robots = load_robots()

    while True:
        run_once(conn, robots, categories, args.pages, args.debug)
        if not args.watch:
            break
        time.sleep(args.interval)


if __name__ == "__main__":
    main()