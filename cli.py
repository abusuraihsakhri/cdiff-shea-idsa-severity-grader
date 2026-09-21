#!/usr/bin/env python3
"""
SHEA / IDSA C. Difficile Severity Grader CLI
============================================
Command line interface for C. difficile infection staging,
ATLAS treatment-response scoring, and antimicrobial stewardship guidance.

Usage:
    python cli.py grade --wbc 18500 --creatinine 1.8
    python cli.py grade --wbc 22000 --creatinine 2.4 --shock --ileus
    python cli.py atlas --age 74 --wbc 19000 --creatinine 2.0 --albumin 2.3 --abx
    python cli.py interactive
    python cli.py batch --input cdiff_patients.csv --output results.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from typing import Any, Dict, List, Optional

from cdiff_grader import (
    CDiffPatientInput,
    FulminantCriteria,
    CDISeverity,
    EpisodeType,
    grade_cdiff_severity,
    calculate_atlas_score,
)


def run_grade(args: argparse.Namespace) -> int:
    fulm = FulminantCriteria(
        hypotension_or_shock=args.shock,
        ileus=args.ileus,
        toxic_megacolon=args.megacolon,
        bowel_perforation_or_peritonitis=args.perforation,
        icu_admission_for_cdi=args.icu,
    )

    ep_type = EpisodeType.INITIAL
    if args.recurrences >= 2 or args.episode == "multiple":
        ep_type = EpisodeType.MULTIPLE_RECURRENCE
    elif args.recurrences == 1 or args.episode == "first_recurrence":
        ep_type = EpisodeType.FIRST_RECURRENCE

    inp = CDiffPatientInput(
        wbc_count=args.wbc,
        serum_creatinine=args.creatinine,
        baseline_creatinine=args.baseline_creatinine,
        fulminant_criteria=fulm,
        episode_type=ep_type,
        prior_recurrence_count=args.recurrences,
        prior_regimen=args.prior_regimen,
        age=args.age,
        body_temperature_c=args.temp,
        serum_albumin_g_dl=args.albumin,
        concomitant_antibiotics=args.abx,
    )

    res = grade_cdiff_severity(inp)

    if args.json:
        print(json.dumps(res.to_dict(), indent=2))
        return 0

    print("=" * 70)
    print("  SHEA / IDSA C. DIFFICILE SEVERITY & STEWARDSHIP ASSESSMENT")
    print("=" * 70)
    print(f"Severity Stage:      {res.severity.value}")
    print(f"Episode Category:    {res.episode_type.value}")
    print(f"WBC Count:           {res.wbc_cells_ul:.0f} cells/uL ({'ELEVATED >= 15k' if res.is_wbc_elevated else 'Normal/Low'})")
    print(f"Serum Creatinine:    {res.serum_creatinine_mg_dl:.2f} mg/dL ({'ELEVATED >= 1.5' if res.is_creatinine_elevated else 'Normal/Low'})")
    if res.fulminant_criteria_present:
        print(f"Fulminant Features:  {', '.join(res.fulminant_criteria_present)}")
    print("-" * 70)
    print(f"Clinical Rationale:  {res.severity_rationale}")

    if res.atlas_score:
        print("-" * 70)
        print(f"ATLAS Score:         {res.atlas_score.score}/10 ({res.atlas_score.score_band.value})")
        print(f"Estimated Cure Rate: {res.atlas_score.estimated_cure_rate_percentage:.1f}%")

    print("-" * 70)
    print("GUIDELINE-DIRECTED THERAPEUTIC REGIMEN (IDSA/SHEA 2021):")
    print(f"  [Preferred]   : {res.treatment.preferred_regimen}")
    if res.treatment.alternative_regimen:
        print(f"  [Alternative] : {res.treatment.alternative_regimen}")
    if res.treatment.surgical_consult_required:
        print("  [ALERT]       : *** URGENT SURGICAL CONSULTATION REQUIRED ***")

    print("\nAdjunctive & Stewardship Measures:")
    for adj in res.treatment.adjunctive_therapies:
        print(f"  * {adj}")

    print("\nInfection Control:")
    for ic in res.treatment.infection_control_measures:
        print(f"  * {ic}")
    print("=" * 70)
    return 0


def run_atlas(args: argparse.Namespace) -> int:
    inp = CDiffPatientInput(
        wbc_count=args.wbc,
        serum_creatinine=args.creatinine,
        age=args.age,
        body_temperature_c=args.temp,
        serum_albumin_g_dl=args.albumin,
        concomitant_antibiotics=args.abx,
    )
    res = calculate_atlas_score(inp)

    if args.json:
        print(json.dumps(res.to_dict(), indent=2))
        return 0

    print("=" * 65)
    print("  ATLAS C. DIFFICILE TREATMENT-RESPONSE SCORE (Miller et al., 2013)")
    print("=" * 65)
    print(f"Total ATLAS Score:   {res.score} / 10")
    print(f"Score Band:          {res.score_band.value}")
    print(f"Estimated Cure Rate: {res.estimated_cure_rate_percentage:.1f}%")
    print("-" * 65)
    print("Component Points Breakdown:")
    for k, v in res.component_breakdown.items():
        print(f"  - {k:<25}: {v} pts")
    print("=" * 65)
    return 0


def run_batch(args: argparse.Namespace) -> int:
    if not os.path.exists(args.input):
        print(f"Error: Input file '{args.input}' not found.", file=sys.stderr)
        return 1

    with open(args.input, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])

    out_fields = fieldnames + [
        "cdi_severity",
        "preferred_treatment",
        "atlas_score",
        "atlas_score_band",
        "atlas_estimated_cure_rate_pct",
    ]
    out_rows = []

    for r in rows:
        try:
            res = grade_cdiff_severity(r)
            row_dict = dict(r)
            row_dict["cdi_severity"] = res.severity.value
            row_dict["preferred_treatment"] = res.treatment.preferred_regimen
            row_dict["atlas_score"] = res.atlas_score.score if res.atlas_score else "N/A"
            row_dict["atlas_score_band"] = res.atlas_score.score_band.value if res.atlas_score else "N/A"
            row_dict["atlas_estimated_cure_rate_pct"] = (
                res.atlas_score.estimated_cure_rate_percentage if res.atlas_score else "N/A"
            )
            out_rows.append(row_dict)
        except Exception as e:
            row_dict = dict(r)
            row_dict["cdi_severity"] = f"ERROR: {e}"
            row_dict["preferred_treatment"] = ""
            row_dict["atlas_score"] = ""
            row_dict["atlas_score_band"] = ""
            row_dict["atlas_estimated_cure_rate_pct"] = ""
            out_rows.append(row_dict)

    with open(args.output, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=out_fields)
        writer.writeheader()
        writer.writerows(out_rows)

    print(f"Batch evaluated {len(out_rows)} records into '{args.output}'.")
    return 0


def run_interactive(args: argparse.Namespace) -> int:
    print("=" * 70)
    print("  SHEA / IDSA C. DIFFICILE SEVERITY WIZARD")
    print("=" * 70)

    def ask_float(prompt: str, default: float) -> float:
        val = input(f"{prompt} [{default}]: ").strip()
        try:
            return float(val) if val else default
        except ValueError:
            return default

    def ask_int(prompt: str, default: int) -> int:
        val = input(f"{prompt} [{default}]: ").strip()
        return int(val) if val.isdigit() else default

    def ask_bool(prompt: str) -> bool:
        val = input(f"{prompt} (y/N): ").strip().lower()
        return val in ["y", "yes", "true", "1"]

    wbc = ask_float("1. Patient WBC count (cells/uL, e.g. 16500 or 16.5)", 12000.0)
    scr = ask_float("2. Current Serum Creatinine (mg/dL)", 1.1)
    has_base = ask_bool("   Do you have a known baseline creatinine?")
    base_scr = ask_float("   Baseline Serum Creatinine (mg/dL)", 1.0) if has_base else None

    print("\n3. Critical Complications (Fulminant Criteria):")
    shock = ask_bool("   - Hypotension / Septic Shock (SBP < 90 or vasopressors)?")
    ileus = ask_bool("   - Paralytic ileus (absent bowel sounds / dilated loops)?")
    megacolon = ask_bool("   - Toxic megacolon (>6 cm colonic dilation)?")
    perforation = ask_bool("   - Bowel perforation or peritonitis?")
    icu = ask_bool("   - ICU admission for CDI?")

    print("\n4. Recurrence History:")
    recs = ask_int("   Number of prior CDI recurrences (0 for initial episode)", 0)
    prior_tx = None
    if recs > 0:
        prior_tx = input("   Prior treatment regimen (VANCOMYCIN / FIDAXOMICIN / METRONIDAZOLE): ").strip()

    print("\n5. ATLAS Score Parameters:")
    age = ask_int("   Patient Age (years)", 65)
    temp = None
    alb = ask_float("   Serum Albumin (g/dL, e.g. 3.2)", 3.2)
    abx = ask_bool("   Concomitant non-CDI systemic antibiotics ongoing?")

    fulm = FulminantCriteria(
        hypotension_or_shock=shock,
        ileus=ileus,
        toxic_megacolon=megacolon,
        bowel_perforation_or_peritonitis=perforation,
        icu_admission_for_cdi=icu,
    )

    ep_type = EpisodeType.MULTIPLE_RECURRENCE if recs >= 2 else (EpisodeType.FIRST_RECURRENCE if recs == 1 else EpisodeType.INITIAL)

    inp = CDiffPatientInput(
        wbc_count=wbc,
        serum_creatinine=scr,
        baseline_creatinine=base_scr,
        fulminant_criteria=fulm,
        episode_type=ep_type,
        prior_recurrence_count=recs,
        prior_regimen=prior_tx,
        age=age,
        body_temperature_c=temp,
        serum_albumin_g_dl=alb,
        concomitant_antibiotics=abx,
    )

    res = grade_cdiff_severity(inp)

    print("\n" + "=" * 70)
    print("  EVALUATION RESULT")
    print("=" * 70)
    print(f"Severity Stage:      {res.severity.value}")
    print(f"Rationale:           {res.severity_rationale}")
    if res.atlas_score:
        print(
            f"ATLAS Score:         {res.atlas_score.score}/10 "
            f"({res.atlas_score.score_band.value}, "
            f"estimated cure {res.atlas_score.estimated_cure_rate_percentage:.1f}%)"
        )
    print("-" * 70)
    print(f"Preferred Therapy:   {res.treatment.preferred_regimen}")
    if res.treatment.alternative_regimen:
        print(f"Alternative Therapy: {res.treatment.alternative_regimen}")
    if res.treatment.surgical_consult_required:
        print("ALERT:               *** SURGICAL EVALUATION REQUIRED ***")
    print("=" * 70)
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="SHEA/IDSA C. Difficile Severity Grader & ATLAS Score Calculator"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Grade subcommand
    g_p = subparsers.add_parser("grade", help="Grade CDI severity and generate treatment recommendations")
    g_p.add_argument("--wbc", type=float, default=12000.0, help="WBC count in cells/uL or x10^9/L")
    g_p.add_argument("--creatinine", "--scr", type=float, default=1.0, help="Current serum creatinine (mg/dL)")
    g_p.add_argument("--baseline-creatinine", type=float, help="Premorbid baseline serum creatinine (mg/dL)")
    g_p.add_argument("--shock", action="store_true", help="Hypotension / Septic shock")
    g_p.add_argument("--ileus", action="store_true", help="Paralytic ileus")
    g_p.add_argument("--megacolon", action="store_true", help="Toxic megacolon")
    g_p.add_argument("--perforation", action="store_true", help="Bowel perforation / peritonitis")
    g_p.add_argument("--icu", action="store_true", help="ICU admission for CDI")
    g_p.add_argument("--episode", choices=["initial", "first_recurrence", "multiple"], default="initial", help="Episode type")
    g_p.add_argument("--recurrences", type=int, default=0, help="Prior recurrence count")
    g_p.add_argument("--prior-regimen", help="Prior antibiotic regimen (e.g. VANCOMYCIN)")
    g_p.add_argument("--age", type=int, help="Patient age for ATLAS scoring")
    g_p.add_argument("--temp", type=float, help="Body temperature (C) for ATLAS scoring")
    g_p.add_argument("--albumin", type=float, help="Serum albumin (g/dL) for ATLAS scoring")
    g_p.add_argument("--abx", action="store_true", help="Concomitant non-CDI antibiotics")
    g_p.add_argument("--json", action="store_true", help="Output JSON format")

    # ATLAS subcommand
    a_p = subparsers.add_parser("atlas", help="Compute the ATLAS treatment-response score")
    a_p.add_argument("--age", type=int, required=True, help="Patient age")
    a_p.add_argument(
        "--temp",
        type=float,
        help="Deprecated compatibility option; temperature is not used by the ATLAS score",
    )
    a_p.add_argument("--wbc", type=float, required=True, help="WBC count (cells/uL)")
    a_p.add_argument(
        "--creatinine",
        "--scr",
        type=float,
        required=True,
        help="Serum creatinine (mg/dL)",
    )
    a_p.add_argument("--albumin", type=float, required=True, help="Serum albumin (g/dL)")
    a_p.add_argument("--abx", action="store_true", help="Concurrent non-CDI antibiotics")
    a_p.add_argument("--json", action="store_true", help="Output JSON format")

    # Batch subcommand
    b_p = subparsers.add_parser("batch", help="Batch grade cohort from CSV file")
    b_p.add_argument("--input", "-i", required=True, help="Input CSV file path")
    b_p.add_argument("--output", "-o", default="cdiff_results.csv", help="Output CSV file path")

    # Interactive subcommand
    subparsers.add_parser("interactive", help="Interactive staging wizard")

    args = parser.parse_args(argv)

    if args.command == "grade":
        return run_grade(args)
    elif args.command == "atlas":
        return run_atlas(args)
    elif args.command == "batch":
        return run_batch(args)
    elif args.command == "interactive":
        return run_interactive(args)
    else:
        if len(sys.argv) == 1:
            return run_interactive(args)
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
