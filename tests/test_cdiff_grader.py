#!/usr/bin/env python3
"""Tests for the CDI severity grader and ATLAS score implementation."""

import json
import unittest

from cdiff_grader import (
    AtlasScoreBand,
    CDISeverity,
    CDiffPatientInput,
    EpisodeType,
    FulminantCriteria,
    _parse_dict_to_patient_input,
    calculate_atlas_score,
    grade_cdiff_severity,
)


class TestCDiffSeverity(unittest.TestCase):
    def test_non_severe_normal_labs(self):
        res = grade_cdiff_severity(
            CDiffPatientInput(wbc_count=8500, serum_creatinine=0.9)
        )
        self.assertEqual(res.severity, CDISeverity.NON_SEVERE)

    def test_wbc_15000_is_non_severe_boundary(self):
        res = grade_cdiff_severity(
            CDiffPatientInput(wbc_count=15000, serum_creatinine=1.0)
        )
        self.assertEqual(res.severity, CDISeverity.NON_SEVERE)
        self.assertFalse(res.is_wbc_elevated)

    def test_wbc_above_15000_is_severe(self):
        res = grade_cdiff_severity(
            CDiffPatientInput(wbc_count=15001, serum_creatinine=1.0)
        )
        self.assertEqual(res.severity, CDISeverity.SEVERE)
        self.assertTrue(res.is_wbc_elevated)

    def test_creatinine_1_5_is_severe(self):
        res = grade_cdiff_severity(
            CDiffPatientInput(wbc_count=9000, serum_creatinine=1.5)
        )
        self.assertEqual(res.severity, CDISeverity.SEVERE)
        self.assertTrue(res.is_creatinine_elevated)

    def test_baseline_relative_rise_alone_does_not_make_severe(self):
        res = grade_cdiff_severity(
            CDiffPatientInput(
                wbc_count=10000,
                serum_creatinine=1.3,
                baseline_creatinine=0.8,
            )
        )
        self.assertEqual(res.severity, CDISeverity.NON_SEVERE)
        self.assertFalse(res.is_creatinine_elevated)

    def test_wbc_thousands_format_normalization(self):
        inp = CDiffPatientInput(wbc_count=16.5, serum_creatinine=1.0)
        self.assertEqual(inp.normalized_wbc(), 16500)
        self.assertEqual(grade_cdiff_severity(inp).severity, CDISeverity.SEVERE)

    def test_hypotension_meets_fulminant_definition(self):
        res = grade_cdiff_severity(
            CDiffPatientInput(
                wbc_count=12000,
                serum_creatinine=1.0,
                fulminant_criteria=FulminantCriteria(
                    hypotension_or_shock=True
                ),
            )
        )
        self.assertEqual(res.severity, CDISeverity.FULMINANT)
        self.assertTrue(res.treatment.surgical_consult_required)

    def test_ileus_meets_fulminant_definition_and_adds_rectal_vancomycin(self):
        res = grade_cdiff_severity(
            CDiffPatientInput(
                wbc_count=12000,
                serum_creatinine=1.0,
                fulminant_criteria=FulminantCriteria(ileus=True),
            )
        )
        self.assertEqual(res.severity, CDISeverity.FULMINANT)
        self.assertTrue(
            any(
                "rectal vancomycin" in item.lower()
                for item in res.treatment.adjunctive_therapies
            )
        )

    def test_toxic_megacolon_meets_fulminant_definition(self):
        res = grade_cdiff_severity(
            CDiffPatientInput(
                wbc_count=12000,
                serum_creatinine=1.0,
                fulminant_criteria=FulminantCriteria(toxic_megacolon=True),
            )
        )
        self.assertEqual(res.severity, CDISeverity.FULMINANT)

    def test_perforation_alone_is_not_relabelled_fulminant(self):
        res = grade_cdiff_severity(
            CDiffPatientInput(
                wbc_count=12000,
                serum_creatinine=1.0,
                fulminant_criteria=FulminantCriteria(
                    bowel_perforation_or_peritonitis=True
                ),
            )
        )
        self.assertEqual(res.severity, CDISeverity.NON_SEVERE)
        self.assertTrue(res.treatment.surgical_consult_required)
        self.assertIn("not part of the IDSA/SHEA fulminant definition", res.severity_rationale)

    def test_icu_admission_alone_is_not_fulminant(self):
        res = grade_cdiff_severity(
            CDiffPatientInput(
                wbc_count=12000,
                serum_creatinine=1.0,
                fulminant_criteria=FulminantCriteria(
                    icu_admission_for_cdi=True
                ),
            )
        )
        self.assertEqual(res.severity, CDISeverity.NON_SEVERE)


class TestTreatmentRecommendations(unittest.TestCase):
    def test_initial_episode_fidaxomicin_preferred(self):
        res = grade_cdiff_severity(
            CDiffPatientInput(
                wbc_count=11000,
                serum_creatinine=1.1,
                episode_type=EpisodeType.INITIAL,
            )
        )
        self.assertIn("Fidaxomicin 200 mg", res.treatment.preferred_regimen)
        self.assertIn("Vancomycin 125 mg", res.treatment.alternative_regimen)

    def test_first_recurrence_fidaxomicin_preferred(self):
        res = grade_cdiff_severity(
            CDiffPatientInput(
                wbc_count=11000,
                serum_creatinine=1.1,
                episode_type=EpisodeType.FIRST_RECURRENCE,
                prior_recurrence_count=1,
                prior_regimen="VANCOMYCIN",
            )
        )
        self.assertIn("Fidaxomicin", res.treatment.preferred_regimen)
        self.assertIn("tapered and pulsed", res.treatment.alternative_regimen)
        self.assertTrue(
            any(
                "bezlotoxumab" in item.lower()
                for item in res.treatment.adjunctive_therapies
            )
        )

    def test_multiple_recurrence_includes_fmt_as_option_after_failures(self):
        res = grade_cdiff_severity(
            CDiffPatientInput(
                wbc_count=11000,
                serum_creatinine=1.1,
                episode_type=EpisodeType.MULTIPLE_RECURRENCE,
                prior_recurrence_count=2,
            )
        )
        self.assertIn("Fidaxomicin", res.treatment.preferred_regimen)
        self.assertIn(
            "fecal microbiota transplantation",
            res.treatment.alternative_regimen.lower(),
        )


class TestAtlasScore(unittest.TestCase):
    def test_low_score_zero(self):
        res = calculate_atlas_score(
            CDiffPatientInput(
                wbc_count=10000,
                serum_creatinine=1.0,
                age=45,
                serum_albumin_g_dl=3.8,
                concomitant_antibiotics=False,
            )
        )
        self.assertEqual(res.score, 0)
        self.assertEqual(res.score_band, AtlasScoreBand.LOW)
        self.assertEqual(res.estimated_cure_rate_percentage, 100.0)

    def test_intermediate_score_three(self):
        res = calculate_atlas_score(
            CDiffPatientInput(
                wbc_count=18000,
                serum_creatinine=1.0,
                age=70,
                serum_albumin_g_dl=3.0,
                concomitant_antibiotics=False,
            )
        )
        self.assertEqual(res.score, 3)
        self.assertEqual(res.score_band, AtlasScoreBand.INTERMEDIATE)

    def test_high_score_six(self):
        res = calculate_atlas_score(
            CDiffPatientInput(
                wbc_count=26000,
                serum_creatinine=1.0,
                age=85,
                serum_albumin_g_dl=2.5,
                concomitant_antibiotics=False,
            )
        )
        self.assertEqual(res.score, 6)
        self.assertEqual(res.score_band, AtlasScoreBand.HIGH)

    def test_max_score_ten_and_cure_equation(self):
        res = calculate_atlas_score(
            CDiffPatientInput(
                wbc_count=30000,
                serum_creatinine=2.5,
                age=85,
                serum_albumin_g_dl=2.0,
                concomitant_antibiotics=True,
            )
        )
        self.assertEqual(res.score, 10)
        self.assertEqual(res.score_band, AtlasScoreBand.VERY_HIGH)
        self.assertEqual(res.estimated_cure_rate_percentage, 49.2)
        self.assertIsNone(res.predicted_mortality_percentage)

    def test_creatinine_component_boundaries(self):
        base = dict(
            wbc_count=10000,
            age=45,
            serum_albumin_g_dl=3.8,
            concomitant_antibiotics=False,
        )
        low = calculate_atlas_score(
            CDiffPatientInput(serum_creatinine=120 / 88.4, **base)
        )
        mid = calculate_atlas_score(
            CDiffPatientInput(serum_creatinine=121 / 88.4, **base)
        )
        high = calculate_atlas_score(
            CDiffPatientInput(serum_creatinine=180 / 88.4, **base)
        )
        self.assertEqual(low.component_breakdown["serum_creatinine_score"], 0)
        self.assertEqual(mid.component_breakdown["serum_creatinine_score"], 1)
        self.assertEqual(high.component_breakdown["serum_creatinine_score"], 2)

    def test_temperature_is_not_an_atlas_component(self):
        common = dict(
            wbc_count=18000,
            serum_creatinine=1.7,
            age=70,
            serum_albumin_g_dl=3.0,
            concomitant_antibiotics=False,
        )
        low_temp = calculate_atlas_score(
            CDiffPatientInput(body_temperature_c=36.0, **common)
        )
        high_temp = calculate_atlas_score(
            CDiffPatientInput(body_temperature_c=40.0, **common)
        )
        self.assertEqual(low_temp.score, high_temp.score)
        self.assertNotIn("temperature_score", low_temp.component_breakdown)

    def test_missing_age_rejected(self):
        with self.assertRaisesRegex(ValueError, "age"):
            calculate_atlas_score(
                CDiffPatientInput(
                    wbc_count=10000,
                    serum_creatinine=1.0,
                    serum_albumin_g_dl=3.8,
                )
            )

    def test_missing_albumin_rejected(self):
        with self.assertRaisesRegex(ValueError, "serum albumin"):
            calculate_atlas_score(
                CDiffPatientInput(
                    wbc_count=10000,
                    serum_creatinine=1.0,
                    age=45,
                )
            )


class TestValidationAndParsing(unittest.TestCase):
    def test_negative_wbc_rejected(self):
        with self.assertRaises(ValueError):
            grade_cdiff_severity(
                CDiffPatientInput(wbc_count=-1, serum_creatinine=1.0)
            )

    def test_negative_creatinine_rejected(self):
        with self.assertRaises(ValueError):
            grade_cdiff_severity(
                CDiffPatientInput(wbc_count=10000, serum_creatinine=-1)
            )

    def test_invalid_temperature_rejected(self):
        with self.assertRaises(ValueError):
            grade_cdiff_severity(
                CDiffPatientInput(
                    wbc_count=10000,
                    serum_creatinine=1.0,
                    body_temperature_c=55,
                )
            )

    def test_invalid_albumin_rejected(self):
        with self.assertRaises(ValueError):
            grade_cdiff_severity(
                CDiffPatientInput(
                    wbc_count=10000,
                    serum_creatinine=1.0,
                    serum_albumin_g_dl=9.5,
                )
            )

    def test_negative_recurrence_count_rejected(self):
        with self.assertRaises(ValueError):
            grade_cdiff_severity(
                CDiffPatientInput(
                    wbc_count=10000,
                    serum_creatinine=1.0,
                    prior_recurrence_count=-1,
                )
            )

    def test_csv_boolean_zero_is_false(self):
        inp = _parse_dict_to_patient_input(
            {
                "wbc": "10000",
                "creatinine": "1.0",
                "age": "45",
                "albumin": "3.8",
                "concomitant_abx": "0",
            }
        )
        self.assertFalse(inp.concomitant_antibiotics)

    def test_csv_boolean_one_is_true(self):
        inp = _parse_dict_to_patient_input(
            {
                "wbc": "10000",
                "creatinine": "1.0",
                "age": "45",
                "albumin": "3.8",
                "concomitant_abx": "1",
            }
        )
        self.assertTrue(inp.concomitant_antibiotics)

    def test_missing_wbc_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "WBC count is required"):
            _parse_dict_to_patient_input({"creatinine": "1.0"})

    def test_missing_creatinine_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Serum creatinine is required"):
            _parse_dict_to_patient_input({"wbc": "10000"})

    def test_json_serialization_reports_atlas_without_mortality_claim(self):
        result = grade_cdiff_severity(
            {
                "wbc": 18000,
                "creatinine": 1.8,
                "age": 68,
                "albumin": 3.0,
            }
        )
        payload = result.to_dict()
        self.assertIn("score_band", payload["atlas_score"])
        self.assertIn("estimated_cure_rate_percentage", payload["atlas_score"])
        self.assertIsNone(payload["atlas_score"]["predicted_mortality_percentage"])
        self.assertIn("SEVERE", json.dumps(payload))


if __name__ == "__main__":
    unittest.main()
