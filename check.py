import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import requests

import classify
import match

FOLDER = Path(__file__).parent
DB_PATH = FOLDER / "opportunities.db"
CONFIG_PATH = FOLDER / "alert_config.json"
LOG_PATH = FOLDER / "alerts.log"

ALERTS_TABLE = """
CREATE TABLE IF NOT EXISTS alerts_sent (
    opportunity_id INTEGER PRIMARY KEY REFERENCES opportunities(id),
    score INTEGER NOT NULL,
    sent_at TEXT NOT NULL
);
"""


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_config():
    if not CONFIG_PATH.exists():
        return {}
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def ensure_alerts_table(conn):
    conn.executescript(ALERTS_TABLE)
    conn.commit()


def already_alerted(conn, opp_id):
    row = conn.execute("SELECT 1 FROM alerts_sent WHERE opportunity_id = ?", (opp_id,)).fetchone()
    return row is not None


def mark_alerted(conn, opp_id, score):
    conn.execute(
        "INSERT OR REPLACE INTO alerts_sent (opportunity_id, score, sent_at) VALUES (?, ?, ?)",
        (opp_id, score, now()),
    )
    conn.commit()


def format_message(job, result):
    lines = [
        "%d/100 %s" % (result["score"], job["title"]),
        "[%s / %s]" % (job["opp_type"], match.format_category(job["category"])),
        "deadline: %s" % match.format_deadline(job["deadline"]),
    ]
    skills = result["skills"]
    matched = skills["matched_required"] | skills["matched_preferred"] | skills["matched_technical"]
    if matched:
        lines.append("matches: " + match.print_set(matched))
    lines.append(job["source_url"])
    return "\n".join(lines)


def send_telegram(config, text):
    token = config.get("telegram_bot_token")
    chat_id = config.get("telegram_chat_id")
    if not token or not chat_id:
        return False, "telegram not configured in alert_config.json"
    url = "https://api.telegram.org/bot%s/sendMessage" % token
    try:
        response = requests.post(url, data={"chat_id": chat_id, "text": text}, timeout=15)
        response.raise_for_status()
        return True, None
    except requests.RequestException as exc:
        return False, str(exc)


def log_alert(text):
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write("--- %s ---\n%s\n\n" % (now(), text))


def run_alerts(conn, profile, config, threshold, dry_run):
    ensure_alerts_table(conn)
    posts = match.open_posts(conn)
    sent = 0
    skipped_seen = 0
    for job in posts:
        if already_alerted(conn, job["id"]):
            skipped_seen += 1
            continue
        result = match.calculate_score(job, profile)
        if result["score"] < threshold:
            continue
        text = format_message(job, result)
        log_alert(text)
        if not dry_run:
            ok, error = send_telegram(config, text)
            if not ok:
                print("telegram not sent (%s), logged locally instead: %s" % (error, job["title"]))
            else:
                print("sent: %s" % job["title"])
        else:
            print("would alert (dry run): %s" % job["title"])
        mark_alerted(conn, job["id"], result["score"])
        sent += 1
    print("%d posts already alerted before this run, %d new alerts this run" % (skipped_seen, sent))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--threshold", type=int, default=40, help="minimum score to trigger an alert")
    parser.add_argument("--dry-run", action="store_true", help="log alerts but don't send Telegram messages")
    parser.add_argument("--skip-scrape", action="store_true", help="use the existing database, don't hit the network")
    parser.add_argument("--watch", action="store_true", help="repeat forever on an interval")
    parser.add_argument("--interval", type=int, default=600)
    args = parser.parse_args()

    config = load_config()
    profile = match.load_profile()

    while True:
        if not args.skip_scrape:
            import scraper
            conn = scraper.connect()
            robots = scraper.load_robots()
            scraper.run_once(conn, robots, ["jobs"], 1, False)
            classify.run(conn, False)
        else:
            conn = classify.connect()

        run_alerts(conn, profile, config, args.threshold, args.dry_run)

        if not args.watch:
            break
        import time
        time.sleep(args.interval)


if __name__ == "__main__":
    main()