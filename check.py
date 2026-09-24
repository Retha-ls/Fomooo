import argparse
import json
import sqlite3
import time
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

    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print("could not load alert_config.json: %s" % exc)
        return {}


def ensure_alerts_table(conn):
    conn.executescript(ALERTS_TABLE)
    conn.commit()


def already_alerted(conn, opp_id):
    row = conn.execute(
        "SELECT 1 FROM alerts_sent WHERE opportunity_id = ?",
        (opp_id,)
    ).fetchone()

    return row is not None


def mark_alerted(conn, opp_id, score):
    conn.execute(
        """
        INSERT OR REPLACE INTO alerts_sent
        (opportunity_id, score, sent_at)
        VALUES (?, ?, ?)
        """,
        (opp_id, score, now())
    )

    conn.commit()


def format_message(job, result):
    lines = [
        "%d/100 %s" % (result["score"], job["title"]),
        "[%s / %s]" % (
            job["opp_type"],
            match.format_category(job["category"])
        ),
        "deadline: %s" % match.format_deadline(job["deadline"]),
    ]

    skills = result["skills"]

    matched = (
        skills["matched_required"]
        | skills["matched_preferred"]
        | skills["matched_technical"]
    )

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
        response = requests.post(
            url,
            data={
                "chat_id": chat_id,
                "text": text
            },
            timeout=15
        )

        response.raise_for_status()

        data = response.json()

        if not data.get("ok"):
            return False, "Telegram API returned ok=false"

        return True, None

    except requests.RequestException as exc:
        return False, str(exc)

    except ValueError as exc:
        return False, "invalid Telegram response: %s" % exc


def log_alert(text):
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(
            "--- %s ---\n%s\n\n"
            % (now(), text)
        )


def run_alerts(conn, profile, config, threshold, dry_run):
    ensure_alerts_table(conn)

    posts = match.open_posts(conn)

    alerted = 0
    skipped_seen = 0
    below_threshold = 0

    for job in posts:

        if already_alerted(conn, job["id"]):
            skipped_seen += 1
            continue

        result = match.calculate_score(job, profile)

        if result["score"] < threshold:
            below_threshold += 1
            continue

        text = format_message(job, result)

        if dry_run:
            print()
            print("would alert (dry run):")
            print(text)
            print()

            continue

        log_alert(text)

        ok, error = send_telegram(config, text)

        if not ok:
            print(
                "telegram not sent (%s), logged locally instead: %s"
                % (error, job["title"])
            )
        else:
            print("sent: %s" % job["title"])

        mark_alerted(
            conn,
            job["id"],
            result["score"]
        )

        alerted += 1

    print()
    print(
        "%d posts already alerted before this run"
        % skipped_seen
    )

    print(
        "%d opportunities below threshold"
        % below_threshold
    )

    if dry_run:
        print("dry run complete - no alerts were sent or recorded")
    else:
        print(
            "%d new alerts processed this run"
            % alerted
        )


def run_pipeline(args):
    config = load_config()
    profile = match.load_profile()

    if args.skip_scrape:
        print("scraping skipped")
        print("using existing database")

        conn = classify.connect()

    else:
        print("starting scraper")

        import scraper

        conn = scraper.connect()

        robots = scraper.load_robots()

        scraper.run_once(
            conn,
            robots,
            ["jobs"],
            1,
            False
        )

        print("scraping complete")

        print("classifying opportunities")

        classify.run(
            conn,
            False
        )

        print("classification complete")

    run_alerts(
        conn,
        profile,
        config,
        args.threshold,
        args.dry_run
    )

    conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="FOMOOO opportunity monitoring and alert pipeline"
    )

    parser.add_argument(
        "--threshold",
        type=int,
        default=40,
        help="minimum score required to trigger an alert"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="preview alerts without sending or recording them"
    )

    parser.add_argument(
        "--skip-scrape",
        action="store_true",
        help="use the existing database without scraping"
    )

    parser.add_argument(
        "--watch",
        action="store_true",
        help="repeat the pipeline continuously"
    )

    parser.add_argument(
        "--interval",
        type=int,
        default=600,
        help="seconds between watch runs (default: 600)"
    )

    args = parser.parse_args()

    if args.threshold < 0:
        print("threshold cannot be negative")
        return

    if args.interval < 1:
        print("interval must be at least 1 second")
        return

    print("FOMOOO opportunity monitor")
    print("threshold: %d" % args.threshold)

    if args.dry_run:
        print("mode: DRY RUN")

    if args.skip_scrape:
        print("scraping: SKIPPED")
    else:
        print("scraping: ENABLED")

    if args.watch:
        print("watch interval: %d seconds" % args.interval)

    print()

    while True:

        try:
            print("=== pipeline run: %s ===" % now())

            run_pipeline(args)

            print("=== pipeline run complete ===")

        except KeyboardInterrupt:
            print()
            print("FOMOOO stopped")
            break

        except Exception as exc:
            print()
            print("pipeline error: %s" % exc)

            if not args.watch:
                raise

        if not args.watch:
            break

        print()
        print(
            "waiting %d seconds until the next run..."
            % args.interval
        )

        try:
            time.sleep(args.interval)

        except KeyboardInterrupt:
            print()
            print("FOMOOO stopped")
            break


if __name__ == "__main__":
    main()