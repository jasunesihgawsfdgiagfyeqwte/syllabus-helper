# main.py - Syllabus Helper backend API
#
# NLP pipeline overview:
#   1. User uploads a syllabus PDF/DOCX/TXT
#   2. Text preprocessing: extract raw text, normalize unicode (pdf_parser.py)
#   3. Information extraction: regex-based NER for course info, deadlines,
#      grading, policies (extractor.py)
#   4. LLM enhancement: Flan-T5 or GPT refines extraction (llm_extractor.py)
#   5. Q&A: TF-IDF + cosine similarity retrieval engine (qa_engine.py)
#
# This combines multiple NLP techniques from the TAC 459 course:
# - Text preprocessing & tokenization (Class 1-2)
# - TF-IDF vectorization & cosine similarity (Class 3-4)
# - Information extraction & text classification (Class 5-6)
# - LLM APIs & prompt engineering (Class 11)

from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

from fastapi import FastAPI, UploadFile, File, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
import tempfile
import os
import threading
from typing import Optional

from pdf_parser import extract_text
from extractor import extract_deadlines, extract_grading, extract_grade_scale, extract_policies, extract_course_info
from llm_extractor import extract_with_llm
from qa_engine import QAEngine
from calendar_service import generate_ics, parse_ics
from storage import save_syllabus, load_user_syllabi, delete_syllabus, save_schedule, load_schedule
from auth import register_user, login_user, google_login, verify_token
from database import init_db

app = FastAPI(title="Syllabus Helper API", version="2.0.0")

ALLOWED_ORIGINS = os.environ.get("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# in-memory caches keyed by user email
user_syllabi: dict[str, dict[str, dict]] = {}
user_qa: dict[str, dict[str, QAEngine]] = {}
user_schedules: dict[str, dict] = {}


@app.on_event("startup")
def startup():
    init_db()
    print("Database initialized.")


# auth dependency - extracts user email from JWT token

def get_current_user(authorization: Optional[str] = Header(None)) -> str:
    if not authorization:
        raise HTTPException(401, "Not authenticated")
    token = authorization.replace("Bearer ", "")
    payload = verify_token(token)
    if not payload:
        raise HTTPException(401, "Invalid or expired token")
    return payload["email"]


def get_optional_user(authorization: Optional[str] = Header(None)) -> Optional[str]:
    if not authorization:
        return None
    token = authorization.replace("Bearer ", "")
    payload = verify_token(token)
    return payload["email"] if payload else None


def _ensure_loaded(email: str):
    # lazy-load user data from DB into memory
    if email not in user_syllabi:
        saved = load_user_syllabi(email)
        user_syllabi[email] = saved
        user_qa[email] = {}
        for sid, data in saved.items():
            if data.get("raw_text"):
                user_qa[email][sid] = QAEngine(data["raw_text"], data)
        sched = load_schedule(email)
        if sched:
            user_schedules[email] = sched


# request models

class AskRequest(BaseModel):
    question: str

class GradeEstimateRequest(BaseModel):
    scores: dict[str, float]

class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str = ""

class LoginRequest(BaseModel):
    email: str
    password: str

class GoogleLoginRequest(BaseModel):
    credential: str


# auth endpoints

@app.post("/auth/register")
def auth_register(req: RegisterRequest):
    try:
        return register_user(req.email, req.password, req.name)
    except ValueError as e:
        raise HTTPException(400, str(e))

@app.post("/auth/login")
def auth_login(req: LoginRequest):
    try:
        return login_user(req.email, req.password)
    except ValueError as e:
        raise HTTPException(401, str(e))

@app.post("/auth/google")
def auth_google(req: GoogleLoginRequest):
    try:
        return google_login(req.credential)
    except ValueError as e:
        raise HTTPException(401, str(e))

@app.get("/auth/me")
def auth_me(email: str = Depends(get_current_user)):
    return {"email": email, "name": email.split("@")[0]}

@app.get("/auth/google-client-id")
def get_google_client_id():
    client_id = os.environ.get("GOOGLE_CLIENT_ID", "")
    if not client_id:
        raise HTTPException(404, "Google Client ID not configured")
    return {"client_id": client_id}


# health check

@app.get("/health")
def health(email: str = Depends(get_optional_user)):
    has_local = False
    try:
        import transformers
        has_local = True
    except ImportError:
        pass
    count = 0
    if email:
        _ensure_loaded(email)
        count = len(user_syllabi.get(email, {}))
    return {
        "status": "ok",
        "llm_enabled": has_local,
        "llm_mode": "flan-t5" if has_local else "regex",
        "syllabi_count": count,
    }


# upload endpoint - this is where the NLP pipeline starts

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".text"}

@app.post("/upload")
async def upload_syllabus(file: UploadFile = File(...), email: str = Depends(get_current_user)):
    _ensure_loaded(email)

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}")

    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        # step 1: text extraction & preprocessing
        raw_text = extract_text(tmp_path)
    finally:
        os.unlink(tmp_path)

    if not raw_text.strip():
        raise HTTPException(400, "Could not extract text from file")

    # step 2: information extraction using regex-based NER (extractor.py)
    course_info = extract_course_info(raw_text)
    grading = extract_grading(raw_text)
    grade_scale = extract_grade_scale(raw_text)
    deadlines = extract_deadlines(raw_text)
    policies = extract_policies(raw_text)

    syllabus_id = file.filename.replace(" ", "_")
    for e in [".pdf", ".docx", ".txt", ".text"]:
        syllabus_id = syllabus_id.replace(e, "")

    data = {
        "course_info": course_info,
        "deadlines": deadlines,
        "grading": grading,
        "grade_scale": grade_scale,
        "policies": policies,
        "raw_text": raw_text,
    }

    user_syllabi[email][syllabus_id] = data
    # initialize Q&A engine with TF-IDF index for this syllabus
    user_qa.setdefault(email, {})[syllabus_id] = QAEngine(raw_text, data)
    save_syllabus(email, syllabus_id, data)

    # step 3: LLM refinement runs in background thread so upload returns fast
    def _refine(em, sid, text):
        llm_data = extract_with_llm(text)
        if not llm_data or sid not in user_syllabi.get(em, {}):
            return
        d = user_syllabi[em][sid]
        ci = d["course_info"]
        for key in ("course_code", "course_name", "location", "ta_name"):
            if llm_data.get(key):
                ci[key] = llm_data[key]
        if llm_data.get("grading") is not None:
            d["grading"] = llm_data["grading"]
        if llm_data.get("grade_scale") is not None:
            d["grade_scale"] = llm_data["grade_scale"]
        for key in ("instructor", "email", "semester", "units", "meeting_time", "office_hours", "ta_email"):
            if llm_data.get(key) and not ci.get(key):
                ci[key] = llm_data[key]
        save_syllabus(em, sid, d)
        user_qa.setdefault(em, {})[sid] = QAEngine(text, d)

    threading.Thread(target=_refine, args=(email, syllabus_id, raw_text), daemon=True).start()

    return {
        "syllabus_id": syllabus_id,
        "course_info": course_info,
        "deadlines": deadlines,
        "grading": grading,
        "grade_scale": grade_scale,
        "policies": policies,
    }


# syllabi CRUD endpoints

@app.get("/syllabi")
def list_syllabi(email: str = Depends(get_current_user)):
    _ensure_loaded(email)
    result = {}
    for sid, data in user_syllabi.get(email, {}).items():
        result[sid] = {
            "syllabus_id": sid,
            "course_info": data["course_info"],
            "deadlines": data["deadlines"],
            "grading": data["grading"],
            "grade_scale": data.get("grade_scale", []),
            "policies": data["policies"],
        }
    return result

@app.get("/syllabus/{syllabus_id}")
def get_syllabus(syllabus_id: str, email: str = Depends(get_current_user)):
    _ensure_loaded(email)
    data = user_syllabi.get(email, {}).get(syllabus_id)
    if not data:
        raise HTTPException(404, "Syllabus not found")
    return {
        "syllabus_id": syllabus_id,
        "course_info": data["course_info"],
        "deadlines": data["deadlines"],
        "grading": data["grading"],
        "grade_scale": data.get("grade_scale", []),
        "policies": data["policies"],
    }

@app.delete("/syllabus/{syllabus_id}")
def remove_syllabus(syllabus_id: str, email: str = Depends(get_current_user)):
    _ensure_loaded(email)
    if syllabus_id not in user_syllabi.get(email, {}):
        raise HTTPException(404, "Syllabus not found")
    del user_syllabi[email][syllabus_id]
    user_qa.get(email, {}).pop(syllabus_id, None)
    delete_syllabus(email, syllabus_id)
    return {"deleted": syllabus_id}

@app.get("/deadlines/{syllabus_id}")
def get_deadlines(syllabus_id: str, email: str = Depends(get_current_user)):
    _ensure_loaded(email)
    data = user_syllabi.get(email, {}).get(syllabus_id)
    if not data:
        raise HTTPException(404, "Syllabus not found")
    return {"deadlines": data["deadlines"]}

@app.get("/grading/{syllabus_id}")
def get_grading(syllabus_id: str, email: str = Depends(get_current_user)):
    _ensure_loaded(email)
    data = user_syllabi.get(email, {}).get(syllabus_id)
    if not data:
        raise HTTPException(404, "Syllabus not found")
    return {"grading": data["grading"]}

@app.get("/policies/{syllabus_id}")
def get_policies(syllabus_id: str, email: str = Depends(get_current_user)):
    _ensure_loaded(email)
    data = user_syllabi.get(email, {}).get(syllabus_id)
    if not data:
        raise HTTPException(404, "Syllabus not found")
    return {"policies": data["policies"]}


# Q&A endpoint - uses TF-IDF retrieval + optional LLM (RAG pipeline)

@app.post("/ask/{syllabus_id}")
def ask_question(syllabus_id: str, req: AskRequest, email: str = Depends(get_current_user)):
    _ensure_loaded(email)
    engine = user_qa.get(email, {}).get(syllabus_id)
    if not engine:
        raise HTTPException(404, "Syllabus not found. Upload first.")
    answer, confidence, source_chunk = engine.answer(req.question)
    return {"answer": answer, "confidence": round(confidence, 3), "source": source_chunk}


# grade estimation

@app.post("/grade-estimate/{syllabus_id}")
def estimate_grade(syllabus_id: str, req: GradeEstimateRequest, email: str = Depends(get_current_user)):
    _ensure_loaded(email)
    data = user_syllabi.get(email, {}).get(syllabus_id)
    if not data:
        raise HTTPException(404, "Syllabus not found")
    grading = data["grading"]
    total_weight = 0
    weighted_score = 0
    breakdown = []
    for item in grading:
        name = item["component"]
        weight = item["weight"]
        if name in req.scores:
            score = req.scores[name]
            weighted_score += score * (weight / 100)
            total_weight += weight
            breakdown.append({"component": name, "weight": weight, "score": score, "contribution": round(score * weight / 100, 2)})
    return {"estimated_grade": round(weighted_score, 2), "total_weight_covered": total_weight, "breakdown": breakdown}


# calendar export/import

@app.get("/calendar/export/{syllabus_id}")
def export_calendar(syllabus_id: str, email: str = Depends(get_current_user)):
    _ensure_loaded(email)
    data = user_syllabi.get(email, {}).get(syllabus_id)
    if not data:
        raise HTTPException(404, "Syllabus not found")
    ci = data["course_info"]
    ics_bytes = generate_ics(data["deadlines"], ci.get("course_code", "Course"), ci.get("course_name", ""))
    filename = f"{ci.get('course_code', 'syllabus').replace(' ', '_')}_deadlines.ics"
    return Response(content=ics_bytes, media_type="text/calendar",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})

@app.get("/calendar/export-all")
def export_all_calendars(email: str = Depends(get_current_user)):
    _ensure_loaded(email)
    store = user_syllabi.get(email, {})
    if not store:
        raise HTTPException(404, "No syllabi uploaded yet")
    all_deadlines = []
    for sid, data in store.items():
        code = data["course_info"].get("course_code", sid)
        for dl in data["deadlines"]:
            merged = dict(dl)
            merged["description"] = f"{code}: {dl['description']}"
            all_deadlines.append(merged)
    ics_bytes = generate_ics(all_deadlines, "All Courses", "Merged Semester Deadlines")
    return Response(content=ics_bytes, media_type="text/calendar",
                    headers={"Content-Disposition": 'attachment; filename="all_courses_deadlines.ics"'})

@app.post("/calendar/import")
async def import_calendar(file: UploadFile = File(...), email: str = Depends(get_current_user)):
    if not file.filename.lower().endswith(".ics"):
        raise HTTPException(400, "Only .ics files are supported")
    ics_bytes = await file.read()
    try:
        result = parse_ics(ics_bytes)
    except Exception as e:
        raise HTTPException(400, f"Failed to parse .ics file: {str(e)}")
    user_schedules[email] = result
    save_schedule(email, result)
    return result

@app.get("/calendar/schedule")
def get_schedule(email: str = Depends(get_current_user)):
    _ensure_loaded(email)
    sched = user_schedules.get(email)
    if not sched:
        raise HTTPException(404, "No schedule imported yet")
    return sched


# courses list (for browser extension)

@app.get("/courses")
def list_courses(email: str = Depends(get_current_user)):
    _ensure_loaded(email)
    courses = []
    for sid, data in user_syllabi.get(email, {}).items():
        ci = data["course_info"]
        courses.append({
            "slug": sid,
            "course_code": ci.get("course_code", sid),
            "deadlines_count": len(data.get("deadlines", [])),
            "grading": data.get("grading", []),
        })
    return courses


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
