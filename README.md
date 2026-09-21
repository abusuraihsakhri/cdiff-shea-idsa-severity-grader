# CDI Severity Grader

### [Open the Live Application →](https://abusuraihsakhri.github.io/cdiff-shea-idsa-severity-grader/)

A small Python and browser-based tool for classifying adult *Clostridioides difficile* infection (CDI) severity using IDSA/SHEA criteria and calculating the published ATLAS treatment-response score.

The repository provides the same core grading logic through a command-line interface, Python API, CSV batch processor, and a browser interface powered by Pyodide.

> **Clinical scope:** This software is for education and decision support. It does not establish the diagnosis of CDI, replace clinical judgment, or account for every patient-specific contraindication, comorbidity, local formulary, or institutional policy.

## What it implements

### IDSA/SHEA severity classification

The severity rules follow the 2017 IDSA/SHEA guideline definitions retained in the 2021 focused treatment update:

| Classification | Implemented criterion |
| --- | --- |
| Non-severe | WBC ≤ 15,000 cells/µL **and** serum creatinine < 1.5 mg/dL |
| Severe | WBC > 15,000 cells/µL **or** serum creatinine ≥ 1.5 mg/dL |
| Fulminant | Hypotension/shock, ileus, or megacolon |

The current serum creatinine is assessed using the guideline's absolute threshold. A rise relative to a historical baseline is not used to assign IDSA/SHEA severity.

Bowel perforation/peritonitis and ICU admission can be recorded as critical contextual findings. They are not relabeled as defining IDSA/SHEA fulminant criteria; perforation/peritonitis still triggers an urgent surgical-evaluation flag.

### ATLAS score

ATLAS is implemented from the original five-component derivation:

- **A**ge
- **T**reatment with non-CDI systemic antibiotics during CDI therapy
- **L**eukocyte count
- serum **A**lbumin
- **S**erum creatinine

The score ranges from 0 to 10. The original derivation modeled clinical cure using:

`estimated cure (%) = 100 - 5.08 × ATLAS score`

This project reports that treatment-response estimate and a descriptive score band. It does **not** convert ATLAS into unvalidated mortality-risk categories.

## Browser application

The browser interface runs the repository's Python grading module client-side with Pyodide. Case inputs are not sent to this repository or stored by the application. The browser does download the Pyodide runtime from jsDelivr when the page loads.

Features include:

- compact responsive layout
- light theme with a dark-mode toggle
- severity, recurrence, treatment, and ATLAS output
- explicit fulminant and surgical-alert handling
- loading, validation, and runtime-error states
- keyboard-accessible labels, controls, and focus states

The first load can take longer because the Python/WebAssembly runtime must be downloaded. Subsequent behavior depends on browser caching and network conditions.

## Command-line use

Python 3.10 or newer is recommended. The core application has no third-party runtime dependencies.

```bash
git clone https://github.com/abusuraihsakhri/cdiff-shea-idsa-severity-grader.git
cd cdiff-shea-idsa-severity-grader
```

Grade a case:

```bash
python cli.py grade --wbc 18500 --creatinine 1.8
```

Grade a fulminant case and calculate ATLAS:

```bash
python cli.py grade \
  --wbc 24000 \
  --creatinine 2.4 \
  --shock \
  --ileus \
  --age 74 \
  --albumin 2.2 \
  --abx
```

Calculate ATLAS directly:

```bash
python cli.py atlas \
  --age 74 \
  --wbc 19000 \
  --creatinine 2.0 \
  --albumin 2.3 \
  --abx
```

Batch-process a CSV:

```bash
python cli.py batch --input sample.csv --output results.csv
```

## Python API

```python
from cdiff_grader import CDiffPatientInput, grade_cdiff_severity

patient = CDiffPatientInput(
    wbc_count=18500,
    serum_creatinine=1.8,
    age=68,
    serum_albumin_g_dl=2.9,
    concomitant_antibiotics=True,
)

result = grade_cdiff_severity(patient)

print(result.severity.value)
print(result.treatment.preferred_regimen)

if result.atlas_score:
    print(result.atlas_score.score)
    print(result.atlas_score.estimated_cure_rate_percentage)
```

## Local browser development

Serve the repository over HTTP so the browser can fetch the Python module:

```bash
python -m http.server 8000
```

Then open `http://localhost:8000/`.

The browser app requires JavaScript, WebAssembly, and network access to the pinned Pyodide CDN on initial load.

## Testing

Install the test-only dependency and run the suite:

```bash
python -m pip install "pytest>=8,<10"
python -m pytest -v
```

CI also compiles the source and smoke-tests severity grading, direct ATLAS scoring, and CSV batch processing on Python 3.10 through 3.14.

## References

- McDonald LC, Gerding DN, Johnson S, et al. IDSA/SHEA 2017 Clinical Practice Guidelines for CDI. *Clin Infect Dis.* 2018;66(7):e1-e48. doi:10.1093/cid/cix1085.
- Johnson S, Lavergne V, Skinner AM, et al. IDSA/SHEA 2021 Focused Update for CDI in Adults. *Clin Infect Dis.* 2021;73(5):e1029-e1044. doi:10.1093/cid/ciab549.
- Miller MA, Louie T, Mullane K, et al. Derivation and validation of the ATLAS bedside scoring system for CDI treatment response. *BMC Infect Dis.* 2013;13:148. doi:10.1186/1471-2334-13-148.

## License

MIT. See [LICENSE](LICENSE).
