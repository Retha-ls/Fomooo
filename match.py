import argparse
import json
import re
import sqlite3
from pathlib import Path
from datetime import date, datetime


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "opportunities.db"
PROFILE_PATH = BASE_DIR / "profile.json"


SKILL_PATTERNS = {
    "python": r"\bpython\b",
    "java": r"\bjava\b",
    "javascript": r"\bjavascript\b|\bjava script\b|\bjs\b",
    "typescript": r"\btypescript\b",
    "php": r"\bphp\b",
    "c++": r"\bc\+\+\b",
    "c#": r"\bc#\b",
    "html": r"\bhtml\b",
    "css": r"\bcss\b",
    "react.js": r"\breact\.?js\b|\breact js\b",
    "next.js": r"\bnext\.?js\b|\bnext js\b",
    "react native": r"\breact native\b",
    "node.js": r"\bnode\.?js\b|\bnode js\b|\bnodejs\b",
    "express.js": r"\bexpress\.?js\b|\bexpress js\b",
    "angular": r"\bangular\b",
    "vue": r"\bvue\.?js\b|\bvue js\b",
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
    "nosql": r"\bno[\s-]?sql\b",
    "git": r"\bgit\b",
    "github": r"\bgithub\b",
    "docker": r"\bdocker\b",
    "kubernetes": r"\bkubernetes\b",
    "aws": r"\baws\b|\bamazon web services\b",
    "azure": r"\bazure\b",
    "linux": r"\blinux\b",
    "api": r"\bapis?\b|\bapi development\b",
    "power bi": r"\bpower\s*bi\b",
    "tableau": r"\btableau\b",
    "spss": r"\bspss\b",
    "stata": r"\bstata\b",
    "statistics": r"\bstatistics\b|\bstatistical\b",
    "machine learning": r"\bmachine learning\b",
    "data analysis": r"\bdata analysis\b|\bdata analyst\b|\banaly[sz]ing data\b",
    "data science": r"\bdata science\b|\bdata scientist\b",
    "nlp": r"\bnlp\b|\bnatural language processing\b",
    "tensorflow": r"\btensorflow\b",
    "pytorch": r"\bpytorch\b",
    "pandas": r"\bpandas\b",
    "numpy": r"\bnumpy\b",
    "scikit-learn": r"\bscikit[- ]learn\b|\bsklearn\b",
    "networks": r"\b(?:computer\s+networks?|network\s+administration|network\s+security|network\s+engineer|it\s+networking)\b",
    "cybersecurity": r"\bcyber\s*security\b|\bcybersecurity\b",
    "erp": r"\berp\b",
    "ms office": r"\bms office\b|\bmicrosoft office\b|\boffice suite\b",
    "figma": r"\bfigma\b",
    "photoshop": r"\bphotoshop\b",
    "excel": r"\bexcel\b|\bmicrosoft excel\b",
    "oracle": r"\boracle\b",
    "sap": r"\bsap\b"
}


PROFILE_SKILL_ALIASES = {
    "js": "javascript",
    "javascript": "javascript",
    "node": "node.js",
    "nodejs": "node.js",
    "node.js": "node.js",
    "react": "react.js",
    "reactjs": "react.js",
    "react.js": "react.js",
    "next": "next.js",
    "nextjs": "next.js",
    "next.js": "next.js",
    "express": "express.js",
    "expressjs": "express.js",
    "express.js": "express.js",
    "c++": "c++",
    "c#": "c#",
    "mysql": "mysql",
    "sql": "sql",
    "git": "git",
    "github": "github",
    "statistics": "statistics"
}


CATEGORY_LABELS = {
    "technology_data": "Technology / Data",
    "engineering_trades": "Engineering / Trades",
    "hospitality_retail": "Hospitality / Retail",
    "sales_marketing": "Sales / Marketing",
    "logistics_transport": "Logistics / Transport",
    "education": "Education",
    "development_ngo": "Development / NGO",
    "hr_legal_compliance": "HR / Legal / Compliance",
    "health_safety": "Health / Safety",
    "finance_banking": "Finance / Banking",
    "government_leadership": "Government / Leadership",
    "media_language": "Media / Language",
    "administration": "Administration",
    "management_operations": "Management / Operations",
    "manufacturing": "Manufacturing",
    "various": "Various"
}


REQUIRED_SECTION_HEADERS = [
    "requirements",
    "required requirements",
    "required skills",
    "essential skills",
    "essential requirements",
    "minimum requirements",
    "minimum qualifications",
    "qualifications",
    "qualification",
    "key requirements",
    "key skills",
    "technical skills",
    "technical requirements",
    "skills required",
    "competencies",
    "core competencies",
    "knowledge and skills",
    "knowledge & skills",
    "skills and competencies"
]


PREFERRED_SECTION_HEADERS = [
    "preferred skills",
    "preferred requirements",
    "preferred qualifications",
    "desirable skills",
    "desirable qualifications",
    "desired skills",
    "advantageous",
    "additional skills",
    "additional qualifications",
    "added advantage",
    "advantages",
    "nice to have",
    "bonus skills"
]


TECHNICAL_SECTION_HEADERS = [
    "key responsibilities",
    "responsibilities",
    "duties",
    "technical responsibilities",
    "role description",
    "role responsibilities",
    "what you will do",
    "what you'll do",
    "what you will be doing"
]


SECTION_STOP_HEADERS = [
    "job description",
    "about the company",
    "about us",
    "how to apply",
    "application process",
    "salary",
    "benefits",
    "closing date",
    "deadline",
    "contact",
    "location",
    "job summary",
    "role summary",
    "desired personal attributes",
    "personal attributes",
    "remote work requirements",
    "what we offer"
]


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def load_profile():
    with open(PROFILE_PATH, "r", encoding="utf-8") as file:
        profile = json.load(file)

    if "skills" not in profile:
        profile["skills"] = []

    if "interest_categories" not in profile:
        profile["interest_categories"] = []

    if "accepted_types" not in profile:
        profile["accepted_types"] = [
            "job",
            "internship"
        ]

    if "years_experience" not in profile:
        profile["years_experience"] = 0

    if "education" not in profile:
        profile["education"] = {
            "degree": "",
            "fields": []
        }

    return profile


def normalize_text(text):
    if not text:
        return ""

    text = text.lower()
    text = text.replace("–", "-")
    text = text.replace("—", "-")
    text = text.replace("’", "'")
    text = text.replace("\xa0", " ")

    return text


def normalize_skill(skill):
    skill = normalize_text(skill).strip()

    if skill in PROFILE_SKILL_ALIASES:
        return PROFILE_SKILL_ALIASES[skill]

    return skill


def normalize_profile_skills(profile):
    result = set()

    for skill in profile.get("skills", []):
        result.add(
            normalize_skill(skill)
        )

    return result


def split_lines(text):
    if not text:
        return []

    text = text.replace("\r", "\n")

    lines = text.split("\n")

    result = []

    for line in lines:
        line = line.strip()

        if line:
            result.append(line)

    return result


def split_sentences(text):
    if not text:
        return []

    text = text.replace("\r", "\n")

    parts = re.split(
        r"(?<=[.!?])\s+|\n+|;",
        text
    )

    return [
        part.strip()
        for part in parts
        if part.strip()
    ]


def find_skill_mentions(text):
    text = normalize_text(text)

    found = {}

    for skill, pattern in SKILL_PATTERNS.items():

        matches = list(
            re.finditer(
                pattern,
                text,
                re.IGNORECASE
            )
        )

        if matches:
            found[skill] = matches

    return found


def is_requirement_context(sentence):
    text = normalize_text(sentence)

    words = [
        "required",
        "requirements",
        "requirement",
        "must have",
        "must possess",
        "should have",
        "should possess",
        "essential",
        "essential skills",
        "minimum requirement",
        "minimum requirements",
        "qualification",
        "qualifications",
        "competencies",
        "competence",
        "proficiency",
        "proficient",
        "experience with",
        "experience in",
        "knowledge of",
        "knowledge in",
        "skills in",
        "technical skills",
        "computer skills",
        "applicants should",
        "candidate should",
        "candidate must",
        "ability to use",
        "ability in",
        "proven ability",
        "familiarity with",
        "familiar with"
    ]

    for word in words:
        if word in text:
            return True

    return False


def is_preferred_context(sentence):
    text = normalize_text(sentence)

    words = [
        "preferred",
        "desirable",
        "advantage",
        "added advantage",
        "an advantage",
        "would be an advantage",
        "plus",
        "nice to have",
        "additional",
        "bonus",
        "if available"
    ]

    for word in words:
        if word in text:
            return True

    return False


def is_incidental_context(sentence):
    text = normalize_text(sentence)

    words = [
        "reporting statistics",
        "monthly statistics",
        "annual statistics",
        "statistics report",
        "statistical report",
        "statistics are",
        "statistics is",
        "data collected",
        "data will be",
        "data from",
        "data available",
        "information about",
        "website",
        "company website",
        "social media",
        "contact us"
    ]

    for word in words:
        if word in text:
            return True

    return False


def clean_header(text):
    text = normalize_text(text)

    text = re.sub(
        r"^[\s\-•*▪◦●]+",
        "",
        text
    )

    text = re.sub(
        r"[:\-]+$",
        "",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


def header_type(line):
    cleaned = clean_header(line)

    for header in REQUIRED_SECTION_HEADERS:

        if cleaned == header:
            return "required"

        if cleaned.startswith(header + ":"):
            return "required"

    for header in PREFERRED_SECTION_HEADERS:

        if cleaned == header:
            return "preferred"

        if cleaned.startswith(header + ":"):
            return "preferred"

    for header in TECHNICAL_SECTION_HEADERS:

        if cleaned == header:
            return "technical"

        if cleaned.startswith(header + ":"):
            return "technical"

    return None


def is_section_stop(line):
    cleaned = clean_header(line)

    for header in SECTION_STOP_HEADERS:

        if cleaned == header:
            return True

        if cleaned.startswith(header + ":"):
            return True

    return False


def extract_section_skills(description):
    lines = split_lines(description)

    required = set()
    preferred = set()
    technical = set()

    current_section = None

    for line in lines:

        section = header_type(line)

        if section:
            current_section = section
            continue

        if is_section_stop(line):
            current_section = None
            continue

        if current_section is None:
            continue

        skills = find_skill_mentions(line)

        if not skills:
            continue

        preferred_context = is_preferred_context(line)

        for skill in skills:

            if preferred_context:
                preferred.add(skill)

            elif current_section == "required":
                required.add(skill)

            elif current_section == "preferred":
                preferred.add(skill)

            elif current_section == "technical":
                technical.add(skill)

    return required, preferred, technical


def extract_job_skills(description):
    required = set()
    preferred = set()
    technical = set()
    incidental = set()

    section_required, section_preferred, section_technical = (
        extract_section_skills(description)
    )

    required.update(section_required)
    preferred.update(section_preferred)
    technical.update(section_technical)

    sentences = split_sentences(description)

    for sentence in sentences:

        skills = find_skill_mentions(sentence)

        if not skills:
            continue

        requirement = is_requirement_context(sentence)
        preferred_context = is_preferred_context(sentence)
        incidental_context = is_incidental_context(sentence)

        for skill in skills:

            if incidental_context:
                incidental.add(skill)
                continue

            if preferred_context:
                preferred.add(skill)
                continue

            if skill in preferred:
                continue

            if skill in required:
                continue

            if skill in technical:
                continue

            if requirement:
                required.add(skill)
                continue

            technical.add(skill)

    required = required - preferred - incidental
    preferred = preferred - incidental
    technical = technical - required - preferred - incidental

    return {
        "required": required,
        "preferred": preferred,
        "technical": technical,
        "incidental": incidental
    }


def extract_all_job_skills(description):
    found = find_skill_mentions(description)

    return set(
        found.keys()
    )


def extract_education(description):
    text = normalize_text(description)

    education_terms = [
        "computer science",
        "computer sciences",
        "information technology",
        "information systems",
        "software engineering",
        "computer engineering",
        "data science",
        "statistics",
        "mathematics",
        "applied mathematics",
        "economics",
        "business administration",
        "business management",
        "accounting",
        "finance",
        "engineering",
        "cybersecurity",
        "cyber security"
    ]

    education_context = [
        "degree",
        "diploma",
        "bachelor",
        "bachelors",
        "bachelor's",
        "master",
        "masters",
        "master's",
        "qualification",
        "qualifications",
        "graduate",
        "academic",
        "field of study",
        "studied"
    ]

    found = set()

    for sentence in split_sentences(description):

        sentence_lower = normalize_text(sentence)

        has_context = False

        for context in education_context:

            if context in sentence_lower:
                has_context = True
                break

        if not has_context:
            continue

        for term in education_terms:

            if term in sentence_lower:
                found.add(term)

    return found


def profile_education(profile):
    education = profile.get(
        "education",
        {}
    )

    degree = education.get(
        "degree",
        ""
    )

    fields = education.get(
        "fields",
        []
    )

    combined = normalize_text(
        degree +
        " " +
        " ".join(fields)
    )

    aliases = {
        "computer science": "computer science",
        "computer sciences": "computer science",
        "information technology": "information technology",
        "information systems": "information systems",
        "software engineering": "software engineering",
        "computer engineering": "computer engineering",
        "data science": "data science",
        "statistics": "statistics",
        "mathematics": "mathematics",
        "engineering": "engineering",
        "cybersecurity": "cybersecurity",
        "cyber security": "cybersecurity"
    }

    result = set()

    for term, normalized in aliases.items():

        if term in combined:
            result.add(normalized)

    return result


def normalize_education(term):
    aliases = {
        "computer sciences": "computer science",
        "cyber security": "cybersecurity"
    }

    return aliases.get(
        term,
        term
    )


def education_match(description, profile):
    required = extract_education(
        description
    )

    required = {
        normalize_education(item)
        for item in required
    }

    user = profile_education(
        profile
    )

    matched = required.intersection(
        user
    )

    return required, matched


def find_required_experience(text):
    text = normalize_text(text)

    patterns = [
        r"(\d+)\s*\+?\s*years?\s*(?:of\s*)?experience",
        r"minimum\s*(?:of\s*)?(\d+)\s*years?",
        r"at least\s*(\d+)\s*years?",
        r"(\d+)\s*-\s*\d+\s*years?\s*(?:of\s*)?experience",
        r"(\d+)\s*yrs?\s*(?:of\s*)?experience"
    ]

    values = []

    for pattern in patterns:

        matches = re.findall(
            pattern,
            text
        )

        for value in matches:

            try:
                values.append(
                    int(value)
                )
            except:
                pass

    if not values:
        return None

    return max(values)


def experience_result(job, profile):
    required = job["min_years"]

    user_years = profile.get(
        "years_experience",
        0
    )

    if required is None:
        return {
            "required": None,
            "user": user_years,
            "gap": 0,
            "factor": 1.0,
            "status": "not stated"
        }

    gap = required - user_years

    if gap <= 0:
        return {
            "required": required,
            "user": user_years,
            "gap": 0,
            "factor": 1.0,
            "status": "meets requirement"
        }

    factor = max(
        0.35,
        1.0 - (
            gap * 0.12
        )
    )

    return {
        "required": required,
        "user": user_years,
        "gap": gap,
        "factor": factor,
        "status": "experience gap"
    }


def category_match(job, profile):
    category = job["category"]

    interests = profile.get(
        "interest_categories",
        []
    )

    return category in interests


def accepted_type(job, profile):
    accepted = profile.get(
        "accepted_types",
        []
    )

    return job["opp_type"] in accepted


def deadline_status(deadline):
    if not deadline:
        return "no deadline"

    try:
        deadline_date = datetime.strptime(
            deadline,
            "%Y-%m-%d"
        ).date()

    except:
        return "unknown"

    today = date.today()

    if deadline_date < today:
        return "closed"

    if deadline_date == today:
        return "today"

    days = (
        deadline_date - today
    ).days

    if days == 1:
        return "1 day"

    return str(days) + " days"


def format_deadline(deadline):
    if not deadline:
        return "no deadline listed"

    status = deadline_status(
        deadline
    )

    if status == "closed":
        return "CLOSED (" + deadline + ")"

    if status == "today":
        return "TODAY"

    if status == "1 day":
        return "tomorrow (" + deadline + ")"

    return (
        deadline +
        " (" +
        status +
        ")"
    )


def calculate_skill_result(
    job_skills,
    profile_skills
):
    required = job_skills["required"]
    preferred = job_skills["preferred"]
    technical = job_skills["technical"]

    matched_required = required.intersection(
        profile_skills
    )

    matched_preferred = preferred.intersection(
        profile_skills
    )

    matched_technical = technical.intersection(
        profile_skills
    )

    missing_required = (
        required -
        profile_skills
    )

    missing_preferred = (
        preferred -
        profile_skills
    )

    missing_technical = (
        technical -
        profile_skills
    )

    if required:
        required_ratio = (
            len(matched_required) /
            len(required)
        )
    else:
        required_ratio = 0

    if preferred:
        preferred_ratio = (
            len(matched_preferred) /
            len(preferred)
        )
    else:
        preferred_ratio = 0

    if required:
        score = (
            required_ratio * 0.80 +
            preferred_ratio * 0.20
        )

    elif preferred:
        score = preferred_ratio

    else:
        score = 0

    return {
        "score": score,
        "required": required,
        "preferred": preferred,
        "technical": technical,
        "incidental": job_skills["incidental"],
        "matched_required": matched_required,
        "matched_preferred": matched_preferred,
        "matched_technical": matched_technical,
        "missing_required": missing_required,
        "missing_preferred": missing_preferred,
        "missing_technical": missing_technical
    }


def calculate_score(job, profile):
    description = job["description"] or ""

    job_skills = extract_job_skills(
        description
    )

    all_skills = extract_all_job_skills(
        description
    )

    profile_skills = normalize_profile_skills(
        profile
    )

    skills = calculate_skill_result(
        job_skills,
        profile_skills
    )

    required_education, matched_education = education_match(
        description,
        profile
    )

    experience = experience_result(
        job,
        profile
    )

    category_ok = category_match(
        job,
        profile
    )

    type_ok = accepted_type(
        job,
        profile
    )

    deadline = deadline_status(
        job["deadline"]
    )

    education_score = 0

    if required_education:
        education_score = (
            len(matched_education) /
            len(required_education)
        )

    evidence = []

    if skills["matched_required"]:
        evidence.append(
            "required skill"
        )

    if skills["matched_preferred"]:
        evidence.append(
            "preferred skill"
        )

    if skills["matched_technical"]:
        evidence.append(
            "technical context"
        )

    if matched_education:
        evidence.append(
            "education"
        )

    if category_ok:
        evidence.append(
            "category"
        )

    has_direct_evidence = (
        bool(
            skills["matched_required"]
        ) or
        bool(
            skills["matched_preferred"]
        ) or
        bool(
            matched_education
        )
    )

    if not has_direct_evidence:

        if category_ok:
            base_score = 15
        else:
            base_score = 0

    else:

        skill_component = (
            skills["score"] *
            55
        )

        education_component = (
            education_score *
            20
        )

        category_component = (
            20
            if category_ok
            else 0
        )

        base_score = (
            skill_component +
            education_component +
            category_component
        )

    score = base_score

    score *= experience["factor"]

    if not type_ok:
        score = 0

    if deadline == "closed":
        score *= 0.25

    elif deadline == "today":
        score *= 1.0

    score = round(
        min(
            100,
            score
        )
    )

    return {
        "score": score,
        "skills": skills,
        "all_skills": all_skills,
        "required_education": required_education,
        "matched_education": matched_education,
        "education_score": education_score,
        "experience": experience,
        "category_ok": category_ok,
        "type_ok": type_ok,
        "deadline": deadline,
        "has_direct_evidence": has_direct_evidence,
        "evidence": evidence
    }


def open_posts(conn):
    today = date.today().isoformat()

    return conn.execute(
        """
        SELECT *
        FROM opportunities
        WHERE duplicate_of IS NULL
        AND (
            deadline IS NULL
            OR deadline >= ?
        )
        ORDER BY
            CASE
                WHEN deadline IS NULL THEN 1
                ELSE 0
            END,
            deadline ASC,
            id DESC
        """,
        (today,)
    ).fetchall()


def all_posts(conn):
    return conn.execute(
        """
        SELECT *
        FROM opportunities
        WHERE duplicate_of IS NULL
        ORDER BY id DESC
        """
    ).fetchall()


def format_category(category):
    return CATEGORY_LABELS.get(
        category,
        category or "Unknown"
    )


def print_set(values):
    if not values:
        return ""

    return ", ".join(
        sorted(values)
    )


def show_ranking(conn, profile):
    rows = open_posts(conn)

    results = []

    for job in rows:

        result = calculate_score(
            job,
            profile
        )

        if result["score"] > 0:

            results.append(
                (
                    result["score"],
                    job,
                    result
                )
            )

    results.sort(
        key=lambda item: (
            -item[0],
            item[1]["deadline"] is None,
            item[1]["deadline"] or "9999-99-99"
        )
    )

    print()

    print(
        str(len(rows)) +
        " open opportunities"
    )

    print(
        str(len(results)) +
        " have a positive match score"
    )

    print()

    if not results:

        print(
            "No matching opportunities found."
        )

        return

    for number, item in enumerate(
        results,
        1
    ):

        score, job, result = item

        print(
            str(number) +
            ". " +
            str(score) +
            "/100  " +
            job["title"]
        )

        print(
            "   [" +
            str(job["opp_type"]) +
            "/" +
            format_category(
                job["category"]
            ) +
            "]"
        )

        print(
            "   deadline: " +
            format_deadline(
                job["deadline"]
            )
        )

        skills = result["skills"]

        matched = (
            skills["matched_required"] |
            skills["matched_preferred"] |
            skills["matched_technical"]
        )

        missing = (
            skills["missing_required"] |
            skills["missing_preferred"]
        )

        if matched:

            print(
                "   skills matched: " +
                print_set(matched)
            )

        if missing:

            print(
                "   skills missing: " +
                print_set(missing)
            )

        if result["matched_education"]:

            print(
                "   education matched: " +
                print_set(
                    result["matched_education"]
                )
            )

        experience = result["experience"]

        if experience["required"] is None:

            print(
                "   experience: no years stated"
            )

        elif experience["gap"] > 0:

            print(
                "   experience gap: needs " +
                str(
                    experience["required"]
                ) +
                " years, you have " +
                str(
                    experience["user"]
                )
            )

        else:

            print(
                "   experience: requirement met"
            )

        if result["category_ok"]:

            print(
                "   category: MATCH"
            )

        print()


def show_why(conn, profile, term):
    rows = conn.execute(
        """
        SELECT *
        FROM opportunities
        WHERE duplicate_of IS NULL
        AND (
            title LIKE ?
            OR company LIKE ?
            OR description LIKE ?
        )
        ORDER BY id DESC
        """,
        (
            "%" + term + "%",
            "%" + term + "%",
            "%" + term + "%"
        )
    ).fetchall()

    if not rows:

        print(
            "No opportunity found for: " +
            term
        )

        return

    for job in rows:

        result = calculate_score(
            job,
            profile
        )

        print()
        print("=" * 70)
        print(job["title"])
        print("=" * 70)

        print(
            "Score: " +
            str(result["score"]) +
            "/100"
        )

        print(
            "Type: " +
            str(job["opp_type"])
        )

        print(
            "Category: " +
            format_category(
                job["category"]
            )
        )

        print(
            "Deadline: " +
            format_deadline(
                job["deadline"]
            )
        )

        print()

        print("SKILLS")

        skills = result["skills"]

        if skills["required"]:

            print(
                "  Required: " +
                print_set(
                    skills["required"]
                )
            )

        if skills["preferred"]:

            print(
                "  Preferred: " +
                print_set(
                    skills["preferred"]
                )
            )

        if skills["technical"]:

            print(
                "  Technical context: " +
                print_set(
                    skills["technical"]
                )
            )

        if skills["incidental"]:

            print(
                "  Incidental mentions: " +
                print_set(
                    skills["incidental"]
                )
            )

        if skills["matched_required"]:

            print(
                "  Required matched: " +
                print_set(
                    skills["matched_required"]
                )
            )

        else:

            print(
                "  Required matched: none"
            )

        if skills["matched_preferred"]:

            print(
                "  Preferred matched: " +
                print_set(
                    skills["matched_preferred"]
                )
            )

        if skills["matched_technical"]:

            print(
                "  Technical context matched: " +
                print_set(
                    skills["matched_technical"]
                )
            )

        if skills["missing_required"]:

            print(
                "  Required missing: " +
                print_set(
                    skills["missing_required"]
                )
            )

        if skills["missing_preferred"]:

            print(
                "  Preferred missing: " +
                print_set(
                    skills["missing_preferred"]
                )
            )

        if (
            not skills["required"] and
            not skills["preferred"] and
            not skills["technical"]
        ):

            print(
                "  No clear skill information detected"
            )

        print()

        print("EDUCATION")

        if result["required_education"]:

            print(
                "  Job mentions: " +
                print_set(
                    result["required_education"]
                )
            )

            if result["matched_education"]:

                print(
                    "  Your matching fields: " +
                    print_set(
                        result["matched_education"]
                    )
                )

            else:

                print(
                    "  Your education: no detected match"
                )

        else:

            print(
                "  No clear education requirement detected"
            )

        print()

        print("EXPERIENCE")

        experience = result["experience"]

        if experience["required"] is None:

            print(
                "  No years of experience detected"
            )

        elif experience["gap"] > 0:

            print(
                "  Required: " +
                str(
                    experience["required"]
                ) +
                " years"
            )

            print(
                "  Your experience: " +
                str(
                    experience["user"]
                ) +
                " years"
            )

            print(
                "  Gap: " +
                str(
                    experience["gap"]
                ) +
                " years"
            )

        else:

            print(
                "  Requirement met: " +
                str(
                    experience["required"]
                ) +
                " years"
            )

        print()

        print("PROFILE FIT")

        if result["category_ok"]:

            print(
                "  Category: MATCH"
            )

        else:

            print(
                "  Category: outside selected interests"
            )

        if result["type_ok"]:

            print(
                "  Opportunity type: accepted"
            )

        else:

            print(
                "  Opportunity type: not accepted"
            )

        print()

        print("URL")

        print(
            "  " +
            job["source_url"]
        )

        print()


def show_market(conn, profile):
    rows = open_posts(conn)

    market = {}

    for job in rows:

        skills = extract_job_skills(
            job["description"] or ""
        )

        for skill in skills["required"]:

            if skill not in market:

                market[skill] = {
                    "required": 0,
                    "preferred": 0,
                    "technical": 0
                }

            market[skill]["required"] += 1

        for skill in skills["preferred"]:

            if skill not in market:

                market[skill] = {
                    "required": 0,
                    "preferred": 0,
                    "technical": 0
                }

            market[skill]["preferred"] += 1

        for skill in skills["technical"]:

            if skill not in market:

                market[skill] = {
                    "required": 0,
                    "preferred": 0,
                    "technical": 0
                }

            market[skill]["technical"] += 1

    profile_skills = normalize_profile_skills(
        profile
    )

    print()

    print(
        "Market skill demand across " +
        str(len(rows)) +
        " open opportunities"
    )

    print()

    if not market:

        print(
            "No recognizable skill information found."
        )

        return

    sorted_market = sorted(
        market.items(),
        key=lambda item: (
            -(
                item[1]["required"] +
                item[1]["preferred"] +
                item[1]["technical"]
            ),
            item[0]
        )
    )

    for skill, data in sorted_market:

        total = (
            data["required"] +
            data["preferred"] +
            data["technical"]
        )

        status = ""

        if skill in profile_skills:

            status = "  <-- YOU HAVE THIS"

        print(
            "  " +
            skill.ljust(20) +
            str(total).rjust(3) +
            " posts" +
            " | required: " +
            str(
                data["required"]
            ) +
            " | preferred: " +
            str(
                data["preferred"]
            ) +
            " | technical: " +
            str(
                data["technical"]
            ) +
            status
        )


def show_profile(profile):
    print()
    print("PROFILE")
    print("=" * 50)

    print(
        "Experience: " +
        str(
            profile.get(
                "years_experience",
                0
            )
        ) +
        " years"
    )

    print(
        "Skills: " +
        print_set(
            normalize_profile_skills(
                profile
            )
        )
    )

    education = profile.get(
        "education",
        {}
    )

    if education.get("degree"):

        print(
            "Degree: " +
            education["degree"]
        )

    if education.get("fields"):

        print(
            "Fields: " +
            ", ".join(
                education["fields"]
            )
        )

    print(
        "Interested categories: " +
        ", ".join(
            profile.get(
                "interest_categories",
                []
            )
        )
    )

    print(
        "Accepted types: " +
        ", ".join(
            profile.get(
                "accepted_types",
                []
            )
        )
    )

    print()


def show_all(conn, profile):
    rows = all_posts(conn)

    results = []

    for job in rows:

        result = calculate_score(
            job,
            profile
        )

        if result["score"] > 0:

            results.append(
                (
                    result["score"],
                    job,
                    result
                )
            )

    results.sort(
        key=lambda item: -item[0]
    )

    print()

    print(
        str(len(rows)) +
        " total opportunities"
    )

    print(
        str(len(results)) +
        " have a positive match score"
    )

    print()

    for number, item in enumerate(
        results,
        1
    ):

        score, job, result = item

        print(
            str(number) +
            ". " +
            str(score) +
            "/100  " +
            job["title"]
        )

        print(
            "   " +
            format_category(
                job["category"]
            ) +
            " | " +
            format_deadline(
                job["deadline"]
            )
        )

        skills = result["skills"]

        matched = (
            skills["matched_required"] |
            skills["matched_preferred"] |
            skills["matched_technical"]
        )

        missing = (
            skills["missing_required"] |
            skills["missing_preferred"]
        )

        if matched:

            print(
                "   matched: " +
                print_set(matched)
            )

        if missing:

            print(
                "   missing: " +
                print_set(missing)
            )

        print(
            "   " +
            job["source_url"]
        )

        print()


def main():
    parser = argparse.ArgumentParser(
        description=
        "Match opportunities against your FOMOOO profile."
    )

    parser.add_argument(
        "--market",
        action="store_true",
        help=
        "Show skill demand across open opportunities"
    )

    parser.add_argument(
        "--why",
        type=str,
        help=
        "Explain why an opportunity matches"
    )

    parser.add_argument(
        "--profile",
        action="store_true",
        help=
        "Show your current profile"
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help=
        "Include closed opportunities"
    )

    args = parser.parse_args()

    profile = load_profile()
    conn = connect()

    try:

        if args.profile:

            show_profile(
                profile
            )

            return

        if args.market:

            show_market(
                conn,
                profile
            )

            return

        if args.why:

            show_why(
                conn,
                profile,
                args.why
            )

            return

        if args.all:

            show_all(
                conn,
                profile
            )

            return

        show_ranking(
            conn,
            profile
        )

    finally:

        conn.close()


if __name__ == "__main__":
    main()