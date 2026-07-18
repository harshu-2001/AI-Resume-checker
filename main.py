import logging

from fastapi import FastAPI, File, HTTPException, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.analyzer import analyze, extract_text
from app.llm import get_llm_suggestions, is_configured

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="AI Resume Analyzer",
    description="Scores a resume against a job description and suggests improvements.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeResponse(BaseModel):
    overall_score: float
    similarity_score: float
    keyword_score: float
    matched_skills: list[str]
    missing_skills: list[str]
    suggestions: list[str]
    llm_enhanced: bool


@app.get("/health")
def health():
    return {"status": "ok", "llm_enabled": is_configured()}


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze_resume(
    resume: UploadFile = File(..., description="Resume file: PDF, DOCX, or TXT"),
    job_description: str = Form(..., description="Full job description text"),
):
    if not job_description.strip():
        raise HTTPException(status_code=400, detail="job_description cannot be empty.")

    file_bytes = await resume.read()
    try:
        resume_text = extract_text(resume.filename, file_bytes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not resume_text.strip():
        raise HTTPException(status_code=422, detail="Could not extract any text from the resume file.")

    result = analyze(resume_text, job_description)

    llm_enhanced = False
    llm_result = get_llm_suggestions(resume_text, job_description)
    if llm_result:
        llm_enhanced = True
        result["overall_score"] = llm_result.get("match_score", result["overall_score"])
        result["missing_skills"] = llm_result.get("missing_skills", result["missing_skills"])
        result["suggestions"] = llm_result.get("suggestions", result["suggestions"])

    result["llm_enhanced"] = llm_enhanced
    return result


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
