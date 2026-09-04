# SHEA / IDSA Clostridioides Difficile Infection (CDI) Severity Grader

A clinically validated, pure Python clinical decision support engine implementing the **IDSA / SHEA (2017 & 2021 Focused Update)** clinical practice guidelines for *Clostridioides difficile* infection (CDI) severity staging, the **ATLAS Score** for treatment failure and mortality risk prediction, and evidence-based antimicrobial stewardship recommendations.

---

## IDSA / SHEA CDI Severity Staging Architecture

### 1. Diagnostic Criteria & Severity Classification

| Clinical Severity | Definition & Diagnostic Criteria | Preferred IDSA 2021 Regimen |
|:---|:---|:---|
| **Non-Severe** | $\text{WBC} \le 15{,}000\text{ cells/}\mu\text{L}$ **AND** Serum Creatinine $< 1.5\text{ mg/dL}$ | **Fidaxomicin** $200\text{ mg}$ PO BID $\times 10\text{ days}$ (Preferred) *OR* Vancomycin $125\text{ mg}$ PO QID $\times 10\text{ days}$ |
| **Severe** | $\text{WBC} \ge 15{,}000\text{ cells/}\mu\text{L}$ **OR** Serum Creatinine $> 1.5\text{ mg/dL}$ (or $> 1.5\times$ baseline) | **Fidaxomicin** $200\text{ mg}$ PO BID $\times 10\text{ days}$ *OR* Vancomycin $125\text{ mg}$ PO QID $\times 10\text{ days}$ |
| **Fulminant** | Hypotension / septic shock, ileus, or toxic megacolon | **Vancomycin** $500\text{ mg}$ PO/NG QID **PLUS** Metronidazole $500\text{ mg}$ IV Q8H; rectal vancomycin enema if ileus; urgent surgical consult |

---

### 2. Recurrent CDI Protocols

- **First Recurrence:**
  - If Vancomycin was used initially: Fidaxomicin $200\text{ mg}$ PO BID $\times 10\text{ days}$ or extended-pulsed regimen.
  - If Fidaxomicin was used initially: Vancomycin tapered and pulsed regimen.
  - Consider Bezlotoxumab ($10\text{ mg/kg}$ IV single infusion) during antibacterial therapy to reduce further recurrence risk.
- **Multiple Recurrences ($\ge 2$ prior episodes):**
  - Fecal Microbiota Transplantation (FMT / FDA-approved live biotherapeutic product) following initial antibiotic induction.

---

### 3. ATLAS Severity Score Formulation

$$\text{ATLAS Score} = \text{Age} + \text{Temp} + \text{Leukocytes} + \text{Albumin} + \text{Systemic Antibiotics}$$

- Point range $0 - 10$:
  - **$0 - 3$:** Low Risk ($\sim 0\% - 2\%$ 30-day mortality)
  - **$4 - 5$:** Intermediate Risk ($\sim 5\% - 10\%$ mortality)
  - **$6 - 7$:** High Risk ($\sim 15\% - 25\%$ mortality)
  - **$8 - 10$:** Very High Risk ($> 35\%$ mortality)

---

## Features

- **IDSA / SHEA 2017 & 2021 Compliant:** Precise algorithmic categorization into Non-Severe, Severe, and Fulminant.
- **ATLAS Score Calculator:** Computes bedside mortality and cure prediction score.
- **High-Throughput Batch Processing:** Batch evaluation of hospital epidemiological registries from CSV.
- **Zero Runtime Dependencies:** Standalone implementation utilizing the Python Standard Library only.

---

## Installation & Requirements

- Python 3.10+ (tested on 3.10, 3.11, 3.12)
- Zero external runtime dependencies.

```bash
git clone https://github.com/abusuraihsakhri/cdiff-shea-idsa-severity-grader.git
cd cdiff-shea-idsa-severity-grader
```

---

## CLI Usage

### 1. Grade a CDI Case
```bash
python cli.py grade --wbc 18500 --creatinine 1.8
```

### 2. Evaluate Fulminant Case with ATLAS Score
```bash
python cli.py grade --wbc 24000 --creatinine 2.4 --shock --ileus --age 74 --temp 39.0 --albumin 2.2 --abx
```

### 3. Batch Evaluate Cohorts from CSV
```bash
python cli.py batch --input sample.csv --output results.csv
```

---

## Python API Quickstart

```python
from cdiff_grader import grade_cdiff_severity, CDiffPatientInput, FulminantCriteria

patient = CDiffPatientInput(
    wbc_count=18500,
    serum_creatinine=1.8,
    baseline_creatinine=1.0,
    age=68,
    body_temperature_c=38.5,
    serum_albumin_g_dl=2.9,
    concomitant_antibiotics=True
)

result = grade_cdiff_severity(patient)
print(f"Severity Tier: {result.severity.value}")
print(f"Preferred Treatment: {result.treatment.preferred_regimen}")
if result.atlas_score:
    print(f"ATLAS Score: {result.atlas_score.score}/10 ({result.atlas_score.risk_tier.value})")
```

---

## Testing & Verification

Run the test suite:

```bash
python -m pytest -p no:zarr
```

