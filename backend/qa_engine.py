# qa_engine.py
# Q&A module that answers user questions about a syllabus.
#
# This is basically a simplified RAG pipeline (Retrieval-Augmented Generation)
# like we learned in Class 11 / Q29:
#   1. First try structured lookup (direct field match - no NLP needed)
#   2. If that fails, use TF-IDF vectorization + cosine similarity to retrieve
#      the most relevant text chunks from the syllabus (Class 3-4 concepts)
#   3. Optionally pass retrieved context to an LLM for a polished answer
#      (prompt engineering w/ system/user roles, Class 11)

import os
import re
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class QAEngine:
    def __init__(self, text: str, structured_data: dict = None):
        self.raw_text = text
        self.data = structured_data or {}
        self.chunks = self._chunk_text(text)

        # TF-IDF vectorizer from sklearn (covered in Class 3-4)
        # - stop_words="english" removes common words like "the", "is", "at"
        #   so they don't dominate the similarity scores
        # - ngram_range=(1,2) means we use both unigrams and bigrams,
        #   e.g. "final exam" as a single feature, not just "final" + "exam"
        # - max_features caps the vocabulary to avoid memory issues on long syllabi
        self.vectorizer = TfidfVectorizer(
            stop_words="english", ngram_range=(1, 2), max_features=5000,
        )
        # fit_transform builds the vocab from chunks and converts to TF-IDF matrix
        self.tfidf_matrix = self.vectorizer.fit_transform(self.chunks)

    def _chunk_text(self, text: str) -> list[str]:
        # Split syllabus into meaningful chunks for TF-IDF indexing.
        # Similar to how we split documents before vectorizing in the
        # TF-IDF retrieval demo (Class 3-4) - each chunk becomes a "document"
        # in our mini corpus so cosine_similarity can rank them against a query.
        cleaned_lines = []
        for line in text.split("\n"):
            s = line.strip()
            if re.match(r"^[●•\-○◦]\s*", s):
                continue
            if re.match(r"^Week\s+\d+", s, re.I):
                continue
            cleaned_lines.append(line)

        paragraphs = [p.strip() for p in re.split(r"\n{2,}", "\n".join(cleaned_lines)) if p.strip()]
        chunks = []
        for para in paragraphs:
            lines = para.split("\n")
            short = sum(1 for l in lines if len(l.strip()) < 15)
            if len(lines) > 3 and short / len(lines) > 0.6:
                continue
            if sum(1 for c in para if c.isalpha()) < len(para) * 0.3:
                continue
            clean = " ".join(para.split())
            sents = re.split(r"(?<=[.!?])\s+", clean)
            if len(sents) <= 2:
                chunks.append(clean)
            else:
                for i in range(0, len(sents), 2):
                    c = " ".join(sents[i:i + 2]).strip()
                    if c:
                        chunks.append(c)
        return [c for c in chunks if len(c) > 30]

    # --- main answer pipeline ---
    # This follows the RAG pattern from Class 11:
    # structured lookup -> TF-IDF retrieval -> (optional) LLM generation

    def answer(self, question: str) -> tuple[str, float, str]:
        # step 1: check if we can answer directly from extracted fields
        # (no NLP needed - just keyword matching on the question)
        structured = self._structured_answer(question)
        if structured:
            return structured, 1.0, "Extracted from syllabus structure"

        # step 2: TF-IDF retrieval - vectorize query, compute cosine similarity
        # against all chunks, return top matches (like Q27 in our exam)
        retrieved = self._retrieve(question, top_k=3)
        if not retrieved or retrieved[0][1] < 0.05:
            return (
                "I couldn't find information about that in this syllabus.",
                0.0, "",
            )

        best_chunk, best_score = retrieved[0]
        context = "\n\n".join(c for c, _ in retrieved)

        # step 3: if OpenAI key is set, use LLM to generate a concise answer
        # from the retrieved context (the "Generation" part of RAG)
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if api_key:
            llm = self._llm_answer(question, context, api_key)
            if llm:
                return llm, best_score, best_chunk

        # step 4: fallback - just return the best matching chunk cleaned up
        clean = self._clean_answer(question, best_chunk)
        if best_score < 0.15:
            return (
                f"Not very confident ({best_score:.0%} match). Closest I found:\n\n{clean}",
                best_score, best_chunk,
            )
        return clean, best_score, best_chunk

    # --- structured data lookup (no NLP, just keyword matching) ---

    def _structured_answer(self, question: str) -> str | None:
        q = question.lower().strip().rstrip("?").strip()

        ci = self.data.get("course_info", {})
        grading = self.data.get("grading", [])
        deadlines = self.data.get("deadlines", [])
        policies = self.data.get("policies", [])
        scale = self.data.get("grade_scale", [])

        # grading questions
        if any(kw in q for kw in ["how much", "worth", "weight", "percentage", "percent", "grading breakdown"]):
            # Specific component: "how much is the final worth"
            for g in grading:
                comp = g["component"].lower()
                if any(w in q for w in comp.split() if len(w) > 3):
                    pts = f" ({g['points']} points)" if "points" in g else ""
                    return f"{g['component']} is worth {g['weight']}% of your grade{pts}."
            # General grading overview
            if grading:
                lines = [f"  {g['component']}: {g['weight']}%" for g in grading]
                return "Grading breakdown:\n" + "\n".join(lines)

        # instructor info
        if any(kw in q for kw in ["who is the instructor", "who teaches", "professor", "who is the prof"]):
            parts = []
            if ci.get("instructor"):
                parts.append(f"Instructor: {ci['instructor']}")
            if ci.get("email"):
                parts.append(f"Email: {ci['email']}")
            if ci.get("office_hours"):
                parts.append(f"Office hours: {ci['office_hours']}")
            if parts:
                return "\n".join(parts)

        # TA info
        if any(kw in q for kw in ["who is the ta", "teaching assistant", "who is the la", "learning assistant"]):
            if ci.get("ta_name"):
                ans = f"TA: {ci['ta_name']}"
                if ci.get("ta_email"):
                    ans += f"\nEmail: {ci['ta_email']}"
                return ans
            return "No TA information found in the syllabus."

        # office hours
        if "office hour" in q:
            if ci.get("office_hours"):
                return f"Office hours: {ci['office_hours']}"

        # email / contact
        if any(kw in q for kw in ["email", "contact"]):
            parts = []
            if ci.get("instructor") and ci.get("email"):
                parts.append(f"{ci['instructor']}: {ci['email']}")
            if ci.get("ta_name"):
                ta_line = f"TA {ci['ta_name']}"
                if ci.get("ta_email"):
                    ta_line += f": {ci['ta_email']}"
                parts.append(ta_line)
            if parts:
                return "\n".join(parts)

        # deadlines / exams
        if any(kw in q for kw in ["when is the", "when are the", "deadline", "exam date", "midterm date", "final date"]):
            if "midterm" in q:
                matches = [d for d in deadlines if d["type"] in ("midterm",)]
            elif "final" in q:
                matches = [d for d in deadlines if d["type"] in ("final_exam",)]
            else:
                matches = deadlines

            if matches:
                lines = [f"  {d['date']}: {d['description']}" for d in matches]
                return "\n".join(lines)

        # late work / attendance / policies
        if any(kw in q for kw in ["late work", "late policy", "late submission", "late assignment", "penalty"]):
            for p in policies:
                if p["type"] == "late_work":
                    return p["text"]

        if any(kw in q for kw in ["attendance", "absent", "absence", "tardy", "skip class"]):
            for p in policies:
                if p["type"] == "attendance":
                    return p["text"]
            return "No specific attendance policy found in this syllabus."

        # AI usage policy
        if any(kw in q for kw in ["ai", "chatgpt", "gpt", "copilot", "llm", "generative ai", "artificial intelligence"]):
            for p in policies:
                if p["type"] == "ai_policy":
                    return p["text"]
            return "No AI usage policy found in this syllabus."

        if any(kw in q for kw in ["make-up", "makeup", "missed exam"]):
            for p in policies:
                if p["type"] == "makeup_exam":
                    return p["text"]

        if any(kw in q for kw in ["extra credit", "bonus"]):
            for p in policies:
                if p["type"] == "extra_credit":
                    return p["text"]
            return "No extra credit policy found in this syllabus."

        if any(kw in q for kw in ["academic integrity", "cheating", "plagiarism"]):
            for p in policies:
                if p["type"] == "academic_integrity":
                    return p["text"]

        # grade scale
        if any(kw in q for kw in ["grade scale", "grading scale", "what grade", "what is an a", "letter grade"]):
            if scale:
                lines = [f"  {s['grade']}: {s['min']}-{s['max']}%" for s in scale]
                return "Grade scale:\n" + "\n".join(lines)

        # meeting time
        if any(kw in q for kw in ["when does class meet", "class time", "meeting time", "what time", "schedule"]):
            if ci.get("meeting_time"):
                return f"Class meets: {ci['meeting_time']}"

        # credits / units
        if any(kw in q for kw in ["how many credit", "how many unit", "credit", "unit"]):
            if ci.get("units"):
                return f"This course is {ci['units']} unit(s)."

        # no structured match found
        return None

    # --- TF-IDF retrieval (core of our search - same idea as Q27 code fill-in) ---

    def _retrieve(self, question: str, top_k: int = 3) -> list[tuple[str, float]]:
        # transform the question into the same TF-IDF vector space as our chunks
        q_vec = self.vectorizer.transform([question])
        # compute cosine similarity between the query vector and every chunk
        # cosine_similarity = dot(a, b) / (||a|| * ||b||)
        # returns values between 0 (no match) and 1 (exact match)
        sims = cosine_similarity(q_vec, self.tfidf_matrix).flatten()
        # grab the indices of the top_k highest similarity scores
        top_idx = np.argsort(sims)[-top_k:][::-1]
        # only return chunks above a minimum threshold (0.02)
        return [(self.chunks[i], float(sims[i])) for i in top_idx if sims[i] > 0.02]

    # --- LLM answer generation (the "G" in RAG) ---

    def _llm_answer(self, question: str, context: str, api_key: str) -> str | None:
        # Uses the OpenAI chat completions API (Class 11)
        # - system role sets the assistant's behavior
        # - user role passes the retrieved context + question
        # - temperature=0.2 for mostly deterministic but slightly flexible output
        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content":
                        "You are a helpful syllabus assistant. Answer based ONLY on the context. "
                        "Be concise (1-3 sentences). If the answer isn't in the context, say so."},
                    {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"},
                ],
                max_tokens=200, temperature=0.2,
            )
            return response.choices[0].message.content.strip()
        except Exception:
            return None

    # --- fallback: clean up the best TF-IDF chunk into a readable answer ---

    def _clean_answer(self, question: str, chunk: str) -> str:
        q_words = set(re.findall(r"\w+", question.lower())) - {
            "what","is","the","how","much","are","who","when","where","does",
            "do","can","will","a","an","of","for","in","to","and","or","my",
            "this","that","there","about",
        }

        scored = []
        for sent in re.split(r"(?<=[.!?])\s+", chunk):
            sent = sent.strip()
            if len(sent) < 20 or re.match(r"^[●•\-\d\s%]+$", sent):
                continue
            overlap = sum(1 for w in q_words if w in sent.lower())
            if re.search(r"\d+%|\d+\s*points?", sent):
                overlap += 1
            scored.append((sent, overlap))

        scored.sort(key=lambda x: x[1], reverse=True)
        relevant = [s for s, sc in scored if sc > 0]
        if relevant:
            return " ".join(relevant[:2])

        fallback = [s for s, _ in scored if len(s) > 30]
        return fallback[0][:200] if fallback else "No specific answer found."
