# llm_extractor.py
# Uses LLMs to extract structured info from syllabus text.
#
# We use Google's Flan-T5-base as our primary model - it's a Text-to-Text
# Transfer Transformer (Class 11) that treats every NLP task as a text-to-text
# problem. We feed it a question + syllabus header and it returns the answer.
#
# Extraction priority:
#   1. Local Flan-T5 (free, runs on CPU, no API key needed)
#   2. OpenAI GPT-4o-mini (if OPENAI_API_KEY env var is set)
#   3. None -> falls back to regex extraction in main.py

import os
import json
import re

_local_pipeline = None


def _get_local_pipeline():
    # Lazy-load the Flan-T5 model using HuggingFace transformers pipeline.
    # We use text2text-generation task because T5 frames everything as
    # "input text -> output text" (the core T5 design from Class 11).
    global _local_pipeline
    if _local_pipeline is None:
        try:
            from transformers import pipeline
            print("Loading Flan-T5-base...")
            _local_pipeline = pipeline(
                "text2text-generation",
                model="google/flan-t5-base",
                max_new_tokens=64,
                device="cpu",
            )
            print("Flan-T5-base loaded.")
        except Exception as e:
            print(f"Failed to load Flan-T5: {e}")
            _local_pipeline = False
    return _local_pipeline if _local_pipeline else None


def extract_with_llm(raw_text: str) -> dict | None:
    # Try LLM extraction. If OpenAI key exists, use GPT (it can handle
    # the full extraction in one shot). Otherwise use Flan-T5 for the
    # fields that regex struggles with (course_code, location, TA name).
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if api_key:
        return _extract_with_openai(raw_text, api_key)

    flan_fields = _extract_key_fields_flan(raw_text)
    if flan_fields:
        return flan_fields

    return None


# ---------------------------------------------------------------
# Flan-T5 extraction
# Uses short, focused prompts (prompt engineering from Class 11)
# with aggressive post-processing to clean up T5 output
# ---------------------------------------------------------------

def _extract_key_fields_flan(raw_text: str) -> dict | None:
    # Flan-T5 only extracts: course_code, course_name, location, ta_name
    # For other fields (instructor, email, grading, etc.) regex is more
    # reliable, so we let main.py handle those with the regex extractor.
    pipe = _get_local_pipeline()
    if not pipe:
        return None

    # only use the first 800 chars - that's where the header info is
    header = raw_text[:800]

    def ask(q: str) -> str:
        # Each prompt is a zero-shot question (Class 11) - we just ask
        # directly without providing examples. T5 handles this because
        # it was fine-tuned on a huge range of NLP tasks.
        try:
            out = pipe(f"{q}\n\n{header}")[0]["generated_text"].strip()
            first = out.split("\n")[0].strip()
            return first if len(first) < 60 else ""
        except Exception:
            return ""

    # Prompt design: keep prompts short and specific (Class 11 principle:
    # "write clear and specific instructions"). Adding "Answer with just..."
    # constrains the output so T5 doesn't dump the whole paragraph back.
    code_raw = ask("What is the course code? Answer with just the code like 'PSYC 361'.")
    name_raw = ask("What is the course title? Answer briefly.")
    location_raw = ask("What room or building is the class in? Answer with just the room code.")
    ta_raw = ask("Who is the teaching assistant? Answer with just the name.")

    # post-process course code - T5 sometimes returns building codes like "KAP"
    code_match = re.search(r"([A-Z]{2,5})\s*(\d{3}[A-Z]?)", code_raw.upper()) if code_raw else None
    if code_match and code_match.group(1) not in _BUILDING_CODES:
        code = f"{code_match.group(1)} {code_match.group(2)}"
    else:
        # Regex fallback: first non-building code in header
        code = None
        for m in re.finditer(r"([A-Z]{2,5})\s+(\d{3}[A-Z]?)", header):
            if m.group(1) not in _BUILDING_CODES:
                code = f"{m.group(1)} {m.group(2)}"
                break
        if not code:
            return None

    # clean up course name
    if name_raw:
        name_raw = re.sub(r"^[A-Z]{2,5}\s*\d{3}[A-Z]?\s*[-:–]?\s*", "", name_raw).strip()
    if not name_raw or len(name_raw) < 3:
        # Try multiline match for long course names
        m = re.search(re.escape(code) + r"\s*[-:–]?\s*(.+?)(?:\n\n|\n(?:Spring|Fall|Units))", header, re.S)
        if m:
            name_raw = " ".join(m.group(1).split()).strip()
        else:
            m = re.search(re.escape(code) + r"\s*[-:–]?\s*(.+?)(?:\n|$)", header)
            name_raw = m.group(1).strip() if m else None

    # validate location looks like a room code (e.g. "KAP 160")
    location = None
    if location_raw and re.match(r"^[A-Z]{2,5}[\s-]?\d{2,4}$", location_raw.strip()):
        location = location_raw.strip()
    if not location:
        # Look for a room code pattern (e.g. "KAP 160", "SCB 104") near "Location"
        loc_section = re.search(r"(?:Location|Room|Building|Meeting).*?([A-Z]{2,5}[\s-]?\d{2,4})", header, re.I | re.S)
        if loc_section:
            location = loc_section.group(1).strip()

    # TA name cleanup
    ta = None
    if ta_raw and len(ta_raw) < 40 and ta_raw.lower() not in ("n/a", "none", "not found", "unknown"):
        ta = ta_raw

    # return only the fields T5 is good at; rest will be filled by regex
    return {
        "course_code": code,
        "course_name": name_raw,
        "location": location,
        "ta_name": ta,
        # None signals main.py to use regex for these fields
        "instructor": None,
        "email": None,
        "semester": None,
        "units": None,
        "meeting_time": None,
        "office_hours": None,
        "ta_email": None,
        "grading": None,
        "grade_scale": None,
    }


# USC building codes - need to exclude these from course code matching
# because T5 sometimes confuses "KAP 160" (a room) with a course code
_BUILDING_CODES = {"KAP", "SCB", "THH", "VHE", "RRB", "DRB", "SAL", "OHE",
                   "GFS", "WPH", "SGM", "SOS", "MHP", "JFF", "SCA", "LVL",
                   "SCIL", "ZHS", "DMC", "CTV", "ACC", "RTH", "TCC"}


def _extract_first_email(text: str) -> str | None:
    emails = re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+", text)
    skip = {"engrhelp", "equity", "dsp.usc", "osas", "otfp", "titleix", "campussupport", "ombuds"}
    for e in emails:
        if not any(s in e.lower() for s in skip):
            return e
    return emails[0] if emails else None


def _extract_ta_email(text: str) -> str | None:
    m = re.search(r"(?:Teaching\s+Assistant|TA|Learning\s+Assistant).*?([\w.+-]+@[\w-]+\.[\w.]+)", text[:2000], re.I | re.S)
    return m.group(1) if m else None


def _extract_grading_regex(text: str) -> list[dict]:
    # regex-based grading extraction (same logic as extractor.py)
    grading = []
    # Strategy 1: "Component: XX%"
    for line in text.split("\n"):
        m = re.search(r"([A-Za-z][A-Za-z \t/&()\-]+?):\s*(\d{1,3})\s*%", line)
        if m:
            comp = m.group(1).strip()
            w = int(m.group(2))
            if 4 <= w <= 100 and len(comp) < 60 and "total" not in comp.lower():
                grading.append({"component": comp, "weight": w})
    if grading:
        return grading

    # Strategy 2: table "Component    XX"
    pattern = r"^[\s]*([A-Z][A-Za-z\s/&]+?)\s{2,}(\d{1,3})\s*(?:\(\+\d+[^)]*\))?\s*%?\s*$"
    for m in re.finditer(pattern, text, re.MULTILINE):
        if ":" in m.group(0):
            continue
        comp = m.group(1).strip()
        w = int(m.group(2))
        if 4 <= w <= 100 and len(comp) < 60:
            noise = ["total", "week", "topic", "study day"]
            if not any(n in comp.lower() for n in noise):
                grading.append({"component": comp, "weight": w})
    if grading:
        total = sum(g["weight"] for g in grading)
        if total > 150:
            grading = [g for g in grading if g["weight"] >= 5]
        return grading

    # Strategy 3: "Component: XX points"
    pts = []
    for line in text.split("\n"):
        m = re.match(r"^\s*([A-Za-z][\w\s/&]+?)\s*(?:\([^)]*\))?\s*:\s*(\d{1,4})\s*(?:points?|pts?)\b", line.strip(), re.I)
        if m:
            comp = m.group(1).strip()
            p = int(m.group(2))
            if p > 0 and len(comp) < 80 and "total" not in comp.lower():
                pts.append({"component": comp, "points": p})
    if pts:
        total_pts = sum(e["points"] for e in pts)
        for e in pts:
            w = round(e["points"] / total_pts * 100)
            if w > 0:
                grading.append({"component": e["component"], "weight": w, "points": e["points"], "total_points": total_pts})

    return grading


def _extract_scale_regex(text: str) -> list[dict]:
    scale = []
    for m in re.finditer(r"([A-D][+-]?|F)\s*:?\s*(\d{2,3})\s*[-–]\s*(\d{2,3})\s*%?", text):
        g, lo, hi = m.group(1), int(m.group(2)), int(m.group(3))
        if 0 <= lo <= 100 and 0 <= hi <= 100:
            scale.append({"grade": g, "min": lo, "max": hi})
    m = re.search(r"F\s*:?\s*(\d{1,2})\s*(?:and\s+below|or\s+below)", text, re.I)
    if m:
        scale.append({"grade": "F", "min": 0, "max": int(m.group(1))})
    return scale


# ---------------------------------------------------------------
# OpenAI fallback - uses GPT-4o-mini via the chat completions API
# (Class 11: API integration with system/user roles)
# ---------------------------------------------------------------

def _extract_with_openai(raw_text: str, api_key: str) -> dict | None:
    text_for_llm = raw_text[:6000]
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        # Using structured output prompting (Class 11): we ask the model
        # to return JSON format, which is one of the prompt engineering
        # tactics - "ask for structured output"
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a syllabus parser. Return ONLY valid JSON."},
                {"role": "user", "content": f"""Extract from this syllabus as JSON:

{{
  "course_code": "e.g. PSYC 361 (NOT a building code)",
  "course_name": "full title",
  "instructor": "name(s)",
  "email": "instructor email(s)",
  "semester": "e.g. Spring 2026",
  "units": "number as string",
  "meeting_time": "days and times",
  "location": "building/room",
  "office_hours": "hours info",
  "ta_name": "TA name or null",
  "ta_email": "TA email or null",
  "grading": [{{"component": "name", "weight": percent_int}}],
  "grade_scale": [{{"grade": "A", "min": 93, "max": 100}}]
}}

Use null for missing fields.

{text_for_llm}"""},
            ],
            max_tokens=1000, temperature=0,  # temperature=0 for deterministic output
        )
        result_text = response.choices[0].message.content.strip()
        if result_text.startswith("```"):
            result_text = result_text.split("\n", 1)[1]
            if result_text.endswith("```"):
                result_text = result_text[:-3]
        return json.loads(result_text.strip())
    except Exception as e:
        print(f"OpenAI extraction failed: {e}")
        return None
