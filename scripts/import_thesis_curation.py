"""Export the hand-curated values of the AeroViz-4D thesis repository into `curation/`.

Run once, from this repository's root:

    python scripts/import_thesis_curation.py /path/to/thesis

It writes three files. Every value keeps the id of the document it was read from and the page
or section (`locator`). Nothing else is copied: no verbatim quotes, no free-text notes, and no
value whose source is EUROCONTROL APD, BADA or EASA ANP (their terms forbid publication).

Values that this repository reads directly from a public file (FAA ACD, OpenAP, Poll-Schumann)
are NOT exported here; `build.py` reads them from `sources/`.

    curation/facts.csv          typecode, field, value, unit, source_id, locator
    curation/sources.csv        source_id, title, publisher, revision, url, retrieved, sha256, kind
    curation/substitutions.csv  typecode, substitute, basis
"""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

LB_TO_KG = 0.45359237

# Sources this repository reads itself, or must not publish. A curated value from one of them is
# skipped: the direct read supplies it (first group) or it may not appear at all (second group).
READ_DIRECTLY = ("faa_acd_2024_10", "pycontrails_ps_20250328", "openap_2_4")
FORBIDDEN_PREFIXES = ("eurocontrol", "bada", "anp")

# airframe_facts column -> (field, unit, source column, locator column)
FACT_COLUMNS = [
    ("wing_area_m2", "wing_area_m2", "m2", "wing_area_source", "wing_area_locator"),
    ("rated_takeoff_thrust_kN_each", "takeoff_thrust_kN_each", "kN", "thrust_source", "thrust_locator"),
    ("rated_takeoff_power_kW_each", "takeoff_power_kW_each", "kW", "power_source", "power_locator"),
    ("mtow_kg", "mtow_kg", "kg", "mtow_source", None),
    ("malw_kg", "mlw_kg", "kg", "malw_source", None),
    ("approach_speed_kt", "approach_speed_kt", "kt", "approach_speed_source", None),
]

# Files in the order they were written; a later file corrects an earlier one (the 2026-11-01
# batches carry two corrections, LJ55 thrust and HDJT MTOW).
FACT_FILES = [
    "airframe_facts.csv",
    "airframe_facts_batch1_20261101.csv",
    "airframe_facts_batch2_20261101.csv",
    "airframe_facts_batch3_20261101.csv",
    "airframe_facts_batch4_20261101.csv",
]
SOURCE_TABLES = [name.replace(".csv", "_sources.md") for name in FACT_FILES]


def skip_source(source_id: str) -> bool:
    return source_id in READ_DIRECTLY or source_id.startswith(FORBIDDEN_PREFIXES)


def source_kind(source_id: str, publisher: str) -> str:
    if source_id.startswith(("faa_", "nasa_")):
        return "us_government"
    if source_id.startswith("easa_"):
        return "easa"
    if source_id.startswith(("donald_", "gunston_")):
        return "book"
    return "manufacturer"


def read_md_sources(path: Path) -> dict[str, dict]:
    """Rows of the `| id | tier | title | publisher | revision / date | URL | local path | bytes | sha256 |` table."""
    out = {}
    header = None
    for line in path.read_text().splitlines():
        if not line.startswith("|"):
            header = None
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells[0] == "id":
            header = cells
            continue
        if header is None or set(cells[0]) <= {"-", ":"}:
            continue
        row = dict(zip(header, cells))
        sid = row["id"].strip("`")
        out[sid] = {
            "title": row["title"],
            "publisher": row["publisher"],
            "revision": row["revision / date"],
            "url": row["URL"],
            "retrieved": "",
            "sha256": row["sha256"].strip("`"),
        }
    return out


def main(thesis: Path) -> None:
    here = Path(__file__).resolve().parent.parent
    lit = thesis / "docs/literature/aircraft_performance"
    perf = json.loads((thesis / "aircraft/performance_index.json").read_text())
    speeds = json.loads((thesis / "aircraft/reference_speeds.json").read_text())

    # --- source metadata -------------------------------------------------------------------------
    meta: dict[str, dict] = {}
    for sid, s in {**perf["sources"], **speeds["sources"]}.items():
        meta[sid] = {
            "title": s["title"],
            "publisher": s["publisher"],
            "revision": s.get("revision") or s.get("document") or "",
            "url": s["url"],
            "retrieved": s.get("retrieved", ""),
            "sha256": s["sha256"],
        }
    for name in SOURCE_TABLES:
        for sid, s in read_md_sources(lit / name).items():
            meta.setdefault(sid, s)

    # --- facts -----------------------------------------------------------------------------------
    facts: dict[tuple[str, str], dict] = {}
    for name in FACT_FILES:
        for row in csv.DictReader(open(lit / name)):
            for col, field, unit, src_col, loc_col in FACT_COLUMNS:
                value, sid = row.get(col, ""), row.get(src_col, "")
                if not value or not sid or skip_source(sid):
                    continue
                facts[(row["typecode"], field)] = {
                    "typecode": row["typecode"], "field": field, "value": value, "unit": unit,
                    "source_id": sid, "locator": row.get(loc_col, "") if loc_col else "",
                }
            if row.get("engine_model") and (row.get("thrust_source") or row.get("power_source")):
                sid = row.get("thrust_source") or row.get("power_source")
                loc = row.get("thrust_locator") or row.get("power_locator") or ""
                if not skip_source(sid):
                    facts[(row["typecode"], "engine_model")] = {
                        "typecode": row["typecode"], "field": "engine_model", "value": row["engine_model"],
                        "unit": "", "source_id": sid, "locator": loc,
                    }

    # performance_index.json "own" entries: add what the fact files do not already hold.
    for t, v in perf["types"].items():
        if v["decision"] != "own":
            continue
        pairs = [("mtow", "mtow_kg", v["mtow_kg"], "kg"),
                 ("wing_area", "wing_area_m2", v["wing_area_m2"], "m2"),
                 ("thrust", "takeoff_thrust_kN_each", round(v["max_thrust_n_each"] / 1000.0, 4), "kN")]
        for key, field, value, unit in pairs:
            sid = v["sources"][key]
            if skip_source(sid) or (t, field) in facts:
                continue
            facts[(t, field)] = {"typecode": t, "field": field, "value": value, "unit": unit,
                                 "source_id": sid, "locator": ""}

    # reference_speeds.json: MLW and OEW read from a manufacturer or a TCDS.
    for t, v in speeds["types"].items():
        if not skip_source(v["malw_source"]):
            facts[(t, "mlw_kg")] = {"typecode": t, "field": "mlw_kg", "value": v["malw_kg"], "unit": "kg",
                                    "source_id": v["malw_source"], "locator": ""}
        if v.get("min_mass_kind") in ("OEW", "OWE") and not skip_source(v["min_mass_source"]):
            facts[(t, "oew_kg")] = {"typecode": t, "field": "oew_kg", "value": v["min_mass_kg"], "unit": "kg",
                                    "source_id": v["min_mass_source"], "locator": ""}

    rows = sorted(facts.values(), key=lambda r: (r["typecode"], r["field"]))
    used = sorted({r["source_id"] for r in rows})
    missing = [s for s in used if s not in meta]
    if missing:
        raise SystemExit(f"source ids without metadata: {missing}")

    out = here / "curation"
    out.mkdir(exist_ok=True)
    with open(out / "facts.csv", "w", newline="") as f:
        w = csv.DictWriter(f, ["typecode", "field", "value", "unit", "source_id", "locator"])
        w.writeheader()
        w.writerows(rows)
    with open(out / "sources.csv", "w", newline="") as f:
        w = csv.DictWriter(f, ["source_id", "title", "publisher", "revision", "url", "retrieved", "sha256", "kind"])
        w.writeheader()
        for sid in used:
            kind = source_kind(sid, meta[sid]["publisher"])
            row = {"source_id": sid, **meta[sid], "kind": kind}
            if kind == "book":
                # Cite a book by its bibliographic record only; the copy we read was a third-party upload.
                row["url"] = ""
                row["sha256"] = ""
            w.writerow(row)

    # --- substitutions ---------------------------------------------------------------------------
    subs = [(t, v["substitute"], re.sub(r"\s+", " ", v["basis"])) for t, v in perf["types"].items()
            if v["decision"] == "substitute"]
    with open(out / "substitutions.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["typecode", "substitute", "basis"])
        w.writerows(sorted(subs))

    print(f"facts: {len(rows)} values, {len({r['typecode'] for r in rows})} types, {len(used)} sources; "
          f"substitutions: {len(subs)}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
