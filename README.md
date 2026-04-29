# Syllabus Helper

An intelligent course management platform that helps students make sense of their syllabi. Upload a syllabus PDF, and the system automatically extracts key information (deadlines, grading, policies), lets you ask questions in plain English, estimate your grade, and export deadlines to your calendar.

**Live at:** https://syllabushelper.net

## Features

- **Syllabus Upload & Parsing** — Upload PDF, DOCX, or TXT files. The system extracts course info, deadlines, grading breakdowns, and policies automatically.
- **Ask-the-Syllabus Q&A** — Type questions like "What is the late work policy?" or "How much is the final worth?" and get answers grounded in your syllabus.
- **Grade Calculator** — Enter your scores for each grading component and see your estimated course grade in real time.
- **Calendar Export** — Export all deadlines to an .ics file compatible with Google Calendar, Apple Calendar, and Outlook.
- **Calendar Import** — Import your university .ics schedule to see all your classes alongside syllabus deadlines.
- **Multi-Syllabus Dashboard** — Manage multiple courses in one place.
- **Chrome Extension** — Access your courses directly from Canvas or Brightspace.
- **User Authentication** — Email/password registration or Google OAuth sign-in.

## NLP Concepts Used (TAC 459)

This project applies several NLP techniques covered in TAC 459:

| Concept | Where It's Used | Course Reference |
|---------|----------------|-----------------|
| Text Preprocessing | `pdf_parser.py` — unicode normalization, whitespace cleanup | Class 1-2 |
| Regex-based Information Extraction | `extractor.py` — extract dates, names, emails, grading, policies | Class 5-6 |
| Text Classification | `extractor.py` — classify deadline lines by event type (exam, quiz, project) | Class 5-6 |
| TF-IDF Vectorization | `qa_engine.py` — vectorize syllabus chunks with unigrams + bigrams | Class 3-4 |
| Cosine Similarity | `qa_engine.py` — rank chunks by similarity to user's question | Class 3-4 |
| Stop Words Removal | `qa_engine.py` — TfidfVectorizer with `stop_words="english"` | Class 1-2 |
| T5 Text-to-Text Model | `llm_extractor.py` — Flan-T5-base for course info extraction | Class 11 |
| Prompt Engineering | `llm_extractor.py` — zero-shot prompts with clear constraints | Class 11 |
| OpenAI API Integration | `qa_engine.py`, `llm_extractor.py` — chat completions with roles | Class 11 |
| RAG Pipeline | `qa_engine.py` — retrieval (TF-IDF) + generation (GPT) for Q&A | Class 11 |

## Tech Stack

**Backend:**
- Python 3.12, FastAPI, Uvicorn
- scikit-learn (TF-IDF + cosine similarity)
- HuggingFace Transformers (Flan-T5-base)
- PyMuPDF (PDF extraction), python-docx (DOCX extraction)
- SQLite, bcrypt, PyJWT, cryptography (Fernet encryption)

**Frontend:**
- React 19 + Vite
- FullCalendar, Framer Motion, React Router
- Google OAuth (via @react-oauth/google)

**Deployment:**
- Docker Compose (backend + frontend containers)
- Nginx reverse proxy for frontend
- Deployed on remote server at syllabushelper.net

## Project Structure

```
syllabus-helper/
├── backend/
│   ├── main.py              # FastAPI app, API endpoints, NLP pipeline orchestration
│   ├── pdf_parser.py         # Text extraction & preprocessing (PDF/DOCX/TXT)
│   ├── extractor.py          # Regex-based information extraction (NER, dates, grading)
│   ├── llm_extractor.py      # LLM extraction (Flan-T5 + optional OpenAI)
│   ├── qa_engine.py          # Q&A engine (TF-IDF retrieval + optional RAG)
│   ├── calendar_service.py   # ICS export/import
│   ├── auth.py               # Authentication (email/password + Google OAuth)
│   ├── database.py           # SQLite schema
│   ├── storage.py            # Encrypted persistence layer
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/            # Upload, Dashboard, Ask, Calendar, Grades, Login
│   │   ├── components/       # Layout, shared components
│   │   └── contexts/         # Auth + data store contexts
│   ├── package.json
│   └── Dockerfile
├── extension/                # Chrome extension (Manifest V3)
├── docker-compose.yml
└── README.md
```

## Running Locally

### Backend
```bash
cd backend
pip install -r requirements.txt
python main.py
# runs on http://localhost:8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
# runs on http://localhost:5173
```

### Docker (Production)
```bash
docker-compose up --build
# frontend on port 80, backend on port 8000
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `JWT_SECRET` | Secret key for JWT tokens and Fernet encryption |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID |
| `CORS_ORIGINS` | Comma-separated allowed origins |
| `DB_PATH` | SQLite database path (default: `./data/syllabus_helper.db`) |
| `OPENAI_API_KEY` | (Optional) Enables GPT-powered Q&A and extraction |

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/upload` | Upload and parse a syllabus file |
| GET | `/syllabi` | List all user's syllabi |
| GET | `/syllabus/{id}` | Get a specific syllabus |
| DELETE | `/syllabus/{id}` | Delete a syllabus |
| POST | `/ask/{id}` | Ask a question about a syllabus |
| POST | `/grade-estimate/{id}` | Calculate estimated grade |
| GET | `/calendar/export/{id}` | Export deadlines as .ics |
| GET | `/calendar/export-all` | Export all deadlines as .ics |
| POST | `/calendar/import` | Import .ics schedule |
| POST | `/auth/register` | Register with email/password |
| POST | `/auth/login` | Login with email/password |
| POST | `/auth/google` | Login with Google OAuth |
| GET | `/health` | Server status |

## Team

TAC 459 – Generative AI and NLP, Spring 2026
