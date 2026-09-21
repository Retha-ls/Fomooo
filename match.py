import argparse
import json
import re
import sqlite3
from datetime import date
from pathlib import Path

FOLDER = Path(__file__).parent
DB_PATH = FOLDER / "opportunities.db"
PROFILE_PATH = FOLDER / "profile.json"

SKILL_PATTERNS = {
    "python": r"\bpython\b",
    "java": r"\bjava\b(?!\s?script)",
    "javascript": r"\bjava\s?script\b",
    "typescript": r"\btypescript\b",
    "php": r"\bphp\b",
    "c++": r"(?<![A-Za-z0-9])c\+\+",
    "c#": r"(?<![A-Za-z0-9])c#",
    "html": r"\bhtml5?\b",
    "css": r"\bcss3?\b",
    "node.js": r"\bnode\.?js\b",
    "angular": r"\bangular(?:js)?\b",
    "vue": r"\bvue(?:\.?js)?\b",
    "laravel": r"\blaravel\b",
    "django": r"\bdjango\b",
    "flask": r"\bflask\b",
    "wordpress": r"\bwordpress\b",
    "android": r"\bandroid\b",
    "flutter": r"\bflutter\b",
    "sql": r"\bsql\b",
    "mysql": r"\bmysql\b",
    "postgresql": r"\bpostgres(?:ql)?\b",
    "mongodb": r"\bmongodb\b",
    "sql server": r"\bsql server\b",
    "git": r"\bgit\b|\bgithub\b|\bgitlab\b",
    "docker": r"\bdocker\b",
    "kubernetes": r"\bkubernetes\b",
    "aws": r"\baws\b|amazon web services",
    "azure": r"\bazure\b",
    "linux": r"\blinux\b",
    "api": r"\bapis?\b",
    "power bi": r"\bpower\s?bi\b",
    "tableau": r"\btableau\b",
    "spss": r"\bspss\b",
    "stata": r"\bstata\b",
    "statistics": r"\bstatistic(?:s|al)\b",
    "machine learning": r"\bmachine learning\b|\bdeep learning\b",
    "data analysis": r"\bdata (?:analysis|analytics|analyst)\b",
    "data science": r"\bdata scien(?:ce|tist)\b",
    "nlp": r"\bnlp\b|natural language processing",
    "tensorflow": r"\btensorflow\b",
    "pytorch": r"\bpytorch\b",
    "pandas": r"\bpandas\b",
    "networks": r"\bnetwork (?:administration|security|infrastructure)\b|\bccna\b|\bcisco\b",
    "cybersecurity": r"\bcyber\s?security\b|\binformation security\b",
    "erp": r"\berp\b",
    "ms office": r"\bmicrosoft office\b|\bms office\b|\boffice 365\b",
    "figma": r"\bfigma\b",
    "photoshop": r"\bphotoshop\b|\billustrator\b|\bcoreldraw\b",
}
CASE_SENSITIVE_SKILLS = {
    "react": r"\bReact(?:\.?js)?\b",
    "ai": r"\bAI\b",
    "excel": r"\bExcel\b",
    "oracle": r"\bOracle\b",
    "sap": r"\bSAP\b",
}
CI_PATTERNS = {name: re.compile(pattern, re.I) for name, pattern in SKILL_PATTERNS.items()}
CS_PATTERNS = {name: re.compile(pattern) for name, pattern in CASE_SENSITIVE_SKILLS.items()}

LEVEL_FACTOR = {"intern": 1.0, "standard": 1.0, "senior": 0.6, "manager": 0.4, "executive": 0.2}


def load_profile():
    if not PROFILE_PATH.exists():
        raise SystemExit("profile.json not found next to match.py")
    profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    profile["skills"] = [skill.lower() for skill in profile.get("skills", [])]
    profile.setdefault("interest_categories", [])
    profile.setdefault("accepted_types", ["job", "internship"])
    profile.setdefault("years_experience", 0)
    return profile


def extract_skills(text):
    found = set()
    for name, pattern in CI_PATTERNS.items():
        if pattern.search(text):
            found.add(name)
    for name, pattern in CS_PATTERNS.items():
        if pattern.search(text):
            found.add(name)
    return found


def experience_factor(job, years):
    need = job["min_years"]
    if need is None:
        return LEVEL_FACTOR.get(job["level"], 1.0), "no years stated, level: %s" % job["level"]
    if need <= years:
        return 1.0, "needs %d years, you have %d" % (need, years)
    return max(0.2, 1.0 - 0.2 * (need - years)), "needs %d years, you have %d" % (need, years)


def score_job(job, profile):
    job_skills = extract_skills(job["description"] or "")
    have = set(profile["skills"])
    matched = sorted(job_skills & have)
    missing = sorted(job_skills - have)
    skill_part = len(matched) / len(job_skills) if job_skills else 0.0
    category_ok = job["category"] in profile["interest_categories"]
    relevance = 0.6 * skill_part + 0.4 * (1.0 if category_ok else 0.0)
    experience, experience_note = experience_factor(job, profile["years_experience"])
    type_ok = job["opp_type"] in profile["accepted_types"]
    total = 100.0 * relevance * experience * (1.0 if type_ok else 0.0)
    return {
        "score": round(total),
        "matched": matched,
        "missing": missing,
        "job_skills": sorted(job_skills),
        "category_ok": category_ok,
        "experience_note": experience_note,
        "type_ok": type_ok,
    }


def label(score):
    if score >= 70:
        return "strong"
    if score >= 40:
        return "possible"
    return "low"


def deadline_text(deadline, today):
    if deadline is None:
        return "no deadline listed"
    days = (date.fromisoformat(deadline) - today).days
    if days == 0:
        return "closes TODAY"
    if days < 0:
        return "closed %s" % deadline
    return "closes %s (%d days)" % (deadline, days)


def connect():
    if not DB_PATH.exists():
        raise SystemExit("opportunities.db not found, run scraper.py and classify.py first")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def open_posts(conn, today):
    return conn.execute(
        "SELECT * FROM opportunities WHERE duplicate_of IS NULL AND (deadline IS NULL OR deadline >= ?)",
        (today.isoformat(),),
    ).fetchall()


def print_result(job, result, today):
    print("%3d %-8s %s [%s/%s] %s" % (
        result["score"], label(result["score"]), job["title"], job["opp_type"], job["category"],
        deadline_text(job["deadline"], today)))
    print("      skills: %s | missing: %s" % (", ".join(result["matched"]) or "none", ", ".join(result["missing"]) or "none"))
    print("      experience: %s | category match: %s" % (result["experience_note"], "yes" if result["category_ok"] else "no"))
    print("      " + job["source_url"])


def show_ranking(conn, profile, top):
    today = date.today()
    posts = open_posts(conn, today)
    scored = []
    for job in posts:
        result = score_job(job, profile)
        if result["score"] > 0:
            scored.append((result["score"], job, result))
    scored.sort(key=lambda item: item[0], reverse=True)
    print("\n%d of %d open posts score above zero for your profile\n" % (len(scored), len(posts)))
    for _, job, result in scored[:top]:
        print_result(job, result, today)
        print()


def show_why(conn, profile, text):
    today = date.today()
    rows = conn.execute(
        "SELECT * FROM opportunities WHERE duplicate_of IS NULL AND title LIKE ?", ("%" + text + "%",)
    ).fetchall()
    if not rows:
        print("no post title contains '%s'" % text)
    for job in rows:
        result = score_job(job, profile)
        print()
        print_result(job, result, today)
        print("      skills the post mentions: %s" % (", ".join(result["job_skills"]) or "none"))
        print("      type accepted by your profile: %s" % ("yes" if result["type_ok"] else "no"))


def show_market(conn, profile):
    today = date.today()
    posts = open_posts(conn, today)
    counts = {}
    with_skills = 0
    for job in posts:
        found = extract_skills(job["description"] or "")
        if found:
            with_skills += 1
        for name in found:
            counts[name] = counts.get(name, 0) + 1
    have = set(profile["skills"])
    print("\nskills mentioned across %d open posts (%d mention at least one)\n" % (len(posts), with_skills))
    for name, count in sorted(counts.items(), key=lambda item: item[1], reverse=True):
        print("  %-18s %3d posts %s" % (name, count, "(you have this)" if name in have else ""))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--top", type=int, default=15, help="how many ranked posts to show")
    parser.add_argument("--why", help="explain the score for posts whose title contains this text")
    parser.add_argument("--market", action="store_true", help="show which skills the open posts ask for")
    args = parser.parse_args()

    profile = load_profile()
    conn = connect()
    if args.why:
        show_why(conn, profile, args.why)
    elif args.market:
        show_market(conn, profile)
    else:
        show_ranking(conn, profile, args.top)


if __name__ == "__main__":
    main()
