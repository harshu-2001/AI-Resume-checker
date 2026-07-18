const RING_CIRCUMFERENCE = 540.35; // 2 * PI * 86

const el = (id) => document.getElementById(id);

const form = el("analyzeForm");
const jdInput = el("jdInput");
const fileInput = el("fileInput");
const dropzone = el("dropzone");
const dropzoneInner = el("dropzoneInner");
const submitBtn = el("submitBtn");
const submitBtnText = el("submitBtnText");
const errorMsg = el("errorMsg");
const resultsSection = el("resultsSection");

let selectedFile = null;

// ---------- health check ----------
async function checkHealth() {
  const dot = el("statusDot");
  const text = el("statusText");
  try {
    const res = await fetch("/api/health");
    const data = await res.json();
    dot.classList.add("ok");
    text.textContent = data.llm_enabled ? "engine ready · llm on" : "engine ready · local only";
  } catch (e) {
    dot.classList.add("down");
    text.textContent = "engine unreachable";
  }
}
checkHealth();

// ---------- dropzone interactions ----------
dropzone.addEventListener("click", () => fileInput.click());

dropzone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropzone.classList.add("drag-over");
});

dropzone.addEventListener("dragleave", () => {
  dropzone.classList.remove("drag-over");
});

dropzone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropzone.classList.remove("drag-over");
  if (e.dataTransfer.files.length) {
    setFile(e.dataTransfer.files[0]);
  }
});

fileInput.addEventListener("change", () => {
  if (fileInput.files.length) {
    setFile(fileInput.files[0]);
  }
});

function setFile(file) {
  selectedFile = file;
  dropzone.classList.add("has-file");
  dropzoneInner.innerHTML = `
    <span class="dropzone-icon">✓</span>
    <span class="dropzone-text">
      <strong>${escapeHtml(file.name)}</strong>
      <br /><span class="dropzone-hint">${(file.size / 1024).toFixed(0)} KB · click to change</span>
    </span>
  `;
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

// ---------- form submit ----------
form.addEventListener("submit", async (e) => {
  e.preventDefault();
  hideError();

  if (!selectedFile) {
    showError("Choose a résumé file first.");
    return;
  }

  const formData = new FormData();
  formData.append("resume", selectedFile);
  formData.append("job_description", jdInput.value);

  setLoading(true);

  try {
    const res = await fetch("/api/analyze", {
      method: "POST",
      body: formData,
    });

    if (!res.ok) {
      const errBody = await res.json().catch(() => ({}));
      throw new Error(errBody.detail || `Request failed (${res.status})`);
    }

    const data = await res.json();
    renderResults(data);
  } catch (err) {
    showError(err.message || "Something went wrong. Check the API is reachable.");
  } finally {
    setLoading(false);
  }
});

function setLoading(isLoading) {
  submitBtn.disabled = isLoading;
  submitBtn.classList.toggle("loading", isLoading);
  submitBtnText.textContent = isLoading ? "Analyzing" : "Run analysis";
}

function showError(msg) {
  errorMsg.textContent = msg;
  errorMsg.hidden = false;
}

function hideError() {
  errorMsg.hidden = true;
}

// ---------- render results ----------
function renderResults(data) {
  resultsSection.hidden = false;

  const overall = Math.max(0, Math.min(100, data.overall_score ?? 0));
  el("overallScore").textContent = Math.round(overall);
  el("similarityScore").textContent = `${Math.round(data.similarity_score ?? 0)}%`;
  el("keywordScore").textContent = `${Math.round(data.keyword_score ?? 0)}%`;

  const ringFill = el("ringFill");
  const offset = RING_CIRCUMFERENCE * (1 - overall / 100);
  // Force reflow so the transition re-triggers on repeat submissions.
  ringFill.style.transition = "none";
  ringFill.style.strokeDashoffset = RING_CIRCUMFERENCE;
  void ringFill.getBoundingClientRect();
  ringFill.style.transition = "";
  requestAnimationFrame(() => {
    ringFill.style.strokeDashoffset = offset;
  });

  const llmBadge = el("llmBadge");
  llmBadge.textContent = data.llm_enhanced ? "✓ llm-enhanced" : "local scoring only";
  llmBadge.classList.toggle("on", !!data.llm_enhanced);

  const matched = data.matched_skills || [];
  const missing = data.missing_skills || [];

  el("matchedCount").textContent = `(${matched.length})`;
  el("matchedSkills").innerHTML = matched
    .map((s) => `<span class="chip matched">${escapeHtml(s)}</span>`)
    .join("") || `<p class="empty-note">No overlapping keywords found.</p>`;

  el("missingCount").textContent = `(${missing.length})`;
  const missingEl = el("missingSkills");
  const emptyNote = el("missingEmptyNote");
  if (missing.length) {
    missingEl.innerHTML = missing.map((s) => `<span class="chip missing">${escapeHtml(s)}</span>`).join("");
    emptyNote.hidden = true;
  } else {
    missingEl.innerHTML = "";
    emptyNote.hidden = false;
  }

  const suggestions = data.suggestions || [];
  el("suggestionList").innerHTML = suggestions.map((s) => `<li>${escapeHtml(s)}</li>`).join("");

  resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });
}
