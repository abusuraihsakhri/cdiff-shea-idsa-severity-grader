"use strict";

const PYODIDE_URL = "https://cdn.jsdelivr.net/pyodide/v314.0.7/full/";
const state = { pyodide: null, ready: false };

const byId = (id) => document.getElementById(id);
const form = byId("case-form");
const analyzeButton = byId("analyze-button");
const resetButton = byId("reset-button");
const runtimeStatus = byId("runtime-status");
const formError = byId("form-error");
const resultContent = byId("result-content");
const emptyState = byId("empty-state");
const severityBadge = byId("severity-badge");

function setRuntimeStatus(message, mode = "") {
  runtimeStatus.textContent = message;
  runtimeStatus.className = "status-pill";
  if (mode) runtimeStatus.classList.add(mode);
}

function showError(message) {
  formError.textContent = message;
  formError.hidden = false;
}

function clearError() {
  formError.textContent = "";
  formError.hidden = true;
}

function readOptionalNumber(id) {
  const value = byId(id).value.trim();
  return value === "" ? null : Number(value);
}

function buildPayload() {
  const age = readOptionalNumber("age");
  const albumin = readOptionalNumber("albumin");

  if ((age === null) !== (albumin === null)) {
    throw new Error("For ATLAS scoring, enter both age and serum albumin, or leave both blank.");
  }

  const payload = {
    wbc: Number(byId("wbc").value),
    creatinine: Number(byId("creatinine").value),
    recurrences: Number(byId("recurrences").value),
    prior_regimen: byId("prior-regimen").value || null,
    shock: byId("shock").checked,
    ileus: byId("ileus").checked,
    megacolon: byId("megacolon").checked,
    perforation: byId("perforation").checked,
    icu: byId("icu").checked,
    age,
    albumin,
    concomitant_abx: byId("abx").checked,
  };

  if (!Number.isFinite(payload.wbc) || payload.wbc <= 0) {
    throw new Error("Enter a positive WBC count.");
  }
  if (!Number.isFinite(payload.creatinine) || payload.creatinine <= 0) {
    throw new Error("Enter a positive serum creatinine.");
  }

  return payload;
}

function setText(id, value) {
  byId(id).textContent = value ?? "—";
}

function fillList(id, values) {
  const list = byId(id);
  list.replaceChildren();
  for (const value of values || []) {
    const item = document.createElement("li");
    item.textContent = value;
    list.appendChild(item);
  }
}

function formatLabel(value) {
  return String(value || "—")
    .replaceAll("_", " ")
    .toLowerCase()
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function renderResult(result) {
  emptyState.hidden = true;
  resultContent.hidden = false;

  const severity = result.severity || "";
  severityBadge.textContent = formatLabel(severity);
  severityBadge.className = "severity-badge";
  if (severity === "NON_SEVERE") severityBadge.classList.add("non-severe");
  else if (severity === "SEVERE") severityBadge.classList.add("severe");
  else if (severity === "FULMINANT") severityBadge.classList.add("fulminant");
  else severityBadge.classList.add("neutral");

  setText("severity-value", formatLabel(result.severity));
  setText("episode-value", formatLabel(result.episode_type));
  setText("rationale-value", result.severity_rationale);
  setText("preferred-value", result.treatment?.preferred_regimen);
  setText("alternative-value", result.treatment?.alternative_regimen || "None listed.");

  if (result.atlas_score) {
    const atlas = result.atlas_score;
    setText(
      "atlas-value",
      `${atlas.score}/10 · ${formatLabel(atlas.score_band)} · estimated cure ${atlas.estimated_cure_rate_percentage}%`
    );
  } else {
    setText("atlas-value", "Not calculated");
  }

  const surgical = Boolean(result.treatment?.surgical_consult_required);
  byId("surgical-alert").hidden = !surgical;

  fillList("adjunctive-list", result.treatment?.adjunctive_therapies);
  fillList("infection-list", result.treatment?.infection_control_measures);
  setText("clinical-note", result.treatment?.clinical_notes);
}

async function initializePython() {
  try {
    setRuntimeStatus("Loading Python runtime…");
    analyzeButton.disabled = true;

    if (typeof loadPyodide !== "function") {
      throw new Error("Pyodide loader did not initialize.");
    }

    state.pyodide = await loadPyodide({ indexURL: PYODIDE_URL });

    const response = await fetch("./cdiff_grader.py", { cache: "no-cache" });
    if (!response.ok) {
      throw new Error(`Could not load the grading engine (HTTP ${response.status}).`);
    }

    const source = await response.text();
    state.pyodide.FS.writeFile("/home/pyodide/cdiff_grader.py", source);
    await state.pyodide.runPythonAsync(
      "import sys\n" +
      "sys.path.insert(0, '/home/pyodide')\n" +
      "import cdiff_grader\n"
    );

    state.ready = true;
    analyzeButton.disabled = false;
    setRuntimeStatus("Runtime ready", "ready");
  } catch (error) {
    state.ready = false;
    analyzeButton.disabled = true;
    setRuntimeStatus("Runtime failed", "error");
    showError(
      "Python runtime failed to load. Check the network connection and reload the page. " +
      (error instanceof Error ? error.message : String(error))
    );
  }
}

async function analyze(event) {
  event.preventDefault();
  clearError();

  if (!state.ready || !state.pyodide) {
    showError("The Python runtime is not ready yet.");
    return;
  }

  if (!form.reportValidity()) return;

  try {
    const payload = buildPayload();
    analyzeButton.disabled = true;
    analyzeButton.textContent = "Analyzing…";

    state.pyodide.globals.set("payload_json", JSON.stringify(payload));
    const output = await state.pyodide.runPythonAsync(
      "import json\n" +
      "from cdiff_grader import grade_cdiff_severity\n" +
      "result_json = json.dumps(grade_cdiff_severity(json.loads(payload_json)).to_dict())\n" +
      "result_json"
    );

    renderResult(JSON.parse(String(output)));
  } catch (error) {
    showError(error instanceof Error ? error.message : String(error));
  } finally {
    analyzeButton.disabled = !state.ready;
    analyzeButton.textContent = "Analyze case";
  }
}

function resetForm() {
  form.reset();
  byId("wbc").value = "12000";
  byId("creatinine").value = "1.0";
  clearError();
  resultContent.hidden = true;
  emptyState.hidden = false;
  severityBadge.textContent = "Not calculated";
  severityBadge.className = "severity-badge neutral";
  byId("surgical-alert").hidden = true;
}

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  const dark = theme === "dark";
  byId("theme-toggle").setAttribute(
    "aria-label",
    dark ? "Switch to light theme" : "Switch to dark theme"
  );
}

function toggleTheme() {
  const current = document.documentElement.dataset.theme || "light";
  applyTheme(current === "light" ? "dark" : "light");
}

form.addEventListener("submit", analyze);
resetButton.addEventListener("click", resetForm);
byId("theme-toggle").addEventListener("click", toggleTheme);

applyTheme("light");
window.addEventListener("DOMContentLoaded", initializePython);
