"""
Core analysis logic for the AI Resume Analyzer.

Runs fully offline by default using TF-IDF keyword matching (no cloud
dependency). If an LLM endpoint is configured (see app/llm.py), it is used
to layer richer, natural-language suggestions on top of the local score.
"""

import re
from io import BytesIO

import pdfplumber
import docx
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# A compact seed list of common tech/professional skill keywords.
# Extend this list to tune matching for your target roles.
SKILL_KEYWORDS = [
    "python", "java", "javascript", "typescript", "kotlin", "sql", "c++",
    "react", "next.js", "node.js", "fastapi", "django", "flask",
    "spring boot", "docker", "kubernetes", "aws", "azure", "gcp",
    "rest api", "graphql", "microservices", "ci/cd", "git",
    "machine learning", "deep learning", "llm", "nlp", "rag",
    "prompt engineering", "langchain", "tensorflow", "pytorch",
    "pandas", "numpy", "scikit-learn", "postgresql", "mongodb",
    "redis", "agile", "scrum", "leadership", "communication",
]


def extract_text_from_pdf(file_bytes: bytes) -> str:
    text_parts = []
    with pdfplumber.open(BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            text_parts.append(page_text)
    return "\n".join(text_parts)


def extract_text_from_docx(file_bytes: bytes) -> str:
    document = docx.Document(BytesIO(file_bytes))
    return "\n".join(p.text for p in document.paragraphs)


def extract_text(filename: str, file_bytes: bytes) -> str:
    lower_name = filename.lower()
    if lower_name.endswith(".pdf"):
        return extract_text_from_pdf(file_bytes)
    if lower_name.endswith(".docx"):
        return extract_text_from_docx(file_bytes)
    if lower_name.endswith(".txt"):
        return file_bytes.decode("utf-8", errors="ignore")
    raise ValueError("Unsupported file type. Use PDF, DOCX, or TXT.")


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def find_keyword_hits(text: str, keywords: list[str]) -> set[str]:
    normalized = _normalize(text)
    hits = set()
    for kw in keywords:
        # word-boundary-ish match; handles multi-word skills like "rest api".
        # Trailing (es|s)? handles simple plurals: "LLM" matches "LLMs",
        # "REST API" matches "REST APIs", "microservice" matches "microservices".
        pattern = r"(?<![a-z0-9])" + re.escape(kw.lower()) + r"(es|s)?(?![a-z0-9])"
        if re.search(pattern, normalized):
            hits.add(kw)
    return hits


def tfidf_similarity(resume_text: str, jd_text: str) -> float:
    vectorizer = TfidfVectorizer(stop_words="english")
    tfidf_matrix = vectorizer.fit_transform([resume_text, jd_text])
    score = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
    return round(float(score) * 100, 2)


def rule_based_suggestions(missing_skills: set[str], match_score: float) -> list[str]:
    suggestions = []
    if missing_skills:
        top_missing = sorted(missing_skills)[:5]
        suggestions.append(
            f"Consider adding evidence of these skills if you have them: {', '.join(top_missing)}."
        )
    if match_score < 40:
        suggestions.append(
            "Overall keyword overlap with the job description is low — mirror more of the "
            "JD's terminology in your bullet points where truthfully applicable."
        )
    elif match_score < 70:
        suggestions.append(
            "Decent overlap. Tighten bullets to lead with quantified impact for the "
            "skills the JD emphasizes most."
        )
    else:
        suggestions.append(
            "Strong keyword alignment. Focus polish on quantifying outcomes and impact."
        )
    suggestions.append(
        "Use exact phrasing from the job description for tools/technologies you already know "
        "(e.g., 'REST API' vs 'RESTful services') to pass literal ATS keyword filters."
    )
    return suggestions


def analyze(resume_text: str, jd_text: str) -> dict:
    resume_hits = find_keyword_hits(resume_text, SKILL_KEYWORDS)
    jd_hits = find_keyword_hits(jd_text, SKILL_KEYWORDS)

    matched = sorted(resume_hits & jd_hits)
    missing = jd_hits - resume_hits

    similarity_score = tfidf_similarity(resume_text, jd_text)
    keyword_score = round((len(matched) / len(jd_hits) * 100), 2) if jd_hits else 0.0

    # Blend semantic (TF-IDF) similarity with literal keyword coverage.
    overall_score = round((similarity_score * 0.5) + (keyword_score * 0.5), 2)

    return {
        "overall_score": overall_score,
        "similarity_score": similarity_score,
        "keyword_score": keyword_score,
        "matched_skills": matched,
        "missing_skills": sorted(missing),
        "suggestions": rule_based_suggestions(missing, overall_score),
    }
