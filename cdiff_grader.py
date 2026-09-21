#!/usr/bin/env python3
"""
SHEA / IDSA Clostridioides Difficile Infection (CDI) Severity Grader
===================================================================
A clinical decision support engine implementing the IDSA / SHEA 2017 & 2021
guidelines for CDI severity staging, ATLAS treatment-response scoring,
and guideline-based therapeutic regimen recommendations.

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


class AtlasScoreBand(str, Enum):
    """Descriptive ATLAS score bands; these are not validated mortality categories."""
    LOW = "LOW_SCORE"                   # 0-2
    INTERMEDIATE = "INTERMEDIATE_SCORE" # 3-5
    HIGH = "HIGH_SCORE"                 # 6-7
    VERY_HIGH = "VERY_HIGH_SCORE"       # 8-10


# Backwards-compatible import alias. The original repository exposed this name,
# but ATLAS was derived to predict treatment response, not mortality strata.
AtlasMortalityRisk = AtlasScoreBand


WBC_SEVERE_THRESHOLD = 15000.0        # cells/uL or 15.0 x 10^9/L
SCR_SEVERE_THRESHOLD = 1.5            # mg/dL


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

    def meets_idsa_fulminant_definition(self) -> bool:
        """Return True for the IDSA/SHEA defining fulminant features."""
        return (
            self.hypotension_or_shock
            or self.ileus
            or self.toxic_megacolon
        )

    def is_present(self) -> bool:
        """Return True when any recorded critical complication is present."""
        return (
            self.meets_idsa_fulminant_definition()
            or self.bowel_perforation_or_peritonitis
            or self.icu_admission_for_cdi
        )

    def positive_list(self) -> List[str]:
        """IDSA/SHEA fulminant defining features that are present."""
        pos = []
        if self.hypotension_or_shock:
            pos.append("Hypotension / Septic Shock")
        if self.ileus:
            pos.append("Paralytic Ileus")
        if self.toxic_megacolon:
            pos.append("Toxic Megacolon")
        return pos

    def additional_critical_complications(self) -> List[str]:
        """Recorded critical findings that are not defining fulminant criteria."""
        pos = []
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
        if self.prior_recurrence_count < 0:
            errors.append("Prior recurrence count cannot be negative.")
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
    """ATLAS treatment-response score result (Miller et al., 2013)."""
    score: int
    score_band: AtlasScoreBand
    estimated_cure_rate_percentage: float
    component_breakdown: Dict[str, int]

    @property
    def risk_tier(self) -> AtlasScoreBand:
        """Backwards-compatible alias for the descriptive score band."""
        return self.score_band

    @property
    def predicted_mortality_percentage(self) -> None:
        """ATLAS does not provide a validated mortality percentage."""
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": self.score,
            "score_band": self.score_band.value,
            "estimated_cure_rate_percentage": self.estimated_cure_rate_percentage,
            "component_breakdown": self.component_breakdown,
            # Backwards-compatible keys retained without asserting mortality risk.
            "risk_tier": self.score_band.value,
            "predicted_mortality_percentage": None,
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

    # Evaluate IDSA/SHEA severity criteria.
    # The 2017 guideline changed creatinine severity assessment from a
    # baseline-relative rule to the absolute serum creatinine threshold.
    wbc_elevated = norm_wbc > WBC_SEVERE_THRESHOLD
    creatinine_elevated = scr >= SCR_SEVERE_THRESHOLD

    fulminant_pos = inp.fulminant_criteria.positive_list()
    has_fulminant = inp.fulminant_criteria.meets_idsa_fulminant_definition()

    # Severity Tier Determination
    if has_fulminant:
        severity = CDISeverity.FULMINANT
        rationale = (
            "Fulminant CDI: IDSA/SHEA defining feature(s) present: "
            + ", ".join(fulminant_pos)
            + "."
        )
    elif wbc_elevated or creatinine_elevated:
        severity = CDISeverity.SEVERE
        reasons = []
        if wbc_elevated:
            reasons.append(
                f"WBC ({norm_wbc:.0f} cells/uL) > {WBC_SEVERE_THRESHOLD:.0f}"
            )
        if creatinine_elevated:
            reasons.append(
                f"SCr ({scr:.2f} mg/dL) >= {SCR_SEVERE_THRESHOLD} mg/dL"
            )
        rationale = f"Severe CDI: Laboratory criteria met ({'; '.join(reasons)})."
    else:
        severity = CDISeverity.NON_SEVERE
        rationale = (
            f"Non-Severe CDI: WBC ({norm_wbc:.0f} cells/uL) <= 15,000 and "
            f"SCr ({scr:.2f} mg/dL) < 1.5 mg/dL without IDSA/SHEA fulminant features."
        )

    extra_critical = inp.fulminant_criteria.additional_critical_complications()
    if extra_critical:
        rationale += (
            " Additional critical finding(s) recorded but not part of the "
            "IDSA/SHEA fulminant definition: "
            + ", ".join(extra_critical)
            + "."
        )

    # Determine episode classification
    if inp.prior_recurrence_count >= 2 or inp.episode_type == EpisodeType.MULTIPLE_RECURRENCE:
        ep_type = EpisodeType.MULTIPLE_RECURRENCE
    elif inp.prior_recurrence_count == 1 or inp.episode_type == EpisodeType.FIRST_RECURRENCE:
        ep_type = EpisodeType.FIRST_RECURRENCE
    else:
        ep_type = EpisodeType.INITIAL

    # Generate Guideline Treatment Recommendation
    treatment = _generate_treatment_plan(severity, ep_type, inp)

    # Calculate ATLAS only when ATLAS-specific inputs are supplied.
    # calculate_atlas_score validates that all required components are present.
    atlas_res = None
    if inp.age is not None or inp.serum_albumin_g_dl is not None:
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
    Compute the five-component ATLAS score from Miller et al. (2013).

    ATLAS uses age, systemic antibiotic treatment, leukocyte count, serum
    albumin, and serum creatinine. The original derivation correlated the
    0-10 score with clinical cure after CDI therapy; it did not define
    validated mortality-risk tiers.
    """
    errors = patient_input.validate()
    if errors:
        raise ValueError("Invalid CDI patient inputs: " + "; ".join(errors))

    missing = []
    if patient_input.age is None:
        missing.append("age")
    if patient_input.serum_albumin_g_dl is None:
        missing.append("serum albumin")
    if missing:
        raise ValueError(
            "ATLAS score requires " + " and ".join(missing) + "."
        )

    breakdown: Dict[str, int] = {}

    age = patient_input.age
    if age < 60:
        age_pts = 0
    elif age < 80:
        age_pts = 1
    else:
        age_pts = 2
    breakdown["age_score"] = age_pts

    # Treatment with non-CDI systemic antibiotics during CDI therapy.
    abx_pts = 2 if patient_input.concomitant_antibiotics else 0
    breakdown["systemic_antibiotics_score"] = abx_pts

    wbc = patient_input.normalized_wbc()
    if wbc < 16000:
        wbc_pts = 0
    elif wbc <= 25000:
        wbc_pts = 1
    else:
        wbc_pts = 2
    breakdown["leukocyte_score"] = wbc_pts

    alb = patient_input.serum_albumin_g_dl
    if alb > 3.5:
        alb_pts = 0
    elif alb >= 2.6:
        alb_pts = 1
    else:
        alb_pts = 2
    breakdown["albumin_score"] = alb_pts

    # Original thresholds were reported in micromol/L: <=120, 121-179, >=180.
    scr_umol_l = patient_input.serum_creatinine * 88.4
    if scr_umol_l <= 120:
        scr_pts = 0
    elif scr_umol_l < 180:
        scr_pts = 1
    else:
        scr_pts = 2
    breakdown["serum_creatinine_score"] = scr_pts

    total_score = sum(breakdown.values())

    if total_score <= 2:
        band = AtlasScoreBand.LOW
    elif total_score <= 5:
        band = AtlasScoreBand.INTERMEDIATE
    elif total_score <= 7:
        band = AtlasScoreBand.HIGH
    else:
        band = AtlasScoreBand.VERY_HIGH

    # Regression from the derivation cohort: predicted cure = 100 - 5.08*score.
    estimated_cure = round(max(0.0, 100.0 - (5.08 * total_score)), 1)

    return AtlasScoreResult(
        score=total_score,
        score_band=band,
        estimated_cure_rate_percentage=estimated_cure,
        component_breakdown=breakdown,
    )


def _generate_treatment_plan(
    severity: CDISeverity,
    episode_type: EpisodeType,
    inp: CDiffPatientInput
) -> TreatmentRecommendation:
    """Generate treatment guidance aligned with IDSA/SHEA 2017 and 2021."""
    adjunctive = [
        "Discontinue unnecessary inciting antimicrobial agents as soon as clinically feasible.",
        "Avoid anti-motility agents when ileus, toxic megacolon, or other contraindications are present.",
        "Use appropriate CDI transmission-based precautions and environmental sporicidal cleaning.",
    ]

    infection_control = [
        "Private room with dedicated toilet when feasible.",
        "Use gloves and gowns for room entry and patient care.",
        "Use soap-and-water handwashing preferentially after CDI care, especially during outbreaks.",
        "Use an EPA-registered sporicidal environmental disinfectant according to facility policy.",
    ]

    if severity == CDISeverity.FULMINANT:
        preferred = (
            "Vancomycin 500 mg PO/NG four times daily (QID) PLUS "
            "Metronidazole 500 mg IV every 8 hours (Q8H)."
        )
        alternative = (
            "If ileus is present, add Vancomycin 500 mg in approximately "
            "100 mL normal saline per rectum every 6 hours as a retention enema."
        )
        surgical = True
        notes = (
            "Fulminant CDI requires urgent multidisciplinary management. "
            "Early surgical evaluation is appropriate for patients who are severely ill "
            "or deteriorating; subtotal colectomy is the established operative approach "
            "when surgery is required."
        )
        if inp.fulminant_criteria.ileus:
            adjunctive.append(
                "ILEUS: Consider rectal vancomycin in addition to oral/NG vancomycin and IV metronidazole."
            )

    elif episode_type == EpisodeType.INITIAL:
        preferred = "Fidaxomicin 200 mg PO twice daily (BID) for 10 days."
        alternative = "Vancomycin 125 mg PO four times daily (QID) for 10 days."
        surgical = False
        notes = (
            "IDSA/SHEA 2021 suggests fidaxomicin over a standard course of vancomycin "
            "for an initial CDI episode; vancomycin remains an acceptable alternative. "
            "For non-severe CDI, metronidazole is an alternative only when fidaxomicin "
            "and vancomycin are unavailable."
        )

    elif episode_type == EpisodeType.FIRST_RECURRENCE:
        preferred = (
            "Fidaxomicin 200 mg PO twice daily for 10 days OR an extended-pulsed "
            "fidaxomicin regimen (200 mg twice daily for 5 days, then once every other "
            "day for 20 days)."
        )
        alternative = (
            "Vancomycin by mouth in a tapered and pulsed regimen; a standard 10-day "
            "vancomycin course is also an acceptable alternative for a first recurrence."
        )
        surgical = False
        adjunctive.append(
            "For a recurrent CDI episode within the last 6 months, consider bezlotoxumab "
            "10 mg/kg IV once during standard-of-care antibiotics when feasible; use caution "
            "in patients with congestive heart failure."
        )
        notes = (
            "The 2021 focused update suggests fidaxomicin (standard or extended-pulsed) "
            "over a standard vancomycin course for recurrent CDI. The recommendation does "
            "not make prior vancomycin versus fidaxomicin exposure a severity criterion."
        )

    else:  # MULTIPLE_RECURRENCE
        preferred = (
            "Fidaxomicin 200 mg PO twice daily for 10 days OR an extended-pulsed "
            "fidaxomicin regimen."
        )
        alternative = (
            "Vancomycin in a tapered and pulsed regimen, vancomycin followed by rifaximin, "
            "or fecal microbiota transplantation after multiple recurrences that have "
            "failed appropriate antibiotic treatments."
        )
        surgical = False
        adjunctive.append(
            "Consider fecal microbiota transplantation for multiple recurrences after "
            "failure of appropriate antibiotic treatment, following current safety guidance."
        )
        notes = (
            "IDSA/SHEA 2021 lists fidaxomicin, vancomycin-based strategies, and fecal "
            "microbiota transplantation as options for patients with multiple recurrences."
        )

    if inp.fulminant_criteria.bowel_perforation_or_peritonitis:
        surgical = True
        adjunctive.append(
            "BOWEL PERFORATION / PERITONITIS: Obtain urgent surgical evaluation."
        )
        notes += (
            " Bowel perforation/peritonitis is a surgical emergency but is not itself "
            "one of the three IDSA/SHEA defining fulminant criteria."
        )

    if inp.fulminant_criteria.icu_admission_for_cdi and severity != CDISeverity.FULMINANT:
        notes += (
            " ICU admission alone is not an IDSA/SHEA defining criterion for fulminant CDI; "
            "classify using hypotension/shock, ileus, or megacolon."
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
    """Parse a dictionary or CSV row into a validated CDiffPatientInput."""

    def _required_float(keys: Tuple[str, ...], label: str) -> float:
        for key in keys:
            value = d.get(key)
            if value is not None and str(value).strip() != "":
                try:
                    return float(value)
                except (TypeError, ValueError) as exc:
                    raise ValueError(f"{label} must be numeric.") from exc
        raise ValueError(f"{label} is required.")

    def _optional_float(keys: Tuple[str, ...]) -> Optional[float]:
        for key in keys:
            value = d.get(key)
            if value is not None and str(value).strip() != "":
                try:
                    return float(value)
                except (TypeError, ValueError) as exc:
                    raise ValueError(f"{key} must be numeric.") from exc
        return None

    def _to_bool(val: Any) -> bool:
        if isinstance(val, bool):
            return val
        if val is None:
            return False
        return str(val).strip().lower() in {"true", "1", "yes", "y", "t"}

    wbc = _required_float(("wbc_count", "wbc"), "WBC count")
    scr = _required_float(("serum_creatinine", "creatinine", "scr"), "Serum creatinine")
    base_scr_val = _optional_float(("baseline_creatinine", "baseline_scr"))

    fulm_in = d.get("fulminant_criteria")
    if isinstance(fulm_in, dict):
        fulm = FulminantCriteria(
            hypotension_or_shock=_to_bool(fulm_in.get("hypotension_or_shock")),
            ileus=_to_bool(fulm_in.get("ileus")),
            toxic_megacolon=_to_bool(fulm_in.get("toxic_megacolon")),
            bowel_perforation_or_peritonitis=_to_bool(
                fulm_in.get("bowel_perforation_or_peritonitis")
            ),
            icu_admission_for_cdi=_to_bool(fulm_in.get("icu_admission_for_cdi")),
        )
    else:
        fulm = FulminantCriteria(
            hypotension_or_shock=_to_bool(d.get("hypotension")) or _to_bool(d.get("shock")),
            ileus=_to_bool(d.get("ileus")),
            toxic_megacolon=_to_bool(d.get("toxic_megacolon"))
            or _to_bool(d.get("megacolon")),
            bowel_perforation_or_peritonitis=_to_bool(d.get("perforation"))
            or _to_bool(d.get("peritonitis")),
            icu_admission_for_cdi=_to_bool(d.get("icu"))
            or _to_bool(d.get("icu_admission")),
        )

    rec_raw = d.get("prior_recurrence_count", d.get("recurrences", 0))
    if rec_raw is None or str(rec_raw).strip() == "":
        rec_count = 0
    else:
        try:
            rec_count = int(float(rec_raw))
        except (TypeError, ValueError) as exc:
            raise ValueError("Prior recurrence count must be numeric.") from exc

    ep_str = str(d.get("episode_type", "")).strip().upper()
    if "MULT" in ep_str or rec_count >= 2:
        ep_type = EpisodeType.MULTIPLE_RECURRENCE
    elif "FIRST" in ep_str or rec_count == 1:
        ep_type = EpisodeType.FIRST_RECURRENCE
    else:
        ep_type = EpisodeType.INITIAL

    age_val = d.get("age")
    if age_val is not None and str(age_val).strip() != "":
        try:
            age = int(float(age_val))
        except (TypeError, ValueError) as exc:
            raise ValueError("Age must be numeric.") from exc
    else:
        age = None

    temp = _optional_float(("body_temperature_c", "temperature", "temp"))
    alb = _optional_float(("serum_albumin_g_dl", "albumin", "alb"))

    concom_abx = _to_bool(
        d.get("concomitant_antibiotics", d.get("concomitant_abx", False))
    )
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
