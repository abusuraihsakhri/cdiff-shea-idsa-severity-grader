#!/usr/bin/env python3
"""
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
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union


# ==============================================================================
# ENUMS & CONSTANTS
# ==============================================================================

class CDISeverity(str, Enum):
    NON_SEVERE = "NON_SEVERE"         # WBC <= 15k AND SCr < 1.5 mg/dL
    SEVERE = "SEVERE"                 # WBC >= 15k OR SCr >= 1.5 mg/dL
    FULMINANT = "FULMINANT"           # Severe + Hypotension/Shock, Ileus, or Toxic Megacolon


class EpisodeType(str, Enum):
    INITIAL = "INITIAL_EPISODE"
    FIRST_RECURRENCE = "FIRST_RECURRENCE"
    MULTIPLE_RECURRENCE = "MULTIPLE_RECURRENCE" # >= 2 recurrences


class AtlasMortalityRisk(str, Enum):
    LOW = "LOW_RISK"                  # Score 0 - 2 (Mortality ~0-2%)
    INTERMEDIATE = "INTERMEDIATE_RISK"# Score 3 - 5 (Mortality ~5-12%)
    HIGH = "HIGH_RISK"                # Score 6 - 7 (Mortality ~20-30%)
    VERY_HIGH = "VERY_HIGH_RISK"      # Score 8 - 10 (Mortality > 35%)


WBC_SEVERE_THRESHOLD = 15000.0        # cells/uL or 15.0 x 10^9/L
SCR_SEVERE_THRESHOLD = 1.5            # mg/dL
SCR_BASELINE_RATIO_THRESHOLD = 1.5    # 50% increase over baseline


# ==============================================================================
# DATA MODELS
# ==============================================================================

@dataclass
class FulminantCriteria:
    """Fulminant CDI complications."""
    hypotension_or_shock: bool = False      # SBP < 90 mmHg or vasopressor requirement
    ileus: bool = False                     # Absent bowel sounds / radiologic ileus
    toxic_megacolon: bool = False           # Colonic dilation > 6 cm with toxicity
    bowel_perforation_or_peritonitis: bool = False
    icu_admission_for_cdi: bool = False

    def is_present(self) -> bool:
        return (
            self.hypotension_or_shock
            or self.ileus
            or self.toxic_megacolon
            or self.bowel_perforation_or_peritonitis
            or self.icu_admission_for_cdi
        )

    def positive_list(self) -> List[str]:
        pos = []
        if self.hypotension_or_shock:
            pos.append("Hypotension / Septic Shock")
        if self.ileus:
            pos.append("Paralytic Ileus")
        if self.toxic_megacolon:
            pos.append("Toxic Megacolon")
        if self.bowel_perforation_or_peritonitis:
            pos.append("Bowel Perforation / Peritonitis")
        if self.icu_admission_for_cdi:
            pos.append("ICU Admission for CDI")
        return pos


@dataclass
class CDiffPatientInput:
    """Input clinical parameters for CDI severity grading and ATLAS score."""
    wbc_count: float                        # WBC count in cells/uL (e.g. 16500) or x10^9/L (e.g. 16.5)
    serum_creatinine: float                 # Current SCr in mg/dL (e.g. 1.8)
    baseline_creatinine: Optional[float] = None # Baseline SCr if known (mg/dL)
    fulminant_criteria: FulminantCriteria = field(default_factory=FulminantCriteria)
    episode_type: EpisodeType = EpisodeType.INITIAL
    prior_recurrence_count: int = 0
    prior_regimen: Optional[str] = None     # e.g., 'VANCOMYCIN', 'FIDAXOMICIN', 'METRONIDAZOLE'
    
    # Optional parameters for ATLAS score
    age: Optional[int] = None               # Patient age in years
    body_temperature_c: Optional[float] = None # Peak temperature in Celsius (e.g. 38.6)
    serum_albumin_g_dl: Optional[float] = None # Serum albumin in g/dL (e.g. 2.4)
    concomitant_antibiotics: bool = False   # Concurrent non-CDI systemic antibiotics

    def normalized_wbc(self) -> float:
        """Normalizes WBC to cells/uL (if entered as 15.2, converts to 15200)."""
        if self.wbc_count < 100.0:
            return self.wbc_count * 1000.0
        return self.wbc_count

    def validate(self) -> List[str]:
        errors = []
        if self.wbc_count <= 0:
            errors.append("WBC count must be positive.")
        if self.serum_creatinine <= 0:
            errors.append("Serum creatinine must be positive.")
        if self.baseline_creatinine is not None and self.baseline_creatinine <= 0:
            errors.append("Baseline creatinine must be positive.")
        if self.age is not None and not (0 <= self.age <= 125):
            errors.append(f"Age {self.age} is out of realistic range (0-125).")
        if self.body_temperature_c is not None and not (30.0 <= self.body_temperature_c <= 45.0):
            errors.append(f"Body temperature {self.body_temperature_c} C is out of realistic range (30-45 C).")
        if self.serum_albumin_g_dl is not None and not (0.5 <= self.serum_albumin_g_dl <= 7.0):
            errors.append(f"Serum albumin {self.serum_albumin_g_dl} g/dL is out of realistic range (0.5-7.0).")
        return errors


@dataclass
class TreatmentRecommendation:
    """Guideline-directed CDI therapeutic regimen."""
    preferred_regimen: str
    alternative_regimen: Optional[str]
    adjunctive_therapies: List[str]
    surgical_consult_required: bool
    infection_control_measures: List[str]
    clinical_notes: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AtlasScoreResult:
    """Calculation result for the ATLAS CDI Severity & Mortality Score."""
    score: int                              # 0 to 10
    risk_tier: AtlasMortalityRisk
    predicted_mortality_percentage: str
    component_breakdown: Dict[str, int]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": self.score,
            "risk_tier": self.risk_tier.value,
            "predicted_mortality_percentage": self.predicted_mortality_percentage,
            "component_breakdown": self.component_breakdown,
        }


@dataclass
class CDiffSeverityResult:
    """Comprehensive evaluation result for C. difficile severity grading."""
    severity: CDISeverity
    episode_type: EpisodeType
    wbc_cells_ul: float
    serum_creatinine_mg_dl: float
    is_wbc_elevated: bool
    is_creatinine_elevated: bool
    fulminant_criteria_present: List[str]
    treatment: TreatmentRecommendation
    atlas_score: Optional[AtlasScoreResult]
    severity_rationale: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "severity": self.severity.value,
            "episode_type": self.episode_type.value,
            "wbc_cells_ul": round(self.wbc_cells_ul, 0),
            "serum_creatinine_mg_dl": round(self.serum_creatinine_mg_dl, 2),
            "is_wbc_elevated": self.is_wbc_elevated,
            "is_creatinine_elevated": self.is_creatinine_elevated,
            "fulminant_criteria_present": self.fulminant_criteria_present,
            "treatment": self.treatment.to_dict(),
            "atlas_score": self.atlas_score.to_dict() if self.atlas_score else None,
            "severity_rationale": self.severity_rationale,
        }


# ==============================================================================
# CORE GRADING & GUIDELINE ENGINE
# ==============================================================================

def grade_cdiff_severity(patient_input: Union[CDiffPatientInput, Dict[str, Any]]) -> CDiffSeverityResult:
    """
    Evaluates Clostridioides difficile infection severity per SHEA/IDSA 2017 & 2021 guidelines.

    Parameters:
        patient_input: CDiffPatientInput instance or dictionary of clinical parameters.

    Returns:
        CDiffSeverityResult with severity tier, rationale, treatment, and ATLAS score.
    """
    if isinstance(patient_input, dict):
        inp = _parse_dict_to_patient_input(patient_input)
    else:
        inp = patient_input

    errors = inp.validate()
    if errors:
        raise ValueError("Invalid CDI patient inputs: " + "; ".join(errors))

    norm_wbc = inp.normalized_wbc()
    scr = inp.serum_creatinine

    # Evaluate criteria
    wbc_elevated = norm_wbc >= WBC_SEVERE_THRESHOLD
    if inp.baseline_creatinine is not None:
        creatinine_elevated = (scr >= SCR_SEVERE_THRESHOLD) or (scr >= inp.baseline_creatinine * SCR_BASELINE_RATIO_THRESHOLD)
    else:
        creatinine_elevated = scr >= SCR_SEVERE_THRESHOLD

    fulminant_pos = inp.fulminant_criteria.positive_list()
    has_fulminant = len(fulminant_pos) > 0

    # Severity Tier Determination
    if has_fulminant:
        severity = CDISeverity.FULMINANT
        rationale = f"Fulminant CDI: Patient exhibits severe CDI with critical systemic/colonic complications: {', '.join(fulminant_pos)}."
    elif wbc_elevated or creatinine_elevated:
        severity = CDISeverity.SEVERE
        reasons = []
        if wbc_elevated:
            reasons.append(f"WBC ({norm_wbc:.0f} cells/uL) >= {WBC_SEVERE_THRESHOLD:.0f}")
        if creatinine_elevated:
            if inp.baseline_creatinine:
                reasons.append(f"SCr ({scr:.2f} mg/dL) >= 1.5x baseline ({inp.baseline_creatinine:.2f} mg/dL)")
            else:
                reasons.append(f"SCr ({scr:.2f} mg/dL) >= {SCR_SEVERE_THRESHOLD} mg/dL")
        rationale = f"Severe CDI: Laboratory criteria met ({'; '.join(reasons)})."
    else:
        severity = CDISeverity.NON_SEVERE
        rationale = f"Non-Severe CDI: WBC ({norm_wbc:.0f} cells/uL) < 15,000 and SCr ({scr:.2f} mg/dL) < 1.5 mg/dL without fulminant features."

    # Determine episode classification
    if inp.prior_recurrence_count >= 2 or inp.episode_type == EpisodeType.MULTIPLE_RECURRENCE:
        ep_type = EpisodeType.MULTIPLE_RECURRENCE
    elif inp.prior_recurrence_count == 1 or inp.episode_type == EpisodeType.FIRST_RECURRENCE:
        ep_type = EpisodeType.FIRST_RECURRENCE
    else:
        ep_type = EpisodeType.INITIAL

    # Generate Guideline Treatment Recommendation
    treatment = _generate_treatment_plan(severity, ep_type, inp)

    # Calculate ATLAS Score if parameters available
    atlas_res = None
    if inp.age is not None or inp.serum_albumin_g_dl is not None or inp.body_temperature_c is not None:
        atlas_res = calculate_atlas_score(inp)

    return CDiffSeverityResult(
        severity=severity,
        episode_type=ep_type,
        wbc_cells_ul=norm_wbc,
        serum_creatinine_mg_dl=scr,
        is_wbc_elevated=wbc_elevated,
        is_creatinine_elevated=creatinine_elevated,
        fulminant_criteria_present=fulminant_pos,
        treatment=treatment,
        atlas_score=atlas_res,
        severity_rationale=rationale,
    )


def calculate_atlas_score(patient_input: CDiffPatientInput) -> AtlasScoreResult:
    """
    Computes the ATLAS CDI Mortality Prediction Score (Miller et al., 2013).
    Range: 0 to 10 points.
    """
    breakdown = {}

    # 1. Age (0, 1, 2 pts)
    age = patient_input.age if patient_input.age is not None else 50
    if age < 60:
        age_pts = 0
    elif age < 80:
        age_pts = 1
    else:
        age_pts = 2
    breakdown["age_score"] = age_pts

    # 2. Temperature (0, 1, 2 pts)
    temp = patient_input.body_temperature_c if patient_input.body_temperature_c is not None else 37.0
    if temp < 37.5:
        temp_pts = 0
    elif temp <= 38.5:
        temp_pts = 1
    else:
        temp_pts = 2
    breakdown["temperature_score"] = temp_pts

    # 3. Leukocyte count (0, 1, 2 pts)
    wbc = patient_input.normalized_wbc()
    if wbc < 16000:
        wbc_pts = 0
    elif wbc <= 25000:
        wbc_pts = 1
    else:
        wbc_pts = 2
    breakdown["leukocyte_score"] = wbc_pts

    # 4. Albumin (0, 1, 2 pts)
    alb = patient_input.serum_albumin_g_dl if patient_input.serum_albumin_g_dl is not None else 3.6
    if alb > 3.5:
        alb_pts = 0
    elif alb >= 2.6:
        alb_pts = 1
    else:
        alb_pts = 2
    breakdown["albumin_score"] = alb_pts

    # 5. Systemic non-CDI Antibiotics (0 or 2 pts)
    abx_pts = 2 if patient_input.concomitant_antibiotics else 0
    breakdown["concomitant_abx_score"] = abx_pts

    total_score = sum(breakdown.values())

    # Mortality Risk Stratification
    if total_score <= 2:
        tier = AtlasMortalityRisk.LOW
        mort_pct = "< 2% 30-day mortality"
    elif total_score <= 5:
        tier = AtlasMortalityRisk.INTERMEDIATE
        mort_pct = "5% - 12% 30-day mortality"
    elif total_score <= 7:
        tier = AtlasMortalityRisk.HIGH
        mort_pct = "20% - 30% 30-day mortality"
    else:
        tier = AtlasMortalityRisk.VERY_HIGH
        mort_pct = "> 35% 30-day mortality"

    return AtlasScoreResult(
        score=total_score,
        risk_tier=tier,
        predicted_mortality_percentage=mort_pct,
        component_breakdown=breakdown,
    )


def _generate_treatment_plan(
    severity: CDISeverity,
    episode_type: EpisodeType,
    inp: CDiffPatientInput
) -> TreatmentRecommendation:
    """Generates IDSA/SHEA 2021 guideline therapeutic regimen."""
    adjunctive = [
        "Discontinue inciting/unnecessary antimicrobial agents as soon as clinically feasible.",
        "Avoid anti-peristaltic / anti-motility agents (e.g. loperamide, diphenoxylate/atropine).",
        "Implement Contact Precautions (gloves, gown, soap & water hand hygiene; alcohol sanitizer is sporicidally ineffective).",
    ]

    infection_control = [
        "Private room with dedicated toilet.",
        "Washing hands with soap and water before and after patient contact (spores resistant to alcohol).",
        "Sporicidal cleaning / disinfection of patient room (e.g., sodium hypochlorite / bleach-based solutions).",
    ]

    if severity == CDISeverity.FULMINANT:
        preferred = "Vancomycin 500 mg PO/NG four times daily (QID) PLUS Metronidazole 500 mg IV every 8 hours (Q8H)."
        alternative = "If ileus present, add Vancomycin retention enema 500 mg in 100 mL normal saline PR every 6 hours."
        surgical = True
        notes = (
            "EMERGENCY: Fulminant CDI carries high mortality. Obtain urgent surgical consultation for consideration "
            "of subtotal colectomy or diverting loop ileostomy with colonic lavage. Monitor closely in ICU."
        )
        if inp.fulminant_criteria.ileus:
            adjunctive.append("ILEUS DETECTED: Administer rectal vancomycin enemas (500 mg in 100 mL NS PR Q6H via Foley catheter with balloon inflated).")

    elif episode_type == EpisodeType.INITIAL:
        preferred = "Fidaxomicin 200 mg PO twice daily (BID) for 10 days (IDSA 2021 Preferred)."
        alternative = "Vancomycin 125 mg PO four times daily (QID) for 10 days (Standard Alternative)."
        surgical = False
        notes = (
            "Fidaxomicin is preferred over standard vancomycin due to lower sustained recurrence rates. "
            "Oral metronidazole is NO LONGER recommended as first-line therapy unless vancomycin and fidaxomicin are inaccessible."
        )

    elif episode_type == EpisodeType.FIRST_RECURRENCE:
        prior = (inp.prior_regimen or "").upper()
        if "VANCOMYCIN" in prior:
            preferred = "Fidaxomicin 200 mg PO twice daily (BID) for 10 days OR Fidaxomicin extended-pulsed regimen (200 mg BID x 5 days, then every other day x 20 days)."
            alternative = "Vancomycin tapered and pulsed regimen (e.g. 125 mg QID x 10-14 days, BID x 7 days, daily x 7 days, then every 2-3 days for 2-8 weeks)."
        elif "FIDAXOMICIN" in prior:
            preferred = "Vancomycin tapered and pulsed regimen."
            alternative = "Fidaxomicin extended-pulsed regimen."
        else:
            preferred = "Fidaxomicin 200 mg PO BID for 10 days (or Vancomycin pulsed/tapered regimen)."
            alternative = "Vancomycin 125 mg PO QID for 10 days."

        surgical = False
        adjunctive.append("Consider Bezlotoxumab 10 mg/kg IV single dose during antibacterial therapy for patients at high risk of recurrence (age >= 65, immunocompromised, severe CDI).")
        notes = (
            "First recurrence management strategy depends on prior exposure. "
            "Bezlotoxumab monoclonal antibody provides passive immunity against C. diff Toxin B and reduces subsequent recurrence risk."
        )

    else: # MULTIPLE_RECURRENCE (>= 2 prior episodes)
        preferred = "Fecal Microbiota Transplantation (FMT / Live Biotherapeutic Product) following 10-14 day course of oral Vancomycin or Fidaxomicin."
        alternative = "Vancomycin tapered and pulsed regimen OR Fidaxomicin 200 mg PO BID for 10 days followed by secondary prophylaxis."
        surgical = False
        adjunctive.append("Evaluate eligibility for FDA-approved fecal microbiota products (e.g., fecal microbiota spores / suspension).")
        notes = (
            "Patients with >= 2 recurrences (3rd episode total) should be referred for Fecal Microbiota Transplantation (FMT) "
            "or live biotherapeutic products to restore colonic microbial diversity."
        )

    return TreatmentRecommendation(
        preferred_regimen=preferred,
        alternative_regimen=alternative,
        adjunctive_therapies=adjunctive,
        surgical_consult_required=surgical,
        infection_control_measures=infection_control,
        clinical_notes=notes,
    )


# ==============================================================================
# DICTIONARY PARSER
# ==============================================================================

def _parse_dict_to_patient_input(d: Dict[str, Any]) -> CDiffPatientInput:
    """Parses loose dictionary or CSV row into structured CDiffPatientInput."""
    wbc = float(d.get("wbc_count", d.get("wbc", 10000.0)))
    scr = float(d.get("serum_creatinine", d.get("creatinine", d.get("scr", 1.0))))
    base_scr = d.get("baseline_creatinine", d.get("baseline_scr"))
    base_scr_val = float(base_scr) if base_scr is not None and str(base_scr).strip() != "" else None

    # Fulminant criteria parsing
    def _to_bool(val: Any) -> bool:
        if isinstance(val, bool):
            return val
        if val is None:
            return False
        s = str(val).strip().lower()
        return s in ["true", "1", "yes", "y", "t"]

    fulm_in = d.get("fulminant_criteria")
    if isinstance(fulm_in, dict):
        fulm = FulminantCriteria(
            hypotension_or_shock=_to_bool(fulm_in.get("hypotension_or_shock")),
            ileus=_to_bool(fulm_in.get("ileus")),
            toxic_megacolon=_to_bool(fulm_in.get("toxic_megacolon")),
            bowel_perforation_or_peritonitis=_to_bool(fulm_in.get("bowel_perforation_or_peritonitis")),
            icu_admission_for_cdi=_to_bool(fulm_in.get("icu_admission_for_cdi")),
        )
    else:
        fulm = FulminantCriteria(
            hypotension_or_shock=_to_bool(d.get("hypotension")) or _to_bool(d.get("shock")),
            ileus=_to_bool(d.get("ileus")),
            toxic_megacolon=_to_bool(d.get("toxic_megacolon")) or _to_bool(d.get("megacolon")),
            bowel_perforation_or_peritonitis=_to_bool(d.get("perforation")) or _to_bool(d.get("peritonitis")),
            icu_admission_for_cdi=_to_bool(d.get("icu")) or _to_bool(d.get("icu_admission")),
        )


    # Episode parsing
    rec_count = int(float(d.get("prior_recurrence_count", d.get("recurrences", 0))))
    ep_str = str(d.get("episode_type", "")).upper()
    if "MULT" in ep_str or rec_count >= 2:
        ep_type = EpisodeType.MULTIPLE_RECURRENCE
    elif "FIRST" in ep_str or "1" in ep_str or rec_count == 1:
        ep_type = EpisodeType.FIRST_RECURRENCE
    else:
        ep_type = EpisodeType.INITIAL

    age_val = d.get("age")
    age = int(float(age_val)) if age_val is not None and str(age_val).strip() != "" else None

    temp_val = d.get("body_temperature_c", d.get("temperature", d.get("temp")))
    temp = float(temp_val) if temp_val is not None and str(temp_val).strip() != "" else None

    alb_val = d.get("serum_albumin_g_dl", d.get("albumin", d.get("alb")))
    alb = float(alb_val) if alb_val is not None and str(alb_val).strip() != "" else None

    concom_abx = bool(d.get("concomitant_antibiotics", d.get("concomitant_abx", False)))
    prior_tx = d.get("prior_regimen")

    return CDiffPatientInput(
        wbc_count=wbc,
        serum_creatinine=scr,
        baseline_creatinine=base_scr_val,
        fulminant_criteria=fulm,
        episode_type=ep_type,
        prior_recurrence_count=rec_count,
        prior_regimen=prior_tx,
        age=age,
        body_temperature_c=temp,
        serum_albumin_g_dl=alb,
        concomitant_antibiotics=concom_abx,
    )
