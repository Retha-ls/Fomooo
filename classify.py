import argparse
import re
import sqlite3
import unicodedata
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

FOLDER = Path(__file__).parent
DB_PATH = FOLDER / "opportunities.db"
SCHEMA_PATH = FOLDER / "schema.sql"

NEW_COLUMNS = {
    "opp_type": "TEXT",
    "category": "TEXT",
    "level": "TEXT",
    "min_years": "INTEGER",
    "deadline": "TEXT",
    "deadline_note": "TEXT",
    "is_bundle": "INTEGER NOT NULL DEFAULT 0",
    "classified_at": "TEXT",
}

DEFAULT_TYPE = {
    "jobs": "job",
    "international": "job",
    "freelance": "job",
    "consultancy": "consultancy",
    "tenders": "tender",
    "scholarships": "scholarship",
    "competitions": "competition",
    "entrepreneurs": "entrepreneurship",
    "training": "training",
}

TENDER_RE = re.compile(r"\btender\b|request for (proposal|quotation)|\brfp\b|\brfq\b|invitation to bid|supply and delivery|supply, delivery", re.I)
CONSULTANCY_RE = re.compile(r"\beoi\b|expression of interest|consultancy|terms of reference", re.I)
INTERN_RE = re.compile(r"\binterns?\b|internships?|attachment|trainee|learnership|apprentice|graduate programme", re.I)
BUNDLE_RE = re.compile(r"various positions|multiple positions|several positions|vacancies", re.I)
GOVERNMENT_RE = re.compile(r"permanent secretary|principal secretary", re.I)
ADMIN_RE = re.compile(r"personal assistant|executive assistant|secretary to", re.I)
EXECUTIVE_RE = re.compile(
    r"(deputy |assistant )?(director|head of|general manager|managing director|"
    r"chief (executive|financial|operating|information|technology|risk) |permanent secretary|principal secretary|ceo\b)"
)
MANAGER_RE = re.compile(r"manager|supervisor|foreman|team leader|coordinator|\blead\b")
SENIOR_RE = re.compile(r"senior|specialist|principal")

CATEGORY_RULES = [
    ("development_ngo", r"programme|program officer|project (manager|coordinator|officer)|\bm&e\b|monitoring and evaluation|community|liaison|civic|advisor|coordinator|fasp|strategic information|instit?utional|public management|policy"),
    ("technology_data", r"(?<!account )developer|software|programmer|programming|\bdata\b|networking|network (administrator|engineer|security|support)|cyber|database|\bweb\b|analytics|information technology|\bui\b|\bux\b"),
    ("finance_banking", r"financ|accountan|accounting|accounts? (payable|receivable|assistant|officer|clerk)|audit|payable|receivable|bookkeep|treasury|payroll|credit|underwriting|\bloans?\b|insurance|\brisk\b|bank|invest|\btax|actuar|collections"),
    ("engineering_trades", r"engineer|(?<!lab )(?<!laboratory )technician|electrician|mechanic|welder|carpenter|rigger|scaffold|steel fixer|construction|civil|surveyor|architect|plumber|artisan|crane|loader|shutter|shatter|concrete|paving|installation|air condition|\broads?\b|foreman|site (supervisor|manager)|generation|electricity|hydro"),
    ("logistics_transport", r"driver|truck|fleet|logistic|warehouse|stores controller|stock controller|storekeeper|distribution|crewman|courier|dispatch|transport|procurement|supply chain"),
    ("health_safety", r"nurse|nursing|clinical|health|medical|\blab\b|laborator|pharmac|nutrition|counsel|midwi|doctor|screening|triage|contact tracer|safety|environment"),
    ("education", r"teacher|lecturer|tutor|invigilator|moderator|school|academic|education|curriculum|assessment|mathematics|sciences|languages|subject manager"),
    ("hr_legal_compliance", r"human resources|people and culture|recruit|legal|compliance|governance|paralegal|\blaw\b"),
    ("sales_marketing", r"sales|marketing|business development|merchandis|brand|social media|promoter|account (developer|manager|executive)|\bagents?\b|telesales"),
    ("media_language", r"designer|graphic|video|photograph|content|copywrit|journalis|editor|translator|interpreter|communications?\b|public relations"),
    ("hospitality_retail", r"waiter|waitress|barista|\bcook\b|chef|bartender|lounge|catering|hospitality|\bevents?\b|butcher|bakery|baker|cashier|shop assistant|store manager|checker|retail|hair|stylist|d[ée]cor|customer service|call cent|cleaner"),
    ("manufacturing", r"sewing|tailor|production|packag|factory"),
    ("administration", r"administrat|secretar|receptionist|office|clerk|personal assistant|records|data capture"),
    ("management_operations", r"\boperations?\b|general manager|management reporting|business partner"),
]
CASE_SENSITIVE_RULES = {
    "technology_data": r"\b(ICT|IT)\b",
    "hr_legal_compliance": r"\bHR\b",
    "health_safety": r"\b(TB|HIV|SHE)\b",
}
CI_PATTERNS = {name: re.compile(pattern, re.I) for name, pattern in CATEGORY_RULES}
CS_PATTERNS = {name: re.compile(pattern) for name, pattern in CASE_SENSITIVE_RULES.items()}

DATE_LINE_RE = re.compile(r"\b20\d\d\b|closing|deadline|apply before|end date|\d{1,2}/\d{1,2}/\d{2,4}", re.I)
WORD_NUMBERS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
YEARS_RE = re.compile(r"\b(\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten)\b[^.\n]{0,25}?\byears?\b", re.I)

MONTH_LOOKUP = {}
for number, name in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"],
    start=1,
):
    MONTH_LOOKUP[name] = number
    MONTH_LOOKUP[name[:3]] = number
MONTH_LOOKUP["sept"] = 9

TRIGGER = (
    r"(?:closing date|closing|deadline|closes|end date|apply (?:by|before)|on or before|on or around|no later than|not later than|"
    r"applications? (?:close|closes|must be (?:submitted|received) (?:by|on|before))|"
    r"(?:cover letter|\bcv\b|applications?|documents)[^.\n]{0,200}?\bby\b)"
    r"[\W_]{0,15}(?:(?:is|of|on|by|before|eob|cob|eod|close of business|end of day)[\W_]{1,5})?(?:[A-Za-z]+day,?\s+)?"
)
DAY = r"(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?([A-Za-z]{3,9})\b\.?"
MONTH = r"([A-Za-z]{3,9})\b\.?\s+(\d{1,2})(?:st|nd|rd|th)?"
DAY_FIRST_RE = re.compile(TRIGGER + DAY + r",?\s+(\d{4})", re.I)
MONTH_FIRST_RE = re.compile(TRIGGER + MONTH + r",?\s+(\d{4})", re.I)
NUMERIC_YMD_RE = re.compile(TRIGGER + r"(\d{4})[/.-](\d{1,2})[/.-](\d{1,2})\b", re.I)
NUMERIC_DMY_RE = re.compile(TRIGGER + r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4}|\d{2})\b", re.I)
DAY_NO_YEAR_RE = re.compile(TRIGGER + DAY + r"(?!,?\s*\d)", re.I)
MONTH_NO_YEAR_RE = re.compile(TRIGGER + MONTH + r"\b(?!,?\s*\d)", re.I)


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def migrate(conn):
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(opportunities)")}
    for name, definition in NEW_COLUMNS.items():
        if name not in existing:
            conn.execute("ALTER TABLE opportunities ADD COLUMN %s %s" % (name, definition))
    conn.commit()


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_PATH.read_text())
    migrate(conn)
    return conn


def role_part(title):
    index = title.lower().rfind(" at ")
    return title[:index] if index > 0 else title


def strip_trailer(text):
    return re.sub(r"\n\s*Comments\s*$", "", text).strip()


def detect_type(role, title, source_category):
    default = DEFAULT_TYPE.get(source_category, "job")
    if default != "job":
        return default
    if TENDER_RE.search(role):
        return "tender"
    if CONSULTANCY_RE.search(role):
        return "consultancy"
    if "consultant" in title.lower() and " at " not in title.lower():
        return "consultancy"
    if INTERN_RE.search(role):
        return "internship"
    return "job"


def score(text, name):
    total = len(CI_PATTERNS[name].findall(text))
    if name in CS_PATTERNS:
        total += len(CS_PATTERNS[name].findall(text))
    return total


def pick_category(text, minimum):
    best = None
    best_score = 0
    for name, _ in CATEGORY_RULES:
        value = score(text, name)
        if value > best_score:
            best = name
            best_score = value
    if best_score >= minimum:
        return best
    return None


def detect_category(role, description):
    if GOVERNMENT_RE.search(role):
        return "government_leadership"
    if ADMIN_RE.search(role):
        return "administration"
    return pick_category(role, 1) or pick_category(description[:800], 2) or "other"


def detect_level(role, opp_type):
    if opp_type == "internship":
        return "intern"
    low = role.lower().strip()
    if EXECUTIVE_RE.match(low):
        return "executive"
    if MANAGER_RE.search(low):
        return "manager"
    if SENIOR_RE.search(low):
        return "senior"
    return "standard"


def find_years_evidence(text):
    for sentence in re.split(r"(?<=[.!?])\s+|\n", text):
        if "experience" not in sentence.lower():
            continue
        match = YEARS_RE.search(sentence)
        if match:
            raw = match.group(1).lower()
            value = int(raw) if raw.isdigit() else WORD_NUMBERS[raw]
            if value <= 15:
                return value, sentence.strip()
    return None, None


def find_min_years(text):
    return find_years_evidence(text)[0]


def month_number(name):
    return MONTH_LOOKUP.get(name.lower().rstrip("."))


def make_date(year, month, day):
    try:
        return date(int(year), month, int(day)).isoformat()
    except ValueError:
        return None


def year_from_posting(month, day, posted):
    start = date.fromisoformat(posted) if posted else date.today()
    for year in (start.year, start.year + 1):
        try:
            candidate = date(year, month, day)
        except ValueError:
            continue
        if candidate >= start - timedelta(days=30):
            return candidate.isoformat()
    return None


def correct_year(deadline, posted):
    if posted is None:
        return deadline, None
    due = date.fromisoformat(deadline)
    start = date.fromisoformat(posted)
    if (start - due).days <= 90:
        return deadline, None
    for year in (start.year, start.year + 1):
        try:
            candidate = date(year, due.month, due.day)
        except ValueError:
            continue
        if candidate >= start and (candidate - start).days <= 180:
            return candidate.isoformat(), "year corrected"
    return deadline, None


def find_deadline_evidence(text, posted=None):
    for regex, day_group, month_group in ((DAY_FIRST_RE, 1, 2), (MONTH_FIRST_RE, 2, 1)):
        for match in regex.finditer(text):
            month = month_number(match.group(month_group))
            if month:
                result = make_date(match.group(3), month, match.group(day_group))
                if result:
                    result, note = correct_year(result, posted)
                    return result, " ".join(match.group(0).split()), note
    for match in NUMERIC_YMD_RE.finditer(text):
        result = make_date(match.group(1), int(match.group(2)), match.group(3))
        if result:
            result, note = correct_year(result, posted)
            return result, " ".join(match.group(0).split()), note
    for match in NUMERIC_DMY_RE.finditer(text):
        year = match.group(3)
        if len(year) == 2:
            year = "20" + year
        result = make_date(year, int(match.group(2)), match.group(1))
        if result:
            result, note = correct_year(result, posted)
            return result, " ".join(match.group(0).split()), note
    for regex, day_group, month_group in ((DAY_NO_YEAR_RE, 1, 2), (MONTH_NO_YEAR_RE, 2, 1)):
        for match in regex.finditer(text):
            month = month_number(match.group(month_group))
            if month:
                result = year_from_posting(month, int(match.group(day_group)), posted)
                if result:
                    return result, " ".join(match.group(0).split()), "year inferred"
    return None, None, None


def find_deadline(text, posted=None):
    return find_deadline_evidence(text, posted)[0]


def classify(row):
    title = row["title"]
    description = unicodedata.normalize("NFKC", strip_trailer(row["description"] or ""))
    role = role_part(title)
    opp_type = detect_type(role, title, row["source_category"])
    is_bundle = 1 if BUNDLE_RE.search(role) else 0
    category = "various" if is_bundle else detect_category(role, description)
    deadline, _, deadline_note = find_deadline_evidence(description, row["date_posted"])
    return {
        "description": description or None,
        "opp_type": opp_type,
        "category": category,
        "level": detect_level(role, opp_type),
        "min_years": find_min_years(description),
        "deadline": deadline,
        "deadline_note": deadline_note,
        "is_bundle": is_bundle,
    }


def run(conn, reclassify):
    query = "SELECT * FROM opportunities"
    if not reclassify:
        query += " WHERE classified_at IS NULL"
    rows = conn.execute(query).fetchall()
    for row in rows:
        result = classify(row)
        conn.execute(
            """UPDATE opportunities SET description = ?, opp_type = ?, category = ?, level = ?,
               min_years = ?, deadline = ?, deadline_note = ?, is_bundle = ?, classified_at = ? WHERE id = ?""",
            (result["description"], result["opp_type"], result["category"], result["level"],
             result["min_years"], result["deadline"], result["deadline_note"], result["is_bundle"], now(), row["id"]),
        )
    conn.commit()
    print("classified %d rows" % len(rows))


def print_counts(conn, column):
    print("\nby %s:" % column)
    rows = conn.execute(
        "SELECT %s AS value, COUNT(*) AS n FROM opportunities WHERE duplicate_of IS NULL GROUP BY %s ORDER BY n DESC" % (column, column)
    ).fetchall()
    for row in rows:
        print("  %-24s %d" % (row["value"], row["n"]))


def print_list(conn, heading, where, params=(), limit=60):
    rows = conn.execute(
        "SELECT title, opp_type, level, deadline FROM opportunities WHERE duplicate_of IS NULL AND %s ORDER BY date_posted DESC LIMIT %d" % (where, limit),
        params,
    ).fetchall()
    print("\n%s (%d):" % (heading, len(rows)))
    for row in rows:
        print("  [%s/%s] %s | deadline %s" % (row["opp_type"], row["level"], row["title"], row["deadline"] or "?"))


def report(conn):
    total = conn.execute("SELECT COUNT(*) FROM opportunities WHERE duplicate_of IS NULL").fetchone()[0]
    with_deadline = conn.execute("SELECT COUNT(*) FROM opportunities WHERE duplicate_of IS NULL AND deadline IS NOT NULL").fetchone()[0]
    with_years = conn.execute("SELECT COUNT(*) FROM opportunities WHERE duplicate_of IS NULL AND min_years IS NOT NULL").fetchone()[0]
    print("\n%d opportunities | deadline found for %d | years of experience found for %d" % (total, with_deadline, with_years))
    print_counts(conn, "opp_type")
    print_counts(conn, "category")
    print_counts(conn, "level")

    today = date.today()
    soon = (today + timedelta(days=7)).isoformat()
    print_list(conn, "closing in the next 7 days", "deadline >= ? AND deadline <= ?", (today.isoformat(), soon))
    notes = conn.execute(
        "SELECT title, deadline, deadline_note FROM opportunities WHERE duplicate_of IS NULL AND deadline_note IS NOT NULL ORDER BY deadline_note, date_posted DESC"
    ).fetchall()
    print("\ndeadlines where the year was corrected or inferred (%d):" % len(notes))
    for row in notes:
        print("  %s -> %s | %s" % (row["title"][:60], row["deadline"], row["deadline_note"]))
    print_list(conn, "technology_data", "category = 'technology_data'")
    print_list(conn, "other (rules did not catch these)", "category = 'other'", limit=60)
    print_list(conn, "no deadline found", "deadline IS NULL", limit=15)


def check(conn):
    rows = conn.execute(
        "SELECT title, description, date_posted FROM opportunities WHERE duplicate_of IS NULL AND description IS NOT NULL ORDER BY id"
    ).fetchall()

    print("\n--- years of experience: what the rule matched (first 15) ---")
    shown = 0
    for row in rows:
        value, sentence = find_years_evidence(row["description"])
        if value is None:
            continue
        print("%s -> %d | %s" % (row["title"][:45], value, sentence[:150]))
        shown += 1
        if shown == 15:
            break

    print("\n--- deadlines: what the rule matched (first 10) ---")
    shown = 0
    for row in rows:
        value, matched, note = find_deadline_evidence(row["description"], row["date_posted"])
        if value is None:
            continue
        print("%s -> %s | %s%s" % (row["title"][:45], value, matched[:80], " | " + note if note else ""))
        shown += 1
        if shown == 10:
            break

    print("\n--- no deadline found: lines that mention a year or a closing word (first 15 posts) ---")
    shown = 0
    for row in rows:
        if find_deadline(row["description"], row["date_posted"]) is not None:
            continue
        lines = [line for line in row["description"].split("\n") if DATE_LINE_RE.search(line)]
        print(row["title"][:70])
        for line in lines[:3]:
            print("    " + line[:260])
        if not lines:
            print("    (no such lines) tail: " + row["description"][-160:].replace("\n", " | "))
        shown += 1
        if shown == 15:
            break


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="reclassify every row, not just new ones")
    parser.add_argument("--report-only", action="store_true", help="skip classifying and print the report")
    parser.add_argument("--check", action="store_true", help="also print the evidence behind years and deadlines")
    args = parser.parse_args()

    print("classify.py v5 (more date formats)")
    conn = connect()
    if not args.report_only:
        run(conn, args.all)
    report(conn)
    if args.check:
        check(conn)


if __name__ == "__main__":
    main()