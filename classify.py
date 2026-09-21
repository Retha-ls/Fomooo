import argparse
import re
import sqlite3
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

WORD_NUMBERS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
YEARS_RE = re.compile(r"\b(\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten)\b[^.\n]{0,25}?\byears?\b", re.I)

MONTHS = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}
TRIGGER = r"(?:closing date|closing|deadline|closes|apply (?:by|before)|applications? (?:close|closes|must be (?:submitted|received) (?:by|on|before)))[\W_]{0,15}(?:(?:is|on|by|before)[\W_]{1,5})?(?:[A-Za-z]+day,?\s+)?"
DAY_FIRST_RE = re.compile(TRIGGER + r"(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?([A-Za-z]{3,9})\.?,?\s+(\d{4})", re.I)
MONTH_FIRST_RE = re.compile(TRIGGER + r"([A-Za-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})", re.I)


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_PATH.read_text())
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(opportunities)")}
    for name, definition in NEW_COLUMNS.items():
        if name not in existing:
            conn.execute("ALTER TABLE opportunities ADD COLUMN %s %s" % (name, definition))
    conn.commit()
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


def find_min_years(text):
    for sentence in re.split(r"(?<=[.!?])\s+|\n", text):
        if "experience" not in sentence.lower():
            continue
        match = YEARS_RE.search(sentence)
        if match:
            raw = match.group(1).lower()
            value = int(raw) if raw.isdigit() else WORD_NUMBERS[raw]
            if value <= 15:
                return value
    return None


def make_date(year, month, day):
    try:
        return date(int(year), month, int(day)).isoformat()
    except ValueError:
        return None


def find_deadline(text):
    for match in DAY_FIRST_RE.finditer(text):
        month = MONTHS.get(match.group(2)[:3].lower())
        if month:
            result = make_date(match.group(3), month, match.group(1))
            if result:
                return result
    for match in MONTH_FIRST_RE.finditer(text):
        month = MONTHS.get(match.group(1)[:3].lower())
        if month:
            result = make_date(match.group(3), month, match.group(2))
            if result:
                return result
    return None


def classify(row):
    title = row["title"]
    description = strip_trailer(row["description"] or "")
    role = role_part(title)
    opp_type = detect_type(role, title, row["source_category"])
    is_bundle = 1 if BUNDLE_RE.search(role) else 0
    category = "various" if is_bundle else detect_category(role, description)
    return {
        "description": description or None,
        "opp_type": opp_type,
        "category": category,
        "level": detect_level(role, opp_type),
        "min_years": find_min_years(description),
        "deadline": find_deadline(description),
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
               min_years = ?, deadline = ?, is_bundle = ?, classified_at = ? WHERE id = ?""",
            (result["description"], result["opp_type"], result["category"], result["level"],
             result["min_years"], result["deadline"], result["is_bundle"], now(), row["id"]),
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
    print_list(conn, "technology_data", "category = 'technology_data'")
    print_list(conn, "other (rules did not catch these)", "category = 'other'", limit=60)
    print_list(conn, "no deadline found", "deadline IS NULL", limit=15)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="reclassify every row, not just new ones")
    parser.add_argument("--report-only", action="store_true", help="skip classifying and print the report")
    args = parser.parse_args()

    conn = connect()
    if not args.report_only:
        run(conn, args.all)
    report(conn)


if __name__ == "__main__":
    main()
