# Cdiff Shea Idsa Severity Grader

> **Domain:** Infectious Disease Surveillance & Microbiology  
> **Reference Guidelines & Standards:** `CLSI M100, EUCAST & CDC NHSN Clinical Standards`

<div align="center">

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-3776AB.svg?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688.svg?logo=fastapi&logoColor=white)
![Audit Trail](https://img.shields.io/badge/Audit-HMAC--SHA256_Tamper--Evident-brightgreen.svg)
![Zero-PHI Guard](https://img.shields.io/badge/Guard-Zero--PHI_Outbound-blue.svg)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg?logo=docker&logoColor=white)

</div>

---

## 📖 What It Does

SHEA / IDSA Clostridioides Difficile Infection (CDI) Severity Grader
===================================================================
A clinical decision support engine implementing the IDSA / SHEA 2017 & 2021
guidelines for CDI severity staging, ATLAS score mortality risk stratification,
and evidence-based therapeutic regimen recommendation.

References:
- McDonald LC, Gerding DN, Johnson S, et al. Clinical Practice Guidelines
  for Clostridium difficile Infection in Adults and Children: 2017 Update by
  the IDSA and SHEA. Clin Infect Dis. 2018;66(7):e1-e48.
- Johnson S, Lavergne V, Skinner AM, et al. Clinical Practice Guideline by
  the IDSA and SHEA: 2021 Focused Update Guidelines on Management of
  Clostridioides difficile Infection in Adults. Clin Infect Dis. 2021;73(5):e1029-e1044.
- Miller MA, Louie T, Mullane K, et al. Derivation and validation of a simple
  clinical severity score (ATLAS) for Clostridium difficile infection.
  Int J Antimicrob Agents. 2013;41(4):349-354.
- Zar FA, Bakkanagari SR, Moorthi KM, Davis MB. A comparison of vancomycin
  and metronidazole for the treatment of C. diff, stratified by severity.
  Clin Infect Dis. 2007;45(3):302-307.

Author: Clinical AI & Domain Engineering
License: MIT

---

## ⚙️ Key Capabilities & Algorithmic Modules

### 🔬 Core Algorithmic & Evaluation Engines

- **`CDISeverity`** — dedicated module for c d i severity evaluation and state verification.
- **`EpisodeType`** — dedicated module for episode type evaluation and state verification.
- **`AtlasMortalityRisk`** — dedicated module for atlas mortality risk evaluation and state verification.
- **`FulminantCriteria`**: Fulminant CDI complications.
- **`CDiffPatientInput`**: Input clinical parameters for CDI severity grading and ATLAS score.
- **`TreatmentRecommendation`**: Guideline-directed CDI therapeutic regimen.

---

## 📐 Mathematical Formulation & Logic

```text
  return (
  Calculate ATLAS Score if parameters available
  atlas_res = calculate_atlas_score(inp)
  total_score = sum(breakdown.values())
```

---

## 💻 CLI Quickstart & Usage

### 1. Guided Interactive Mode
```bash
python cli.py
```

### 2. Direct Parameterized Evaluation
```bash
python cli.py --wbc <value> --creatinine <value> --shock <value> --ileus <value>
```

### Parameter Reference
- `--wbc`: Specifies input measurement or parameter value.
- `--creatinine`: Specifies input measurement or parameter value.
- `--shock`: Specifies input measurement or parameter value.
- `--ileus`: Specifies input measurement or parameter value.
- `--age`: Specifies input measurement or parameter value.
- `--temp`: Specifies input measurement or parameter value.
- `--albumin`: Specifies input measurement or parameter value.
- `--abx`: Specifies input measurement or parameter value.
- `--input`: Specifies input measurement or parameter value.
- `--output`: Specifies input measurement or parameter value.

### Input Data Schema

| Field | Description | Requirement |
|:------|:------------|:------------|
| `Patient_ID` | Parameter / observation metric | Required |
| `v1` | Parameter / observation metric | Required |
| `v2` | Parameter / observation metric | Required |
| `v3` | Parameter / observation metric | Required |

---

## 🛡️ Security & Enterprise Architecture

* **Zero-PHI Outbound Interceptor:** Active AST and regex inspection blocking SSNs, MRNs, phone numbers, and patient identifiers.
* **Tamper-Evident HMAC-SHA256 Audit Trail:** Chained, cryptographically signed logs for every evaluation and state transition.
* **Air-Gapped LLM Reasoning Adapter:** Agnostic integration for local Ollama instances (`llama3`, `mistral`), Claude 3.5 Sonnet, GPT-4o, and deterministic test mocks.
* **Active Learning Bayesian Calibration:** Dynamic tracker updating worker reliability weights and monitoring Brier calibration drift.
* **FastAPI & Prometheus Telemetry:** Exposes OpenAPI 3.1 REST endpoints and operational Prometheus metrics (`/metrics`).

---

## 🧪 Testing & Verification

Run the automated test suite:

```bash
pytest -v
```

Execute high-throughput batch simulation benchmarks:

```bash
python simulator.py --tasks 1000 --concurrency 8
```

---

## 🐳 Container Deployment

```bash
docker build -t cdiff-shea-idsa-severity-grader .
docker run -p 8000:8000 cdiff-shea-idsa-severity-grader
```
