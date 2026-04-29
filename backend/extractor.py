# extractor.py
# Information Extraction module (Class 5-6 concepts)
#
# This is basically a regex-based NER (Named Entity Recognition) system.
# Instead of using spaCy's pre-trained NER model (which recognizes generic
# entities like PERSON, ORG, GPE), we wrote custom regex patterns that are
# specific to syllabus documents. This works better for our use case because
# syllabi have very predictable structure (e.g. "Instructor: Name",
# "Grading: Component XX%", date formats, etc.)
#
# We extract:
# - Course info (code, name, instructor, email, etc.)
# - Deadlines (dates + event types like exam, quiz, project)
# - Grading breakdown (component -> weight %)
# - Policies (late work, attendance, AI policy, etc.)

import re
from datetime import datetime, timedelta
from typing import Optional


# ---------------------------------------------------------------
# Course Info extraction
# Uses regex patterns to find structured fields in the syllabus
# header. Similar to entity extraction (Class 5-6) but domain-specific.
# ---------------------------------------------------------------

def extract_course_info(text: str) -> dict:
    info: dict[str, Optional[str]] = {
        "course_code": None,
        "course_name": None,
        "instructor": None,
        "email": None,
        "semester": None,
        "units": None,
        "ta_name": None,
        "ta_email": None,
        "meeting_time": None,
        "office_hours": None,
    }

    # USC building codes to skip - these look like course codes (e.g. "KAP 160")
    # but are actually room numbers
    BUILDING_CODES = {"KAP", "SCB", "THH", "VHE", "RRB", "DRB", "SAL", "OHE",
                      "GFS", "WPH", "SGM", "SOS", "MHP", "JFF", "SCA", "LVL"}

    def _is_course_code(code: str) -> bool:
        prefix = code.split()[0] if " " in code else code[:3]
        return prefix.upper() not in BUILDING_CODES

    # try multiple regex strategies to find the course code + name
    # (syllabi have inconsistent formatting so we need several patterns)
    m = re.search(
        r"(?:Course\s+(?:ID\s+(?:and|&)\s+)?(?:Title|Name)|Course)\s*:\s*([A-Z]{2,5}\s?\d{3}[A-Z]?)\s+(.+?)(?:\n|$)",
        text, re.I
    )

    # pattern 2: "CODE – Name" or "CODE: Name"
    if not m:
        m = re.search(
            r"([A-Z]{2,5}\s?\d{3}[A-Z]?)\s*[-–:]\s*(.+?)(?:\n\n|\n(?:Spring|Fall|Summer|Winter|Units?:?\s*\d))",
            text, re.S
        )
        if m and not _is_course_code(m.group(1)):
            m = None

    # pattern 3: "CODE Name" (space only, in first 500 chars)
    if not m:
        m = re.search(r"([A-Z]{2,5}\s?\d{3}[A-Z]?)\s+([A-Z][A-Za-z].+?)(?:\n|$)", text[:500])
        if m and not _is_course_code(m.group(1)):
            m = None

    if m:
        info["course_code"] = m.group(1).strip()
        info["course_name"] = " ".join(m.group(2).split()).strip()

    # instructor name extraction - this is like NER for PERSON entities
    # but we use regex patterns specific to syllabi instead of spaCy
    m = re.search(r"Instructor[s]?:\s*\n?(.+?)(?:\n(?:Contact|Email|Meeting|Office)|\n\n)", text, re.S)
    if m:
        names = [n.strip() for n in re.split(r"\n|,|;", m.group(1)) if n.strip() and "@" not in n]
        info["instructor"] = ", ".join(names) if names else None

    # fallback: "Name, Ph.D." or "Name, Professor of..."
    if not info["instructor"]:
        m = re.search(r"([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+),?\s+(?:Ph\.?\s*D|Professor|Instructor|Dr\.)", text)
        if m:
            info["instructor"] = m.group(1).strip()

    # email extraction with regex
    emails = re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+", text)
    # filter out institutional emails that aren't the instructor's
    filtered = [e for e in emails if not any(x in e.lower() for x in [
        "engrhelp", "equity", "dsp.usc", "osas", "otfp", "titleix",
        "campussupport", "ombuds", "policy.usc", "conduct",
    ])]
    if filtered:
        info["email"] = ", ".join(set(filtered))
    elif emails:
        info["email"] = ", ".join(set(emails))

    # semester (e.g. "Spring 2026")
    m = re.search(r"(Spring|Fall|Summer|Winter)\s+(\d{4})", text, re.I)
    if m:
        info["semester"] = f"{m.group(1)} {m.group(2)}"

    # units / credits
    m = re.search(r"(?:Units?|Credits?)\s*:?\s*(\d)", text, re.I)
    if not m:
        m = re.search(r"(\d)\s*(?:Units?|Credits?)", text, re.I)
    if m:
        info["units"] = m.group(1)

    # meeting time (e.g. "T Th 10:00 am to 11:50 am")
    m = re.search(
        r"((?:M|T|W|Th|F|Sa|Su)[\s/]*(?:M|T|W|Th|F|Sa|Su)?\s+\d{1,2}:\d{2}\s*(?:am|pm|AM|PM)?\s*(?:to|-)\s*\d{1,2}:\d{2}\s*(?:am|pm|AM|PM)?)",
        text
    )
    if not m:
        # "TTh 2:00 - 3:50 pm (PT)"
        m = re.search(r"((?:M|T|W|Th|F|TTh|MW|MWF)[\w]*\s+\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}\s*(?:am|pm|AM|PM)?(?:\s*\(PT\))?)", text)
    if m:
        info["meeting_time"] = m.group(1).strip()

    # office hours
    m = re.search(r"Office Hours?:?\s*\n?((?:[^\n]+\n?){1,4}?)(?:\n\s*\n|\nCourse|\nContact|\nLearn)", text, re.I)
    if m:
        oh = m.group(1).strip()
        # Clean up bullet points
        oh = re.sub(r"[•●]\s*", "", oh)
        oh = re.sub(r"\n\s*\n", "\n", oh).strip()
        # Remove trailing section headers that leaked in
        oh = re.sub(r"\n(?:Course|Learning|Contact).*$", "", oh, flags=re.I).strip()
        if oh:
            info["office_hours"] = oh

    # TA / Learning Assistant extraction
    ta_section = re.search(
        r"(?:Teaching\s+Assistant|^TA|Learning\s+Assistant)[s]?\s*[:/]?\s*\n((?:.+\n?){1,6}?)(?:\n\n|\nClass\s|Course\s|Disc)",
        text, re.I | re.M
    )
    if ta_section:
        ta_block = ta_section.group(1).strip()
        # Extract TA name: look for a proper name (not labels like "Office:", "Email:")
        ta_lines = [l.strip() for l in ta_block.split("\n") if l.strip()]
        for line in ta_lines:
            # Remove labels like "Office:", "Name:" before the actual name
            cleaned = re.sub(r"^(?:Office|Name|Email|Contact)\s*:\s*", "", line, flags=re.I).strip()
            # Check if it looks like a name (2+ words, starts with uppercase, no @)
            if cleaned and re.match(r"[A-Z][a-z]+ [A-Z]", cleaned) and "@" not in cleaned:
                info["ta_name"] = cleaned
                break
            # Also try if the line IS just a name
            if cleaned and re.match(r"^[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+$", cleaned):
                info["ta_name"] = cleaned
                break

        # Extract TA email from the block
        ta_emails = re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+", ta_block)
        if ta_emails:
            info["ta_email"] = ta_emails[0]

    # If no TA email found in section, try "Learning Assistant / Email" pattern
    if not info["ta_email"]:
        m = re.search(r"(?:TA|Teaching\s+Assistant|Learning\s+Assistant)\s*/?\s*Email\s*[:/]\s*([\w.+-]+@[\w-]+\.[\w.]+)", text, re.I)
        if m:
            info["ta_email"] = m.group(1)

    return info


# ---------------------------------------------------------------
# Deadline Extraction
# Uses regex to find dates in text and classify them by event type.
# This is a form of information extraction (Class 5-6) - we identify
# temporal expressions (DATE entities) and their associated events.
# ---------------------------------------------------------------

# date patterns we look for
DATE_PATTERNS = [
    # "April 26", "Apr 26", "April 26, 2026"
    r"((?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2}(?:,?\s*\d{4})?)",
    # "4/26/2026", "04/26" — but NOT phone-number fragments like "24/7"
    r"(?<!\d)(\d{1,2}/\d{1,2}/\d{2,4})(?!\d)",
    # "2026-04-26"
    r"(\d{4}-\d{2}-\d{2})",
]

# noise patterns to filter out (phone numbers, URLs, etc.)
NOISE_PATTERNS = [
    r"\(\d{3}\)\s*\d{3}-\d{4}",   # phone numbers
    r"\d{3}-\d{3}-\d{4}",          # phone numbers
    r"24/7",                        # on-call indicators
    r"http[s]?://",                 # URLs
    r"@.*\.edu",                    # email lines
    r"suicidepreventionlifeline",
    r"counseling",
    r"Department of Public Safety",
    r"Emergency",
]

# keywords that indicate a deadline (used for text classification)
DEADLINE_KEYWORDS = [
    r"due\b", r"deadline", r"submit", r"submission",
    r"exam", r"midterm", r"final", r"quiz",
    r"presentation", r"project",
    r"by\s+(?:the\s+)?(?:end\s+of\s+)?",
]


def extract_deadlines(text: str) -> list[dict]:
    deadlines = []

    # phase 1: find explicit dates in the text using regex patterns
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if any(re.search(p, line, re.I) for p in NOISE_PATTERNS):
            continue
        for pattern in DATE_PATTERNS:
            for m in re.finditer(pattern, line, re.I):
                date_str = m.group(1)
                parsed_date = _try_parse_date(date_str)
                if not parsed_date:
                    continue

                # Classify using CURRENT LINE ONLY to avoid bleeding
                # from neighboring lines (e.g. "Week 7" near "Exam 1")
                event_type = _classify_event(line)

                # FILTER: skip "other" — no deadline keyword on this line
                if event_type == "other":
                    continue

                description = _extract_event_description(line, date_str)
                deadlines.append({
                    "date": parsed_date,
                    "raw_date": date_str,
                    "description": description,
                    "type": event_type,
                    "context": line.strip(),
                })

    # phase 2: extract week-based events from course schedule tables
    semester_start = _detect_semester_start(text)
    schedule_events = _extract_schedule_events(text)

    for week_num, event_desc, event_type in schedule_events:
        event_date = _week_to_date(week_num, semester_start)
        deadlines.append({
            "date": event_date,
            "raw_date": f"Week {week_num}",
            "description": event_desc,
            "type": event_type,
            "context": f"Week {week_num} of course schedule",
        })

    # deduplicate - if same exam shows up in both phases, keep the better one

    def _score(d):
        s = 0
        ctx = d.get("context", "")
        # Prefer standalone exam lines ("Exam 1, Thursday, ...") over
        # week schedule lines ("Week 6. Feb 17, 19. Exam 1 on ...")
        if not re.match(r"^\s*Week\s+\d", ctx, re.I):
            s += 10
        # Prefer entries with location/time info
        if re.search(r"[A-Z]{2,5}[-\s]?\d{2,4}", ctx):
            s += 5
        if re.search(r"\d{1,2}:\d{2}", ctx):
            s += 3
        return s

    # Step 1: exact (date, type) dedup — keep highest quality entry
    best = {}
    for d in deadlines:
        key = (d["date"], d["type"])
        if key not in best or _score(d) > _score(best[key]):
            best[key] = d

    merged = list(best.values())
    merged.sort(key=lambda x: x["date"] or "9999")

    # Step 2: same-type events within 7 days are the same exam/deadline
    # Keep the one with better score; on tie, keep the later date
    final = []
    for d in merged:
        duplicate = False
        for j, existing in enumerate(final):
            if existing["type"] == d["type"] and existing["type"] != "other":
                try:
                    d1 = datetime.strptime(existing["date"], "%Y-%m-%d")
                    d2 = datetime.strptime(d["date"], "%Y-%m-%d")
                    if abs((d2 - d1).days) <= 7:
                        # Keep the one with better score; tie → later date
                        if _score(d) > _score(existing) or (
                            _score(d) == _score(existing) and d2 > d1
                        ):
                            final[j] = d
                        duplicate = True
                        break
                except ValueError:
                    pass
        if not duplicate:
            final.append(d)

    final.sort(key=lambda x: x["date"] or "9999")
    return final


# semester start dates for converting "Week N" to actual dates
SEMESTER_STARTS = {
    "Spring 2025": "2025-01-13",
    "Fall 2025": "2025-08-25",
    "Spring 2026": "2026-01-12",
    "Fall 2026": "2026-08-24",
    "Spring 2027": "2027-01-11",
}


def _detect_semester_start(text: str) -> str:
    m = re.search(r"(Spring|Fall|Summer|Winter)\s+(\d{4})", text, re.I)
    if m:
        semester = f"{m.group(1).capitalize()} {m.group(2)}"
        if semester in SEMESTER_STARTS:
            return SEMESTER_STARTS[semester]
    # Fallback: assume current Spring 2026
    return "2026-01-12"


def _week_to_date(week_num: int, semester_start: str) -> str:
    start = datetime.strptime(semester_start, "%Y-%m-%d")
    target = start + timedelta(weeks=week_num - 1)
    return target.strftime("%Y-%m-%d")


# schedule table parser - patterns for events in the weekly schedule
SCHEDULE_EVENT_PATTERNS = [
    (r"\bExam\s*(?:I|1|One)\b|\bMidterm\s+Exam\b|\bMidterm\b", "midterm"),
    (r"\bExam\s*(?:II|2|Two)\b|\bFinal\s+Exam\b", "final_exam"),
    (r"\bCapstone\s+Project\s+Presentation\b|\bFinal\s+Presentation\b|\bStudent\s+[Pp]resentation", "presentation"),
    (r"\bProject\s+(?:Due|Submission|Deadline)\b", "project"),
    (r"\bQuiz\b", "quiz"),
]


def _extract_schedule_events(text: str) -> list[tuple[int, str, str]]:
    # Parse the weekly schedule table for events (exams, presentations, etc.)
    # First isolate the schedule section to avoid false positives
    schedule_text = text
    # Look for the actual schedule table header (not passing references)
    sched_start = re.search(
        r"Course\s+Schedule\s*:\s*A?\s*Weekly|Weekly\s+Breakdown|Week\s+\n\s*Topic",
        text, re.I
    )
    if sched_start:
        tail = text[sched_start.start():]
        sched_end = re.search(r"\n(?:Statement on Academic|Additional Policies|Support Systems)", tail, re.I)
        schedule_text = tail[:sched_end.start()] if sched_end else tail

    events = []
    lines = schedule_text.split("\n")

    for i, line in enumerate(lines):
        # Match standalone week numbers (from table rows like "8\nExam I")
        week_match = re.match(r"^\s*(\d{1,2})\s*$", line.strip())
        if week_match:
            week_num = int(week_match.group(1))
            if 1 <= week_num <= 20 and i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                # Skip topic descriptions ("Week X: long topic...") — only match
                # short event lines like "Exam I", "Exam II", "Study Days"
                if next_line.lower().startswith("week "):
                    continue
                if len(next_line) > 60:
                    continue
                for pattern, etype in SCHEDULE_EVENT_PATTERNS:
                    if re.search(pattern, next_line, re.I):
                        desc = _build_schedule_description(next_line, etype)
                        events.append((week_num, desc, etype))
                        break

    # Deduplicate: keep one event per (week, type)
    seen = set()
    unique = []
    for w, d, t in events:
        key = (w, t)
        if key not in seen:
            seen.add(key)
            unique.append((w, d, t))

    return unique


def _build_schedule_description(context: str, event_type: str) -> str:
    labels = {
        "midterm": "Midterm Exam",
        "final_exam": "Final Exam",
        "presentation": "Capstone Project Presentation",
        "project": "Project Due",
        "quiz": "Quiz",
    }
    base = labels.get(event_type, event_type.replace("_", " ").title())

    # Try to extract the topic from context
    topic_match = re.search(r"Week\s+\d+\s*:?\s*(.+?)(?:\n|$)", context, re.I)
    if topic_match:
        topic = topic_match.group(1).strip()[:80]
        if topic and topic.lower() != base.lower():
            return f"{base} — {topic}"

    return base


def _try_parse_date(date_str: str) -> Optional[str]:
    formats = [
        "%B %d, %Y", "%B %d %Y", "%B %d",
        "%b %d, %Y", "%b %d %Y", "%b %d",
        "%m/%d/%Y", "%m/%d/%y", "%m/%d",
        "%Y-%m-%d",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            if dt.year < 2000:
                dt = dt.replace(year=2026)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _classify_event(context: str) -> str:
    # Text classification (Class 5-6): classify a line containing a date
    # into event categories. This is rule-based classification using keyword
    # patterns rather than ML-based (like the sentiment analysis from class).
    c = context.lower()

    # Exams (order matters — check final before midterm)
    if re.search(r"\bfinal\s+exam\b|\bfinal\s*,", c):
        return "final_exam"
    if re.search(r"\bmidterm\b|\bexam\s*[12i]\b|\bexam\b", c):
        return "midterm"
    if re.search(r"\bquiz\b|\btest\b", c):
        return "quiz"

    # Assignments
    if re.search(r"\bproject\b.*\b(due|submit|deadline)\b|\bcapstone\b|\bproject\s+(submission|deadline|due)\b", c):
        return "project"
    if re.search(r"\bpresentation\b.*\b(due|date)\b|\bpresent(ation)?\s+(date|day|due)\b", c):
        return "presentation"
    if re.search(r"\bhomework\b|\bassignment\b|\bhw\s*\d|\bpaper\b.*\bdue\b|\blab\b.*\bdue\b", c):
        return "homework"
    if re.search(r"\bdue\b|\bdeadline\b|\bsubmit|\bsubmission\b|\bturn\s*in\b", c):
        return "deadline"

    # Everything else (weekly class sessions, readings, etc.) → not a deadline
    return "other"


def _extract_event_description(line: str, date_str: str) -> str:
    # build a clean description from a deadline line
    event_name = _extract_event_name(line)

    # extract location if present (e.g. "KAP-145")
    loc_match = re.search(r"\b([A-Z]{2,5}[-\s]?\d{2,4})\b", line)
    location = loc_match.group(1) if loc_match else ""

    # extract time if present
    time_match = re.search(r"(\d{1,2}:\d{2}\s*(?:am|pm|AM|PM)?\s*(?:to|-)\s*\d{1,2}:\d{2}\s*(?:am|pm|AM|PM)?)", line)
    time_str = time_match.group(1) if time_match else ""

    parts = [event_name]
    if location:
        parts.append(location)
    if time_str:
        parts.append(time_str)

    return " — ".join(parts) if len(parts) > 1 else parts[0]


def _extract_event_name(line: str) -> str:
    # extract the event name using regex pattern matching
    m = re.search(r"((?:Final\s+)?Exam\s*(?:\d+|[IVX]+)?)", line, re.I)
    if m:
        name = m.group(1).strip()
        # Normalize: "exam 1" → "Exam 1"
        return name[0].upper() + name[1:]

    # "Midterm", "Midterm Exam"
    m = re.search(r"(Midterm(?:\s+Exam)?)", line, re.I)
    if m:
        return m.group(1).strip()

    # "Quiz X"
    m = re.search(r"(Quiz\s*\d*)", line, re.I)
    if m:
        return m.group(1).strip()

    # "Final Exam" / "Final"
    m = re.search(r"(Final\s+Exam|Final)", line, re.I)
    if m:
        return m.group(1).strip()

    # "Homework X due" / "HW X due"
    m = re.search(r"((?:Homework|HW|Assignment|Paper|Lab|Report|Essay)\s*\d*)\s*(?:due)?", line, re.I)
    if m:
        return m.group(1).strip() + " Due"

    # "Project" / "Presentation"
    m = re.search(r"((?:Final\s+)?(?:Project|Presentation|Capstone)(?:\s+\d*)?)", line, re.I)
    if m:
        return m.group(1).strip()

    # Fallback: clean the line
    cleaned = re.sub(r"Week\s+\d+\.?", "", line)
    # Remove dates
    for p in DATE_PATTERNS:
        cleaned = re.sub(p, "", cleaned, flags=re.I)
    # Remove day names
    cleaned = re.sub(r"\b(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b,?", "", cleaned, re.I)
    # Clean up residual punctuation
    cleaned = re.sub(r"\s*[,;.]+\s*", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:80] if cleaned else "Deadline"


# ---------------------------------------------------------------
# Grading Breakdown extraction
# ---------------------------------------------------------------

def extract_grading(text: str) -> list[dict]:
    # Extract grading breakdown - handles both percentage and points-based systems.
    # Uses multiple regex strategies because syllabi format grading info differently.
    grading = []

    # strategy 1: table format "Component    XX" (tab/space separated)
    table_match = re.search(
        r"(?:Assessment|Assignment|%\s*of\s*grade|Grading\s*Breakdown).*?\n((?:.*\n)*?)(?:\n\n|\nAssignment\s+Submission|\nGen\s+AI|\nFinal\s+Project(?:\s+Submission|\s+Grading))",
        text, re.I
    )
    search_text = table_match.group(1) if table_match else text

    # Only match lines WITHOUT colons (to avoid capturing "Component: XX%" as table)
    pattern = r"^[\s]*([A-Z][A-Za-z\s/&]+?)\s{2,}(\d{1,3})\s*(?:\(\+\d+[^)]*\))?\s*%?\s*$"
    for m in re.finditer(pattern, search_text, re.MULTILINE):
        line = m.group(0)
        if ":" in line:
            continue  # Skip colon format — handled by Strategy 2
        component = m.group(1).strip()
        weight = int(m.group(2))
        if 4 <= weight <= 100 and len(component) < 60:
            grading.append({"component": component, "weight": weight})

    # strategy 2: "Component: XX%" inline
    if not grading:
        for line in text.split("\n"):
            m = re.search(r"([A-Za-z][A-Za-z \t/&()\-]+?):\s*(\d{1,3})\s*%", line)
            if m:
                component = m.group(1).strip()
                weight = int(m.group(2))
                if 4 <= weight <= 100 and len(component) < 60:
                    grading.append({"component": component, "weight": weight})

    # strategy 3: points-based "Component: XX points"
    if not grading:
        point_entries = []
        for line in text.split("\n"):
            m = re.match(
                r"^\s*([A-Za-z][A-Za-z\s/&0-9]+?)\s*(?:\([^)]*\))?\s*:\s*(\d{1,4})\s*(?:points?|pts?)\b",
                line.strip(), re.I
            )
            if m:
                component = m.group(1).strip()
                points = int(m.group(2))
                # Skip "Total" lines
                if re.search(r"^total$", component, re.I):
                    continue
                if points > 0 and len(component) < 80:
                    point_entries.append({"component": component, "points": points})

        # Convert points to percentages
        if point_entries:
            total_pts = sum(e["points"] for e in point_entries)
            if total_pts > 0:
                for e in point_entries:
                    weight = round(e["points"] / total_pts * 100)
                    if weight > 0:
                        grading.append({
                            "component": e["component"],
                            "weight": weight,
                            "points": e["points"],
                            "total_points": total_pts,
                        })

    # Filter noise
    noise_words = ["total", "week", "topic", "study day"]
    grading = [g for g in grading if not any(nw in g["component"].lower() for nw in noise_words)]

    # Validate: if weights sum to way over 100, keep only large items
    total = sum(g["weight"] for g in grading)
    if total > 150:
        grading = [g for g in grading if g["weight"] >= 5]

    return grading


def extract_grade_scale(text: str) -> list[dict]:
    # extract letter grade scale (e.g. A: 93-100%, B+: 87-89%)
    scale = []

    # Pattern: "A: 93-100%" or "A  93-100" or "A: 93 - 100%"
    for m in re.finditer(
        r"([A-D][+-]?|F)\s*:?\s*(\d{2,3})\s*[-–]\s*(\d{2,3})\s*%?",
        text
    ):
        letter = m.group(1)
        low = int(m.group(2))
        high = int(m.group(3))
        if 0 <= low <= 100 and 0 <= high <= 100:
            scale.append({"grade": letter, "min": low, "max": high})

    # Also check for "F: 59 and below" type
    m = re.search(r"F\s*:?\s*(\d{1,2})\s*(?:and\s+below|or\s+below|%?\s*and\s+below)", text, re.I)
    if m:
        scale.append({"grade": "F", "min": 0, "max": int(m.group(1))})

    return scale


# ---------------------------------------------------------------
# Policy Extraction
# Extracts policy sections by matching keyword patterns against
# paragraphs. This is another form of text classification - we
# classify each paragraph into a policy type (or skip it).
# ---------------------------------------------------------------

POLICY_SECTIONS = [
    ("late_work", [r"late\s+(work|submission|assignment|penalty)", r"turned?\s+in\s+late", r"deduct", r"late\s+day", r"no.penalty.day"]),
    ("attendance", [r"attendance", r"unapproved\s+absence", r"absent", r"absence", r"tardy", r"tardiness", r"participation\s+grade"]),
    ("academic_integrity", [r"academic\s+(integrity|dishonesty|conduct|misconduct)", r"plagiarism", r"cheating"]),
    ("makeup_exam", [r"make-?up\s+exam", r"no\s+make-?up", r"missed?\s+exam"]),
    ("extra_credit", [r"extra\s+credit", r"bonus\s+point"]),
    ("ai_policy", [r"AI\s*[Pp]ol[il]cy",
                   r"\b(?:ChatGPT|GPT|Copilot)\b",
                   r"(?:use\s+of|using)\s+(?:generative\s+)?AI\s+(?:tools|is)",
                   r"AI\s+tools?\s+(?:are|is)\s+(?:permitted|allowed|prohibited|encouraged)",
                   r"AI.generated\s+(?:content|text|code|work)"]),
    ("accommodations", [r"accommodat", r"disabilit", r"OSAS", r"accessibility"]),
]


def extract_policies(text: str) -> list[dict]:
    policies = []

    # Clean up unicode whitespace that breaks paragraph splitting
    clean_text = text.replace("\xa0", " ").replace("\u200b", "")
    clean_text = re.sub(r"[ \t]+\n", "\n", clean_text)  # trailing spaces

    raw_lines = clean_text.split("\n")
    paragraphs = []
    buf = []
    for line in raw_lines:
        if line.strip() == "":
            if buf:
                paragraphs.append("\n".join(buf))
                buf = []
        else:
            buf.append(line)
    if buf:
        paragraphs.append("\n".join(buf))

    for para in paragraphs:
        stripped = para.strip()
        if len(stripped) < 40:
            continue

        for policy_name, patterns in POLICY_SECTIONS:
            if any(p["type"] == policy_name for p in policies):
                continue
            for pattern in patterns:
                m = re.search(pattern, stripped, re.I)
                if m:
                    # Try to start from the match position if it's deep in the paragraph
                    # (avoids including preceding unrelated text)
                    match_start = m.start()
                    if match_start > 80:
                        # Find the last sentence boundary before the match
                        preceding = stripped[:match_start]
                        last_period = max(preceding.rfind(". "), preceding.rfind(".\n"))
                        if last_period > 0:
                            stripped = stripped[last_period + 2:]

                    summary = stripped.strip()
                    if len(summary) > 500:
                        summary = summary[:500] + "..."
                    policies.append({
                        "type": policy_name,
                        "label": policy_name.replace("_", " ").title(),
                        "text": summary,
                    })
                    break

    return policies
