#!/usr/bin/env python3
"""
Unit Test Suite for SHEA / IDSA C. Difficile Severity Grader
============================================================
Comprehensive test coverage for CDI staging, IDSA/SHEA 2021 treatments,
ATLAS mortality score, recurrence management, and boundary validation.
"""

import json
import unittest
from cdiff_grader import (
    CDiffPatientInput,
    FulminantCriteria,
    CDISeverity,
    EpisodeType,
    AtlasMortalityRisk,
    grade_cdiff_severity,
    calculate_atlas_score,
    _parse_dict_to_patient_input,
)


class TestCDiffGrader(unittest.TestCase):

    # 1. Non-Severe CDI Staging
    def test_non_severe_cdi_normal_labs(self):
        inp = CDiffPatientInput(wbc_count=8500.0, serum_creatinine=0.9)
        res = grade_cdiff_severity(inp)
        self.assertEqual(res.severity, CDISeverity.NON_SEVERE)
        self.assertFalse(res.is_wbc_elevated)
        self.assertFalse(res.is_creatinine_elevated)
        self.assertIn("Fidaxomicin", res.treatment.preferred_regimen)

    def test_non_severe_boundary_wbc_and_scr(self):
        # Exactly 14,900 WBC and 1.4 mg/dL SCr
        inp = CDiffPatientInput(wbc_count=14900.0, serum_creatinine=1.4)
        res = grade_cdiff_severity(inp)
        self.assertEqual(res.severity, CDISeverity.NON_SEVERE)

    # 2. Severe CDI Staging (WBC criteria)
    def test_severe_cdi_elevated_wbc_only(self):
        inp = CDiffPatientInput(wbc_count=15500.0, serum_creatinine=1.0)
        res = grade_cdiff_severity(inp)
        self.assertEqual(res.severity, CDISeverity.SEVERE)
        self.assertTrue(res.is_wbc_elevated)
        self.assertFalse(res.is_creatinine_elevated)

    def test_severe_cdi_exact_wbc_threshold(self):
        # Exactly 15,000 cells/uL
        inp = CDiffPatientInput(wbc_count=15000.0, serum_creatinine=1.0)
        res = grade_cdiff_severity(inp)
        self.assertEqual(res.severity, CDISeverity.SEVERE)
        self.assertTrue(res.is_wbc_elevated)

    # 3. Severe CDI Staging (Creatinine criteria)
    def test_severe_cdi_elevated_creatinine_absolute(self):
        inp = CDiffPatientInput(wbc_count=11000.0, serum_creatinine=1.6)
        res = grade_cdiff_severity(inp)
        self.assertEqual(res.severity, CDISeverity.SEVERE)
        self.assertFalse(res.is_wbc_elevated)
        self.assertTrue(res.is_creatinine_elevated)

    def test_severe_cdi_exact_creatinine_threshold(self):
        # Exactly 1.5 mg/dL SCr
        inp = CDiffPatientInput(wbc_count=9000.0, serum_creatinine=1.5)
        res = grade_cdiff_severity(inp)
        self.assertEqual(res.severity, CDISeverity.SEVERE)
        self.assertTrue(res.is_creatinine_elevated)

    def test_severe_cdi_relative_to_baseline_creatinine(self):
        # Baseline 0.8 mg/dL, current 1.3 mg/dL (1.3 / 0.8 = 1.625x >= 1.5x baseline)
        inp = CDiffPatientInput(wbc_count=10000.0, serum_creatinine=1.3, baseline_creatinine=0.8)
        res = grade_cdiff_severity(inp)
        self.assertEqual(res.severity, CDISeverity.SEVERE)
        self.assertTrue(res.is_creatinine_elevated)

    def test_severe_cdi_both_wbc_and_scr_elevated(self):
        inp = CDiffPatientInput(wbc_count=22000.0, serum_creatinine=2.1)
        res = grade_cdiff_severity(inp)
        self.assertEqual(res.severity, CDISeverity.SEVERE)
        self.assertTrue(res.is_wbc_elevated)
        self.assertTrue(res.is_creatinine_elevated)

    # 4. Fulminant CDI Staging & Complications
    def test_fulminant_cdi_hypotension_shock(self):
        fulm = FulminantCriteria(hypotension_or_shock=True)
        inp = CDiffPatientInput(wbc_count=28000.0, serum_creatinine=2.4, fulminant_criteria=fulm)
        res = grade_cdiff_severity(inp)
        self.assertEqual(res.severity, CDISeverity.FULMINANT)
        self.assertTrue(res.treatment.surgical_consult_required)
        self.assertIn("Metronidazole 500 mg IV", res.treatment.preferred_regimen)

    def test_fulminant_cdi_ileus(self):
        fulm = FulminantCriteria(ileus=True)
        inp = CDiffPatientInput(wbc_count=18000.0, serum_creatinine=1.8, fulminant_criteria=fulm)
        res = grade_cdiff_severity(inp)
        self.assertEqual(res.severity, CDISeverity.FULMINANT)
        self.assertIn("rectal vancomycin enemas", " ".join(res.treatment.adjunctive_therapies))

    def test_fulminant_cdi_toxic_megacolon(self):
        fulm = FulminantCriteria(toxic_megacolon=True)
        inp = CDiffPatientInput(wbc_count=32000.0, serum_creatinine=3.0, fulminant_criteria=fulm)
        res = grade_cdiff_severity(inp)
        self.assertEqual(res.severity, CDISeverity.FULMINANT)
        self.assertIn("Toxic Megacolon", res.fulminant_criteria_present)

    def test_fulminant_cdi_bowel_perforation(self):
        fulm = FulminantCriteria(bowel_perforation_or_peritonitis=True)
        inp = CDiffPatientInput(wbc_count=12000.0, serum_creatinine=1.2, fulminant_criteria=fulm)
        res = grade_cdiff_severity(inp)
        self.assertEqual(res.severity, CDISeverity.FULMINANT)

    # 5. Treatment Regimens by Episode Category
    def test_treatment_initial_episode(self):
        inp = CDiffPatientInput(wbc_count=11000.0, serum_creatinine=1.1, episode_type=EpisodeType.INITIAL)
        res = grade_cdiff_severity(inp)
        self.assertIn("Fidaxomicin 200 mg PO twice daily", res.treatment.preferred_regimen)
        self.assertIn("Vancomycin 125 mg PO", res.treatment.alternative_regimen)

    def test_treatment_first_recurrence_after_vancomycin(self):
        inp = CDiffPatientInput(
            wbc_count=12000.0, serum_creatinine=1.0,
            episode_type=EpisodeType.FIRST_RECURRENCE,
            prior_recurrence_count=1,
            prior_regimen="VANCOMYCIN"
        )
        res = grade_cdiff_severity(inp)
        self.assertIn("Fidaxomicin", res.treatment.preferred_regimen)
        self.assertIn("Vancomycin tapered", res.treatment.alternative_regimen)
        self.assertTrue(any("Bezlotoxumab" in adj for adj in res.treatment.adjunctive_therapies))

    def test_treatment_multiple_recurrence_fmt_recommendation(self):
        inp = CDiffPatientInput(
            wbc_count=10000.0, serum_creatinine=0.9,
            episode_type=EpisodeType.MULTIPLE_RECURRENCE,
            prior_recurrence_count=2
        )
        res = grade_cdiff_severity(inp)
        self.assertIn("Fecal Microbiota Transplantation", res.treatment.preferred_regimen)

    # 6. ATLAS Score Validation
    def test_atlas_score_low_risk(self):
        # Age 45 (0), Temp 37.0 (0), WBC 10k (0), Albumin 3.8 (0), No Abx (0) -> Score 0
        inp = CDiffPatientInput(
            wbc_count=10000.0, serum_creatinine=1.0, age=45, body_temperature_c=37.0,
            serum_albumin_g_dl=3.8, concomitant_antibiotics=False
        )
        atlas = calculate_atlas_score(inp)
        self.assertEqual(atlas.score, 0)
        self.assertEqual(atlas.risk_tier, AtlasMortalityRisk.LOW)

    def test_atlas_score_intermediate_risk(self):
        # Age 70 (1), Temp 38.0 (1), WBC 18k (1), Albumin 3.0 (1), No Abx (0) -> Score 4
        inp = CDiffPatientInput(
            wbc_count=18000.0, serum_creatinine=1.0, age=70, body_temperature_c=38.0,
            serum_albumin_g_dl=3.0, concomitant_antibiotics=False
        )
        atlas = calculate_atlas_score(inp)
        self.assertEqual(atlas.score, 4)
        self.assertEqual(atlas.risk_tier, AtlasMortalityRisk.INTERMEDIATE)

    def test_atlas_score_high_risk(self):
        # Age 75 (1), Temp 38.8 (2), WBC 22k (1), Albumin 2.3 (2), No Abx (0) -> Score 6
        inp = CDiffPatientInput(
            wbc_count=22000.0, serum_creatinine=1.0, age=75, body_temperature_c=38.8,
            serum_albumin_g_dl=2.3, concomitant_antibiotics=False
        )
        atlas = calculate_atlas_score(inp)
        self.assertEqual(atlas.score, 6)
        self.assertEqual(atlas.risk_tier, AtlasMortalityRisk.HIGH)

    def test_atlas_score_maximum_very_high_risk(self):
        # Age 85 (2), Temp 39.0 (2), WBC 30k (2), Albumin 2.0 (2), Concomitant Abx (2) -> Score 10
        inp = CDiffPatientInput(
            wbc_count=30000.0, serum_creatinine=2.5, age=85, body_temperature_c=39.0,
            serum_albumin_g_dl=2.0, concomitant_antibiotics=True
        )
        atlas = calculate_atlas_score(inp)
        self.assertEqual(atlas.score, 10)
        self.assertEqual(atlas.risk_tier, AtlasMortalityRisk.VERY_HIGH)

    # 7. WBC Format Normalization
    def test_wbc_entered_as_thousands(self):
        # 16.5 x 10^9 / L -> 16,500
        inp = CDiffPatientInput(wbc_count=16.5, serum_creatinine=1.0)
        self.assertEqual(inp.normalized_wbc(), 16500.0)
        res = grade_cdiff_severity(inp)
        self.assertEqual(res.severity, CDISeverity.SEVERE)

    # 8. Input Validation & Error Handling
    def test_negative_wbc_raises_error(self):
        inp = CDiffPatientInput(wbc_count=-5000.0, serum_creatinine=1.0)
        with self.assertRaises(ValueError):
            grade_cdiff_severity(inp)

    def test_negative_creatinine_raises_error(self):
        inp = CDiffPatientInput(wbc_count=10000.0, serum_creatinine=-1.5)
        with self.assertRaises(ValueError):
            grade_cdiff_severity(inp)

    def test_invalid_temperature_raises_error(self):
        inp = CDiffPatientInput(wbc_count=10000.0, serum_creatinine=1.0, body_temperature_c=55.0)
        with self.assertRaises(ValueError):
            grade_cdiff_severity(inp)

    def test_invalid_albumin_raises_error(self):
        inp = CDiffPatientInput(wbc_count=10000.0, serum_creatinine=1.0, serum_albumin_g_dl=9.5)
        with self.assertRaises(ValueError):
            grade_cdiff_severity(inp)

    # 9. Dictionary Parsing & JSON Serialization
    def test_parse_dict_to_input(self):
        d = {
            "wbc": 17500,
            "creatinine": 1.9,
            "shock": True,
            "recurrences": 1,
            "age": 72,
        }
        inp = _parse_dict_to_patient_input(d)
        self.assertEqual(inp.wbc_count, 17500.0)
        self.assertEqual(inp.serum_creatinine, 1.9)
        self.assertTrue(inp.fulminant_criteria.hypotension_or_shock)
        self.assertEqual(inp.episode_type, EpisodeType.FIRST_RECURRENCE)

    def test_json_serialization(self):
        inp = CDiffPatientInput(wbc_count=18000.0, serum_creatinine=1.8, age=68, body_temperature_c=38.4)
        res = grade_cdiff_severity(inp)
        d = res.to_dict()
        self.assertIn("severity", d)
        self.assertIn("treatment", d)
        self.assertIn("atlas_score", d)
        json_str = json.dumps(d)
        self.assertIn("SEVERE", json_str)


if __name__ == "__main__":
    unittest.main()
