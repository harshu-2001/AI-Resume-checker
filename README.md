# AI Resume Analyzer

Scores a resume against a job description, flags missing skills, and returns
actionable suggestions — as a REST API.

Runs fully standalone in Docker with **no cloud dependency** by default,
using TF-IDF similarity + keyword matching. If you set an `LLM_API_KEY`,
it layers LLM-generated (prompt-engineered) suggestions on top of the same
local score, with automatic fallback if the LLM call fails.

## Run with Docker

```bash
docker compose up --build
```

This starts two containers:
- **Backend API** → `http://localhost:8000` (Swagger docs at `/docs`)
- **Frontend UI** → `http://localhost:3000`

Open `http://localhost:3000`, paste a job description, drop a resume file, and
click **Run analysis**. The frontend talks to the backend via an nginx proxy
(`/api/*` → the `resume-analyzer` container), so there's no CORS setup and no
hardcoded backend URL — it works the same on localhost or any server you
deploy this to.

## Run locally without Docker

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

## API

### `GET /health`
Returns service status and whether the optional LLM layer is enabled.

### `POST /analyze`
Multipart form fields:
- `resume`: file upload (`.pdf`, `.docx`, or `.txt`)
- `job_description`: plain text field

Example with `curl`:

```bash
curl -X POST http://localhost:8000/analyze \
  -F "resume=@/path/to/resume.pdf" \
  -F "job_description=We are looking for a Python developer with FastAPI, Docker, and REST API experience..."
```

Example response:

```json
{
  "overall_score": 72.4,
  "similarity_score": 68.1,
  "keyword_score": 76.7,
  "matched_skills": ["docker", "fastapi", "python", "rest api"],
  "missing_skills": ["kubernetes", "graphql"],
  "suggestions": [
    "Consider adding evidence of these skills if you have them: graphql, kubernetes.",
    "Decent overlap. Tighten bullets to lead with quantified impact for the skills the JD emphasizes most.",
    "Use exact phrasing from the job description for tools/technologies you already know..."
  ],
  "llm_enhanced": false
}
```

## Enabling the LLM layer (optional)

Copy `.env.example` to `.env` and set `LLM_API_KEY` (any OpenAI-compatible
endpoint — OpenAI, Azure OpenAI-compatible gateway, or a local server like
Ollama's OpenAI-compatible API via `LLM_API_BASE`). Restart the container;
`/health` will report `llm_enabled: true` and responses will include
`llm_enhanced: true` when the LLM call succeeds.

### Using LM Studio (local model, no API key needed)

1. In LM Studio, load a model and open the **Developer** (or **Local Server**)
   tab, then click **Start Server**. Note the port (default `1234`) and the
   exact model identifier shown in the server log.
2. Set these in `.env`:
   ```
   LLM_API_KEY=lm-studio
   LLM_MODEL=<model identifier from LM Studio>
   ```
   The key value itself doesn't matter to LM Studio (it doesn't check it) —
   the app just requires the field to be non-empty to turn the LLM layer on.
3. Set `LLM_API_BASE` depending on how you run the app:
   - **Via `docker compose up`**: `LLM_API_BASE=http://host.docker.internal:1234/v1`
     (the compose file already maps `host.docker.internal` to your host machine
     via `extra_hosts`, since "localhost" inside a container means the
     container itself, not your host).
   - **Running `uvicorn` directly on your host (no Docker)**:
     `LLM_API_BASE=http://localhost:1234/v1`
4. Restart: `docker compose up --build`. Check `curl http://localhost:8000/health`
   — you should see `"llm_enabled": true`. If a request to `/analyze` can't
   reach LM Studio for any reason, it silently falls back to the local
   TF-IDF/keyword score, so the app never breaks because of it.

## Architecture

```
main.py              FastAPI app, /analyze and /health routes
app/analyzer.py       Text extraction (PDF/DOCX/TXT), TF-IDF similarity,
                      keyword matching, rule-based suggestions (offline core)
app/llm.py            Optional OpenAI-compatible LLM call for richer
                      suggestions; degrades gracefully on any failure
Dockerfile             Backend container image, served via Uvicorn
frontend/              Static HTML/CSS/JS UI, served via nginx
frontend/nginx.conf    Serves the UI + proxies /api/* to the backend container
frontend/Dockerfile    Frontend container image
docker-compose.yml     Runs backend + frontend together on one Docker network
.github/workflows/     CI: builds & pushes both images to GHCR on push to main
```

## Deploying

### Push the code to GitHub

```bash
cd ai-resume-analyzer
git init
git add .
git commit -m "Initial commit: AI resume analyzer + frontend"
git branch -M main
git remote add origin https://github.com/<your-username>/<your-repo>.git
git push -u origin main
```

`.gitignore` already excludes `.env`, `__pycache__/`, and local virtualenvs —
your `LLM_API_KEY` (if you ever set a real cloud one) won't get committed.

### CI: auto-build both Docker images

`.github/workflows/docker-publish.yml` is already included. On every push to
`main`, GitHub Actions builds the backend and frontend images and pushes them
to **GitHub Container Registry (GHCR)** — no extra setup or secrets needed
beyond the repo's built-in `GITHUB_TOKEN`. After your first push, check the
**Actions** tab on GitHub to watch it run, then find the images under your
GitHub profile's **Packages** tab as:
- `ghcr.io/<your-username>/<repo>-backend:latest`
- `ghcr.io/<your-username>/<repo>-frontend:latest`

### Running the published images anywhere (e.g. a VPS)

Once the images are published, any server with Docker installed can run the
app without needing your source code at all — just this `docker-compose.yml`
pointed at the GHCR images instead of `build:`:

```yaml
services:
  resume-analyzer:
    image: ghcr.io/<your-username>/<repo>-backend:latest
    ports: ["8000:8000"]
    environment:
      - LLM_API_KEY=${LLM_API_KEY:-}
      - LLM_API_BASE=${LLM_API_BASE:-https://api.openai.com/v1}
      - LLM_MODEL=${LLM_MODEL:-gpt-4o-mini}
    networks: [resume-net]

  frontend:
    image: ghcr.io/<your-username>/<repo>-frontend:latest
    ports: ["3000:80"]
    networks: [resume-net]

networks:
  resume-net:
    driver: bridge
```

Note: if you deploy this way, drop the `extra_hosts: host.docker.internal`
LM Studio setup — that only makes sense when the LLM server is on the same
machine as Docker. For a real server deployment, either point `LLM_API_BASE`
at a real hosted LLM endpoint, or leave `LLM_API_KEY` unset and let the app
run on local TF-IDF scoring only (which is what "no cloud dependency" means
in practice for a deployed instance).

## Notes / extension ideas
- Swap the seed `SKILL_KEYWORDS` list in `analyzer.py` for a taxonomy suited
  to your target roles.
- Add request logging/latency metrics for an observability story.
- Persist each analysis (SQLite/Postgres) to show history over time.
