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


SKILL_RELATIONSHIPS = {
    "mysql": {
        "sql": 0.90
    },

    "postgresql": {
        "sql": 0.90
    },

    "sql server": {
        "sql": 0.90
    },

    "react.js": {
        "javascript": 0.80
    },

    "node.js": {
        "javascript": 0.80
    },

    "express.js": {
        "javascript": 0.80
    },

    "react native": {
        "javascript": 0.80
    },

    "spss": {
        "data analysis": 0.70
    },

    "statistics": {
        "data analysis": 0.55
    },

    "pandas": {
        "data analysis": 0.90
    },

    "numpy": {
        "data analysis": 0.60
    },

    "power bi": {
        "data analysis": 0.90
    },

    "tableau": {
        "data analysis": 0.90
    },

    "python": {
        "data analysis": 0.40,
        "data science": 0.35,
        "machine learning": 0.30
    }
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


EDUCATION_TERMS = [
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


EDUCATION_ALIASES = {
    "computer sciences": "computer science",
    "cyber security": "cybersecurity"
}


EDUCATION_CONTEXT = [
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


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def load_profile():
    with open(
        PROFILE_PATH,
        "r",
        encoding="utf-8"
    ) as file:
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


def normalize_education(term):
    term = normalize_text(term).strip()

    return EDUCATION_ALIASES.get(
        term,
        term
    )


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

    result = set()

    for term in EDUCATION_TERMS:

        if term in combined:

            result.add(
                normalize_education(term)
            )

    return result


def find_education_phrases(sentence):
    text = normalize_text(sentence)

    found = []

    for term in EDUCATION_TERMS:

        if re.search(
            r"\b" +
            re.escape(term) +
            r"\b",
            text
        ):

            found.append(
                normalize_education(term)
            )

    return list(
        dict.fromkeys(found)
    )


def parse_education_requirement(sentence):
    text = normalize_text(sentence)

    terms = find_education_phrases(
        sentence
    )

    if not terms:
        return []

    if re.search(
        r"\b(?:or|either)\b",
        text
    ):

        return [
            {
                "type": "or",
                "options": terms,
                "source": sentence
            }
        ]

    if re.search(
        r"\b(?:and|with)\b",
        text
    ):

        return [
            {
                "type": "and",
                "options": terms,
                "source": sentence
            }
        ]

    return [
        {
            "type": "single",
            "options": terms,
            "source": sentence
        }
    ]


def extract_education_requirements(description):
    requirements = []

    for sentence in split_sentences(description):

        sentence_lower = normalize_text(
            sentence
        )

        has_context = False

        for context in EDUCATION_CONTEXT:

            if context in sentence_lower:
                has_context = True
                break

        if not has_context:
            continue

        parsed = parse_education_requirement(
            sentence
        )

        for requirement in parsed:

            requirements.append(
                requirement
            )

    return requirements


def education_requirement_match(
    requirements,
    user_education
):
    if not requirements:

        return {
            "requirements": [],
            "matched": set(),
            "missing": [],
            "satisfied": 0,
            "total": 0,
            "score": 0,
            "has_requirement": False
        }

    matched = set()
    missing = []

    satisfied = 0

    for requirement in requirements:

        options = set(
            requirement["options"]
        )

        found = options.intersection(
            user_education
        )

        if requirement["type"] == "or":

            if found:

                satisfied += 1
                matched.update(found)

            else:

                missing.append(
                    requirement
                )

        elif requirement["type"] == "and":

            if options.issubset(
                user_education
            ):

                satisfied += 1
                matched.update(options)

            else:

                missing.append(
                    requirement
                )

                matched.update(found)

        else:

            if found:

                satisfied += 1
                matched.update(found)

            else:

                missing.append(
                    requirement
                )

    total = len(requirements)

    score = 0

    if total > 0:

        score = (
            satisfied /
            total
        )

    return {
        "requirements": requirements,
        "matched": matched,
        "missing": missing,
        "satisfied": satisfied,
        "total": total,
        "score": score,
        "has_requirement": True
    }


def education_match(description, profile):
    requirements = extract_education_requirements(
        description
    )

    user = profile_education(
        profile
    )

    result = education_requirement_match(
        requirements,
        user
    )

    return result


def find_required_experience(text):
    text = normalize_text(text)

    patterns = [
        r"\b(\d+)\s*\+?\s*years?\s+of\s+experience\b",
        r"\bminimum\s+(?:of\s+)?(\d+)\s+years?\s+(?:of\s+)?experience\b",
        r"\bat\s+least\s+(\d+)\s+years?\s+(?:of\s+)?experience\b",
        r"\b(\d+)\s*-\s*(\d+)\s+years?\s+(?:of\s+)?experience\b",
        r"\b(\d+)\s+yrs?\s+(?:of\s+)?experience\b"
    ]

    values = []

    for pattern in patterns:

        matches = re.findall(
            pattern,
            text
        )

        for match in matches:

            if isinstance(
                match,
                tuple
            ):

                for value in match:

                    try:

                        values.append(
                            int(value)
                        )

                    except:

                        pass

            else:

                try:

                    values.append(
                        int(match)
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
            "factor": 0.0,
            "score": 0,
            "status": "not stated"
        }

    if required <= 0:
        return {
            "required": required,
            "user": user_years,
            "gap": 0,
            "factor": 1.0,
            "score": 15,
            "status": "no experience required"
        }

    gap = required - user_years

    if gap <= 0:
        factor = 1.0
        status = "meets requirement"

    elif gap == 1:
        factor = 0.80
        status = "minor experience gap"

    elif gap == 2:
        factor = 0.65
        status = "experience gap"

    elif gap == 3:
        factor = 0.55
        status = "experience gap"

    else:
        factor = 0.35
        status = "significant experience gap"

    return {
        "required": required,
        "user": user_years,
        "gap": gap,
        "factor": factor,
        "score": 15 * factor,
        "status": status
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
        deadline_date -
        today
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

        return (
            "CLOSED (" +
            deadline +
            ")"
        )

    if status == "today":

        return "TODAY"

    if status == "1 day":

        return (
            "tomorrow (" +
            deadline +
            ")"
        )

    return (
        deadline +
        " (" +
        status +
        ")"
    )


def find_best_related_match(
    profile_skills,
    target_skill
):
    best_profile_skill = None
    best_weight = 0

    for profile_skill in profile_skills:

        relationships = SKILL_RELATIONSHIPS.get(
            profile_skill,
            {}
        )

        weight = relationships.get(
            target_skill
        )

        if weight is None:
            continue

        if weight > best_weight:

            best_weight = weight
            best_profile_skill = profile_skill

    if best_profile_skill is None:

        return None

    return {
        "profile_skill": best_profile_skill,
        "target_skill": target_skill,
        "weight": best_weight
    }


def calculate_related_skill_matches(
    job_skills,
    profile_skills
):
    result = {
        "required": {},
        "preferred": {},
        "technical": {}
    }

    for section in [
        "required",
        "preferred",
        "technical"
    ]:

        for target_skill in job_skills[section]:

            if target_skill in profile_skills:
                continue

            related = find_best_related_match(
                profile_skills,
                target_skill
            )

            if related:

                result[section][
                    target_skill
                ] = related

    return result


def calculate_weighted_skill_ratio(
    skills,
    exact_matches,
    related_matches
):
    if not skills:
        return 0

    total = 0

    for skill in skills:

        if skill in exact_matches:

            total += 1

        elif skill in related_matches:

            total += related_matches[
                skill
            ]["weight"]

    return total / len(skills)


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

    related_matches = calculate_related_skill_matches(
        job_skills,
        profile_skills
    )

    related_required = related_matches[
        "required"
    ]

    related_preferred = related_matches[
        "preferred"
    ]

    related_technical = related_matches[
        "technical"
    ]

    missing_required = (
        required -
        matched_required -
        set(related_required.keys())
    )

    missing_preferred = (
        preferred -
        matched_preferred -
        set(related_preferred.keys())
    )

    missing_technical = (
        technical -
        matched_technical -
        set(related_technical.keys())
    )

    required_exact_ratio = 0
    required_related_ratio = 0

    preferred_exact_ratio = 0
    preferred_related_ratio = 0

    technical_exact_ratio = 0
    technical_related_ratio = 0

    if required:

        required_exact_ratio = (
            len(matched_required) /
            len(required)
        )

        required_related_ratio = (
            sum(
                item["weight"]
                for item in related_required.values()
            ) /
            len(required)
        )

    if preferred:

        preferred_exact_ratio = (
            len(matched_preferred) /
            len(preferred)
        )

        preferred_related_ratio = (
            sum(
                item["weight"]
                for item in related_preferred.values()
            ) /
            len(preferred)
        )

    if technical:

        technical_exact_ratio = (
            len(matched_technical) /
            len(technical)
        )

        technical_related_ratio = (
            sum(
                item["weight"]
                for item in related_technical.values()
            ) /
            len(technical)
        )

    required_score = (
        required_exact_ratio +
        required_related_ratio
    )

    preferred_score = (
        preferred_exact_ratio +
        preferred_related_ratio
    )

    technical_score = (
        technical_exact_ratio +
        technical_related_ratio
    )

    required_score = min(
        1,
        required_score
    )

    preferred_score = min(
        1,
        preferred_score
    )

    technical_score = min(
        1,
        technical_score
    )

    if required:

        score = (
            required_score * 0.75 +
            preferred_score * 0.10 +
            technical_score * 0.15
        )

    elif preferred:

        score = (
            preferred_score * 0.65 +
            technical_score * 0.35
        )

    elif technical:

        score = technical_score

    else:

        score = 0

    required_gap_ratio = 0

    if required:

        required_coverage = (
            required_exact_ratio +
            required_related_ratio
        )

        required_coverage = min(
            1,
            required_coverage
        )

        required_gap_ratio = (
            1 -
            required_coverage
        )

    required_penalty = (
        required_gap_ratio *
        0.25
    )

    return {
        "score": score,

        "required": required,
        "preferred": preferred,
        "technical": technical,

        "incidental": job_skills["incidental"],

        "matched_required": matched_required,
        "matched_preferred": matched_preferred,
        "matched_technical": matched_technical,

        "related_required": related_required,
        "related_preferred": related_preferred,
        "related_technical": related_technical,

        "missing_required": missing_required,
        "missing_preferred": missing_preferred,
        "missing_technical": missing_technical,

        "required_ratio": required_score,
        "preferred_ratio": preferred_score,
        "technical_ratio": technical_score,

        "required_exact_ratio": required_exact_ratio,
        "required_related_ratio": required_related_ratio,

        "preferred_exact_ratio": preferred_exact_ratio,
        "preferred_related_ratio": preferred_related_ratio,

        "technical_exact_ratio": technical_exact_ratio,
        "technical_related_ratio": technical_related_ratio,

        "required_gap_ratio": required_gap_ratio,

        "required_penalty": required_penalty
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

    education = education_match(
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

    skill_component = (
        skills["score"] *
        40
    )

    education_component = (
        education["score"] *
        30
    )

    experience_component = (
        experience["score"]
    )

    category_component = 0

    if category_ok:

        category_component = 10

    type_component = 0

    if type_ok:

        type_component = 5

    has_skill_evidence = (
        bool(
            skills["matched_required"]
        ) or
        bool(
            skills["matched_preferred"]
        ) or
        bool(
            skills["matched_technical"]
        ) or
        bool(
            skills["related_required"]
        ) or
        bool(
            skills["related_preferred"]
        ) or
        bool(
            skills["related_technical"]
        )
    )

    has_education_evidence = bool(
        education["matched"]
    )

    has_direct_evidence = (
        has_skill_evidence or
        has_education_evidence
    )

    raw_score = (
        skill_component +
        education_component +
        experience_component +
        category_component +
        type_component
    )

    required_penalty = 0

    if skills["required"]:

        required_penalty = (
            skills["required_gap_ratio"] *
            20
        )

    raw_score -= required_penalty

    evidence_cap = None
    evidence_cap_reason = None

    if not has_direct_evidence:

        evidence_cap = (
            experience_component
        )

        evidence_cap_reason = (
            "No matched skills or education; "
            "category and opportunity type are supporting signals only."
        )

        base_score = min(
            raw_score,
            evidence_cap
        )

    elif not has_skill_evidence:

        evidence_cap = (
            education_component +
            experience_component
        )

        evidence_cap_reason = (
            "No matched skills; category and opportunity type "
            "cannot push an education/experience-only match higher."
        )

        base_score = min(
            raw_score,
            evidence_cap
        )

    else:

        base_score = raw_score

    experience_penalty = 0

    if experience["required"] is not None:

        experience_penalty = (
            15 -
            experience_component
        )

    deadline_penalty = 0

    if deadline == "closed":

        deadline_penalty = (
            base_score *
            0.75
        )

        base_score *= 0.25

    elif deadline == "today":

        deadline_penalty = 0

    score = round(
        min(
            100,
            max(
                0,
                base_score
            )
        )
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

    if skills["related_required"]:

        evidence.append(
            "related required skill"
        )

    if skills["related_preferred"]:

        evidence.append(
            "related preferred skill"
        )

    if skills["related_technical"]:

        evidence.append(
            "related technical context"
        )

    if education["matched"]:

        evidence.append(
            "education"
        )

    if category_ok:

        evidence.append(
            "category"
        )

    return {
        "score": score,
        "skills": skills,
        "all_skills": all_skills,

        "education": education,
        "required_education": set(
            item
            for requirement in education["requirements"]
            for item in requirement["options"]
        ),
        "matched_education": education["matched"],
        "education_score": education["score"],
        "education_component": education_component,

        "skill_component": skill_component,

        "experience_component": experience_component,
        "experience_penalty": experience_penalty,

        "category_component": category_component,
        "type_component": type_component,

        "required_skill_penalty": required_penalty,
        "deadline_penalty": deadline_penalty,

        "raw_score": raw_score,
        "evidence_cap": evidence_cap,
        "evidence_cap_reason": evidence_cap_reason,
        "base_score": base_score,

        "experience": experience,
        "category_ok": category_ok,
        "type_ok": type_ok,
        "deadline": deadline,

        "has_direct_evidence": has_direct_evidence,
        "has_skill_evidence": has_skill_evidence,
        "has_education_evidence": has_education_evidence,

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


def format_education_requirement(requirement):
    options = requirement["options"]

    if requirement["type"] == "or":

        return (
            "(" +
            " OR ".join(
                options
            ) +
            ")"
        )

    if requirement["type"] == "and":

        return (
            "(" +
            " AND ".join(
                options
            ) +
            ")"
        )

    return options[0]


def format_related_matches(related_matches):
    results = []

    for target_skill, data in sorted(
        related_matches.items()
    ):

        profile_skill = data[
            "profile_skill"
        ]

        weight = round(
            data["weight"] * 100
        )

        results.append(
            profile_skill +
            " -> " +
            target_skill +
            " (" +
            str(weight) +
            "% support)"
        )

    return results


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

        exact_matched = (
            skills["matched_required"] |
            skills["matched_preferred"] |
            skills["matched_technical"]
        )

        missing = (
            skills["missing_required"] |
            skills["missing_preferred"]
        )

        if exact_matched:

            print(
                "   skills matched: " +
                print_set(
                    exact_matched
                )
            )

        related_display = []

        related_display.extend(
            format_related_matches(
                skills["related_required"]
            )
        )

        related_display.extend(
            format_related_matches(
                skills["related_preferred"]
            )
        )

        related_display.extend(
            format_related_matches(
                skills["related_technical"]
            )
        )

        if related_display:

            print(
                "   related skills: " +
                "; ".join(
                    related_display
                )
            )

        if missing:

            print(
                "   skills missing: " +
                print_set(
                    missing
                )
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


def show_why(conn, profile, opportunity_id):
    job = conn.execute(
        """
        SELECT *
        FROM opportunities
        WHERE id = ?
        AND duplicate_of IS NULL
        """,
        (opportunity_id,)
    ).fetchone()

    if not job:

        print(
            "No opportunity found for ID: " +
            str(opportunity_id)
        )

        return

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

    print("SCORE BREAKDOWN")
    print("-" * 50)

    print(
        "  Skills: " +
        str(
            round(
                result["skill_component"],
                2
            )
        ) +
        "/40"
    )

    print(
        "  Education: " +
        str(
            round(
                result["education_component"],
                2
            )
        ) +
        "/30"
    )

    print(
        "  Experience: " +
        str(
            round(
                result["experience_component"],
                2
            )
        ) +
        "/15"
    )

    print(
        "  Category: " +
        str(
            result["category_component"]
        ) +
        "/10"
    )

    print(
        "  Opportunity type: " +
        str(
            result["type_component"]
        ) +
        "/5"
    )

    print(
        "  Required skill penalty: -" +
        str(
            round(
                result["required_skill_penalty"],
                2
            )
        )
    )

    print(
        "  Raw score: " +
        str(
            round(
                result["raw_score"],
                2
            )
        )
    )

    if result["evidence_cap"] is not None:

        print(
            "  Evidence cap: " +
            str(
                round(
                    result["evidence_cap"],
                    2
                )
            )
        )

        print(
            "  Cap reason: " +
            result["evidence_cap_reason"]
        )

    print(
        "  Final score before deadline: " +
        str(
            round(
                result["base_score"],
                2
            )
        )
    )

    print(
        "  Experience factor: " +
        str(
            result["experience"]["factor"]
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

    if skills["related_required"]:

        print(
            "  Required related matches:"
        )

        for item in format_related_matches(
            skills["related_required"]
        ):

            print(
                "    " +
                item
            )

    if skills["related_preferred"]:

        print(
            "  Preferred related matches:"
        )

        for item in format_related_matches(
            skills["related_preferred"]
        ):

            print(
                "    " +
                item
            )

    if skills["related_technical"]:

        print(
            "  Technical related matches:"
        )

        for item in format_related_matches(
            skills["related_technical"]
        ):

            print(
                "    " +
                item
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

    education = result["education"]

    if education["requirements"]:

        print(
            "  Detected requirements:"
        )

        for requirement in education[
            "requirements"
        ]:

            print(
                "    " +
                format_education_requirement(
                    requirement
                )
            )

        print(
            "  Satisfied: " +
            str(
                education["satisfied"]
            ) +
            "/" +
            str(
                education["total"]
            )
        )

        if education["matched"]:

            print(
                "  Your matching fields: " +
                print_set(
                    education["matched"]
                )
            )

        if education["missing"]:

            print(
                "  Missing education requirements:"
            )

            for requirement in education[
                "missing"
            ]:

                print(
                    "    " +
                    format_education_requirement(
                        requirement
                    )
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

        print(
            "  Score: 0/15"
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

        print(
            "  Experience score: " +
            str(
                round(
                    result["experience_component"],
                    2
                )
            ) +
            "/15"
        )

    else:

        print(
            "  Requirement met: " +
            str(
                experience["required"]
            ) +
            " years"
        )

        print(
            "  Experience score: 15/15"
        )

    print()

    print("PROFILE FIT")

    if result["category_ok"]:

        print(
            "  Category: MATCH (+10)"
        )

    else:

        print(
            "  Category: outside selected interests (+0)"
        )

    if result["type_ok"]:

        print(
            "  Opportunity type: accepted (+5)"
        )

    else:

        print(
            "  Opportunity type: not accepted (score = 0)"
        )

    print()

    print("EVIDENCE")

    if result["evidence"]:

        for item in result["evidence"]:

            print(
                "  + " +
                item
            )

    else:

        print(
            "  No direct profile evidence"
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

        exact_matched = (
            skills["matched_required"] |
            skills["matched_preferred"] |
            skills["matched_technical"]
        )

        missing = (
            skills["missing_required"] |
            skills["missing_preferred"]
        )

        if exact_matched:

            print(
                "   matched: " +
                print_set(
                    exact_matched
                )
            )

        related_display = []

        related_display.extend(
            format_related_matches(
                skills["related_required"]
            )
        )

        related_display.extend(
            format_related_matches(
                skills["related_preferred"]
            )
        )

        related_display.extend(
            format_related_matches(
                skills["related_technical"]
            )
        )

        if related_display:

            print(
                "   related: " +
                "; ".join(
                    related_display
                )
            )

        if missing:

            print(
                "   missing: " +
                print_set(
                    missing
                )
            )

        if result["matched_education"]:

            print(
                "   education: " +
                print_set(
                    result["matched_education"]
                )
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
        type=int,
        help=
        "Explain why an opportunity matches using its ID"
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

        if args.why is not None:

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