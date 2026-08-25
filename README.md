# SHEA / IDSA Clostridioides Difficile Infection (CDI) Severity Grader

A clinical decision support engine implementing the **IDSA / SHEA 2017 & 2021 Clinical Practice Guidelines** for *Clostridioides difficile* infection (CDI) severity stratification, **ATLAS mortality risk score prediction**, and guideline-directed antimicrobial regimen recommendations.

---

## Clinical Domain & Diagnostic Criteria

*Clostridioides difficile* is the leading cause of healthcare-associated infectious diarrhea. The Infectious Diseases Society of America (IDSA) and Society for Healthcare Epidemiology of America (SHEA) updated clinical practice guidelines stratify CDI into three severity tiers to guide therapy:

### 1. SHEA / IDSA Severity Classification Criteria

| Severity Tier | Laboratory & Clinical Definition |
| :--- | :--- |
| **Non-Severe (Mild-to-Moderate)** | $\text{WBC} \le 15{,}000\text{ cells/}\mu\text{L}$ ($\le 15.0 \times 10^9/\text{L}$) **AND** $\text{Serum Creatinine} < 1.5\text{ mg/dL}$ (or $<1.5\times$ baseline) |
| **Severe** | $\text{WBC} \ge 15{,}000\text{ cells/}\mu\text{L}$ ($\ge 15.0 \times 10^9/\text{L}$) **OR** $\text{Serum Creatinine} \ge 1.5\text{ mg/dL}$ (or $\ge 1.5\times$ baseline) |
| **Fulminant (Severe, Complicated)** | Presence of severe CDI **PLUS** any of:<br>• Hypotension / Septic Shock ($\text{SBP} < 90\text{ mmHg}$ or vasopressors)<br>• Paralytic Ileus<br>• Toxic Megacolon ($>6\text{ cm}$ dilation with toxicity)<br>• Bowel Perforation / Peritonitis<br>• ICU admission for CDI |

---

### 2. IDSA / SHEA 2021 Guideline Treatment Recommendations

| Episode / Staging | Preferred Regimen | Alternative Regimen | Key Clinical Considerations |
| :--- | :--- | :--- | :--- |
| **Initial, Non-Severe** | **Fidaxomicin** 200 mg PO BID $\times 10$ days | **Vancomycin** 125 mg PO QID $\times 10$ days | Oral metronidazole is *no longer recommended* as first-line |
| **Initial, Severe** | **Fidaxomicin** 200 mg PO BID $\times 10$ days | **Vancomycin** 125 mg PO QID $\times 10$ days | Fidaxomicin preferred due to lower sustained recurrence rates |
| **Initial, Fulminant** | **Vancomycin** 500 mg PO/NG QID **PLUS** **Metronidazole** 500 mg IV Q8H | If ileus: Add Vancomycin retention enema (500 mg in 100 mL NS PR Q6H) | **Urgent surgical consultation** (subtotal colectomy / diverting ileostomy) |
| **First Recurrence** | **Fidaxomicin** 200 mg BID $\times 10$ days (or pulsed) | **Vancomycin** tapered/pulsed regimen | Consider **Bezlotoxumab** (10 mg/kg IV single dose) for high-risk patients |
| **Multiple Recurrences ($\ge 2$)** | **Fecal Microbiota Transplantation (FMT)** or Live Biotherapeutic Product | Vancomycin taper/pulse or Fidaxomicin | Restores colonic microbial diversity to prevent future relapses |

---

### 3. ATLAS Severity & Mortality Prediction Score

The **ATLAS Score** (Miller et al., 2013) predicts 30-day mortality and treatment failure ($0 - 10$ points):

$$\text{ATLAS} = \text{Age} + \text{Temperature} + \text{Leukocyte} + \text{Albumin} + \text{Systemic Antibiotics}$$

- **A**ge: $<60$ ($0$), $60-79$ ($1$), $\ge 80$ ($2$)
- **T**emperature: $<37.5^\circ\text{C}$ ($0$), $37.5-38.5^\circ\text{C}$ ($1$), $>38.5^\circ\text{C}$ ($2$)
- **L**eukocytes: $<16{,}000$ ($0$), $16{,}000-25{,}000$ ($1$), $>25{,}000$ ($2$)
- **A**lbumin: $>3.5\text{ g/dL}$ ($0$), $2.6-3.5\text{ g/dL}$ ($1$), $\le 2.5\text{ g/dL}$ ($2$)
- **S**ystemic Antibiotics ongoing: No ($0$), Yes ($2$)

**Risk Stratification:**
- Score 0 - 2: Low Risk ($< 2\%$ mortality)
- Score 3 - 5: Intermediate Risk ($5\% - 12\%$ mortality)
- Score 6 - 7: High Risk ($20\% - 30\%$ mortality)
- Score 8 - 10: Very High Risk ($> 35\%$ mortality)

---

## Installation & Requirements

Pure Python 3.9+ with zero external dependencies.

```bash
cd cdiff-shea-idsa-severity-grader
```

---

## CLI Usage

### 1. Grade Patient CDI Severity
```bash
python cli.py grade --wbc 18500 --creatinine 1.8
```

### 2. Fulminant CDI with Shock and Ileus
```bash
python cli.py grade --wbc 28000 --creatinine 2.4 --shock --ileus
```

### 3. Output Machine-Readable JSON
```bash
python cli.py grade --wbc 18500 --creatinine 1.8 --json
```

### 4. Calculate ATLAS Mortality Score
```bash
python cli.py atlas --age 75 --temp 38.8 --wbc 22000 --albumin 2.3 --abx
```

### 5. Interactive Staging Wizard
```bash
python cli.py interactive
```

### 6. Batch Process Cohort File
```bash
python cli.py batch --input cdiff_patients.csv --output results.csv
```

---

## Python API Usage

```python
from cdiff_grader import CDiffPatientInput, FulminantCriteria, EpisodeType, grade_cdiff_severity

patient = CDiffPatientInput(
    wbc_count=19200.0,
    serum_creatinine=1.9,
    baseline_creatinine=1.0,
    age=72,
    body_temperature_c=38.4,
    serum_albumin_g_dl=2.8,
    concomitant_antibiotics=True
)

result = grade_cdiff_severity(patient)
print(f"Severity: {result.severity.value}")
print(f"Preferred Therapy: {result.treatment.preferred_regimen}")
if result.atlas_score:
    print(f"ATLAS Score: {result.atlas_score.score}/10 ({result.atlas_score.predicted_mortality_percentage})")
```

---

## Unit Testing

Execute the comprehensive test suite:

```bash
python -m unittest -v test_cdiff_grader.py
```

Test coverage:
- Non-severe, severe (WBC $\ge 15\text{k}$ and/or SCr $\ge 1.5$), and fulminant tiers.
- Relative creatinine baseline escalation ($1.5\times$).
- Fulminant complications (shock, ileus, toxic megacolon, perforation).
- IDSA 2021 treatment algorithms (Initial, 1st recurrence, multiple recurrence).
- ATLAS scoring across all point categories and risk tiers.
- WBC format normalization (cells/$\mu$L vs $\times 10^9$/L).
- Boundary validation and input error raising.

---

## References

1. **McDonald LC, Gerding DN, Johnson S, et al.** Clinical Practice Guidelines for *Clostridium difficile* Infection in Adults and Children: 2017 Update by the IDSA and SHEA. *Clin Infect Dis*. 2018;66(7):e1-e48.
2. **Johnson S, Lavergne V, Skinner AM, et al.** Clinical Practice Guideline by the IDSA and SHEA: 2021 Focused Update Guidelines on Management of *Clostridioides difficile* Infection in Adults. *Clin Infect Dis*. 2021;73(5):e1029-e1044.
3. **Miller MA, Louie T, Mullane K, et al.** Derivation and validation of a simple clinical severity score (ATLAS) for *Clostridium difficile* infection. *Int J Antimicrob Agents*. 2013;41(4):349-354.

---

## License

MIT License.
