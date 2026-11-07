"""Build `data/` from `sources/` (public files) and `curation/` (hand-curated values).

    python scripts/build.py

Outputs (all CSV, UTF-8):
    data/parameters.csv     long table: one row per (type, field, source)
    data/recommended.csv    wide table: one value per (type, field), chosen by FIELD_PRIORITY
    data/sources.csv        every source_id used, with licence
    data/substitutions.csv  "type X uses type Y's parameters" statements from OpenAP, Poll-Schumann
                            and the thesis analysis
    data/fields.csv         field dictionary
    docs/data.json          the same data for the static page (GitHub Pages serves docs/)
    docs/downloads/*.csv    copies of data/*.csv, so the page can link them
"""

from __future__ import annotations

import csv
import glob
import hashlib
import json
import math
import shutil
from collections import defaultdict
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "sources"
OUT = ROOT / "data"

LB_TO_KG = 0.45359237
FT_TO_M = 0.3048
KT_TO_MS = 1852.0 / 3600.0
G0 = 9.80665          # m/s^2
RHO0 = 1.225          # kg/m^3, ISA sea level
CLMAX_FACTORS = {"cl_max_landing_f123": 1.23, "cl_max_landing_f130": 1.3}

ACD_FILE = SRC / "faa_acd/FAA-Aircraft-Characteristics-Database-2024-10.xlsx"
PS_FILE = SRC / "poll_schumann/ps-aircraft-params-20250328.csv"
PS_SYN_FILE = SRC / "poll_schumann/ps-synonym-list-20250328.csv"

ACD, OPENAP, PS, DERIVED = "faa_acd_2024_10", "openap_2_6_2", "poll_schumann_20250328", "this_repository"

FIXED_SOURCES = {
    ACD: {
        "title": "Aircraft Characteristics Database", "publisher": "FAA Office of Airports",
        "revision": "October 2024 (page last updated 2025-01-07)",
        "url": "https://www.faa.gov/airports/engineering/aircraft_char_database/aircraft_data",
        "retrieved": "2026-09-07", "kind": "us_government", "file": ACD_FILE,
    },
    OPENAP: {
        "title": "OpenAP aircraft performance model, data directory (aircraft/, dragpolar/, engine/)",
        "publisher": "Junzi Sun, TU Delft (github.com/junzis/openap)",
        "revision": "2.6.2 (PyPI wheel openap-2.6.2-py3-none-any.whl, sha256 c4a79325...a508a295)",
        "url": "https://pypi.org/project/openap/2.6.2/",
        "retrieved": "2026-09-23", "kind": "gpl3", "file": None,
    },
    PS: {
        "title": "Poll-Schumann aircraft parameters, ps-aircraft-params-20250328.csv",
        "publisher": "pycontrails (Contrails.org / Breakthrough Energy Foundation)",
        "revision": "pycontrails 0.63.5, parameter file dated 2025-03-28",
        "url": "https://github.com/contrailcirrus/pycontrails/blob/v0.63.5/pycontrails/models/ps_model/static/ps-aircraft-params-20250328.csv",
        "retrieved": "2026-09-23", "kind": "apache2", "file": PS_FILE,
    },
    DERIVED: {
        "title": "Computed by this repository (scripts/build.py)", "publisher": "this repository",
        "revision": "", "url": "", "retrieved": "", "kind": "derived", "file": None,
    },
}

LICENCE = {
    "us_government": "US federal government work (17 U.S.C. 105)",
    "easa": "EASA: reproduction authorised, provided the source is acknowledged",
    "manufacturer": "manufacturer document (copyrighted); only the factual value and its page are used",
    "book": "copyrighted book; only the single factual value is cited",
    "gpl3": "GPL-3.0 (openap/data/LICENSE)",
    "apache2": "Apache-2.0 (sources/poll_schumann/LICENSE, NOTICE)",
    "derived": "GPL-3.0 (this repository)",
}

# field -> (unit, description, group, recommended?)
FIELDS = {
    "manufacturer":            ("", "Manufacturer", "identity", True),
    "model":                   ("", "Model name", "identity", True),
    "aircraft_class":          ("", "Fixed-wing / Amphibian / Tiltrotor (FAA ACD)", "identity", True),
    "propulsion_class":        ("", "Jet / Turboprop / Piston / Turboshaft (FAA ACD)", "identity", True),
    "mtow_kg":                 ("kg", "Maximum take-off weight", "mass", True),
    "mlw_kg":                  ("kg", "Maximum (allowable) landing weight", "mass", True),
    "oew_kg":                  ("kg", "Operating empty weight", "mass", True),
    "wing_area_m2":            ("m2", "Wing reference area S", "geometry", True),
    "wing_span_m":             ("m", "Wing span without winglets / sharklets", "geometry", True),
    "wing_span_winglets_m":    ("m", "Wing span with winglets / sharklets", "geometry", True),
    "engine_mount":            ("", "Engine mount (wing / rear)", "geometry", True),
    "cd0":                     ("", "Zero-lift drag coefficient, clean", "aero_clean", True),
    "k":                       ("", "Induced drag factor, clean", "aero_clean", True),
    "oswald_e":                ("", "Oswald efficiency factor, clean", "aero_clean", True),
    "cd0_gear":                ("", "Landing gear drag increment", "aero_landing", True),
    "flap_cf_c":               ("", "Flap chord ratio c_f/c", "aero_landing", True),
    "flap_sf_s":               ("", "Flap area ratio S_f/S", "aero_landing", True),
    "flap_lambda_f":           ("", "Flap drag factor lambda_f", "aero_landing", True),
    "flap_angles_deg":         ("deg", "Flap deflection per setting (not yet collected)", "aero_landing", True),
    "cl_max_landing_f123":     ("", "C_L,max landing, from V_app with V_s = V_app/1.23", "lift", True),
    "cl_max_landing_f130":     ("", "C_L,max landing, from V_app with V_s = V_app/1.3", "lift", True),
    "n_engines":               ("", "Number of engines", "propulsion", True),
    "engine_model":            ("", "Engine model", "propulsion", True),
    "takeoff_thrust_kN_each":  ("kN", "Rated static take-off thrust per engine, sea level", "propulsion", True),
    "takeoff_power_kW_each":   ("kW", "Rated take-off power per engine (propeller aircraft)", "propulsion", True),
    "bpr":                     ("", "Bypass ratio", "propulsion", True),
    "vmo_kt":                  ("kt", "Maximum operating speed", "speed", True),
    "mmo":                     ("", "Maximum operating Mach number", "speed", True),
    "vfe_kt":                  ("kt", "Maximum flap extended speed per setting (not yet collected)", "speed", True),
    "vle_kt":                  ("kt", "Maximum landing gear extended speed (not yet collected)", "speed", True),
    "vlo_kt":                  ("kt", "Maximum landing gear operating speed (not yet collected)", "speed", True),
    "approach_speed_kt":       ("kt", "Approach speed at MLW, IAS (FAA ACD)", "speed", True),
    "approach_speed_min_kt":   ("kt", "Approach speed, minimum of the FAA range", "speed", True),
    "approach_speed_max_kt":   ("kt", "Approach speed, maximum of the FAA range", "speed", True),
    "ps_psi0":                 ("", "Poll-Schumann zero-lift drag factor psi_0 (C_D0 = C_f(Re) psi_0)", "ps_native", False),
    "ps_delta2":               ("", "Poll-Schumann lift-dependent drag parameter delta_2", "ps_native", False),
    "ps_cos_sweep":            ("", "Poll-Schumann cosine of wing sweep", "ps_native", False),
}

CURATED = "curated"  # placeholder in FIELD_PRIORITY: any source from curation/sources.csv
FIELD_PRIORITY = {
    "manufacturer": [ACD, OPENAP, PS],
    "model": [ACD, OPENAP, PS],
    "aircraft_class": [ACD],
    "propulsion_class": [ACD],
    "mlw_kg": [CURATED, ACD, OPENAP, PS],
    "mtow_kg": [CURATED, ACD, OPENAP, PS],
    "oew_kg": [CURATED, OPENAP, PS],
    "wing_area_m2": [CURATED, OPENAP, PS],
    "wing_span_m": [ACD, OPENAP, PS],
    "wing_span_winglets_m": [ACD],
    "engine_mount": [OPENAP],
    "cd0": [OPENAP], "k": [OPENAP], "oswald_e": [OPENAP], "cd0_gear": [OPENAP],
    "flap_cf_c": [OPENAP], "flap_sf_s": [OPENAP], "flap_lambda_f": [OPENAP],
    "flap_angles_deg": [], "vfe_kt": [], "vle_kt": [], "vlo_kt": [],
    "cl_max_landing_f123": [DERIVED], "cl_max_landing_f130": [DERIVED],
    "n_engines": [ACD, CURATED, OPENAP, PS],
    "engine_model": [CURATED, OPENAP],
    "takeoff_thrust_kN_each": [CURATED, OPENAP, PS],
    "takeoff_power_kW_each": [CURATED],
    "bpr": [OPENAP, PS],
    "vmo_kt": [OPENAP],
    "mmo": [OPENAP, PS],
    "approach_speed_kt": [ACD], "approach_speed_min_kt": [ACD], "approach_speed_max_kt": [ACD],
}
assert set(FIELD_PRIORITY) == {f for f, v in FIELDS.items() if v[3]}


class Table:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    def add(self, typecode, field, value, source_id, locator="", derived=False, note=""):
        if value is None or (isinstance(value, float) and math.isnan(value)) or value == "":
            return
        if field not in FIELDS:
            raise KeyError(field)
        if isinstance(value, float):
            value = float(f"{value:.6g}")
        self.rows.append({
            "typecode": typecode.upper(), "field": field, "value": value, "unit": FIELDS[field][0],
            "source_id": source_id, "locator": locator, "derived": "yes" if derived else "no", "note": note,
        })


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --- FAA ACD -----------------------------------------------------------------------------------
def read_acd(t: Table) -> None:
    df = pd.read_excel(ACD_FILE, sheet_name="ACD_Data")
    if df.ICAO_Code.isna().any() or df.ICAO_Code.duplicated().any():
        raise SystemExit("FAA ACD: ICAO_Code must be present and unique")
    for i, r in df.iterrows():
        tc, loc = r.ICAO_Code.strip(), f"sheet ACD_Data, row {i + 2}"
        t.add(tc, "manufacturer", str(r.Manufacturer).strip(), ACD, loc)
        t.add(tc, "model", str(r.Model_FAA).strip(), ACD, loc)
        t.add(tc, "aircraft_class", str(r.Class).strip(), ACD, loc)
        t.add(tc, "propulsion_class", str(r.Physical_Class_Engine).strip(), ACD, loc)
        t.add(tc, "n_engines", int(r.Num_Engines), ACD, loc)
        t.add(tc, "mtow_kg", round(r.MTOW_lb * LB_TO_KG), ACD, loc, note="MTOW_lb x 0.45359237")
        if not math.isnan(r.MALW_lb):
            t.add(tc, "mlw_kg", round(r.MALW_lb * LB_TO_KG), ACD, loc, note="MALW_lb x 0.45359237")
        t.add(tc, "wing_span_m", round(r.Wingspan_ft_without_winglets_sharklets * FT_TO_M, 2), ACD, loc)
        t.add(tc, "wing_span_winglets_m", round(r.Wingspan_ft_with_winglets_sharklets * FT_TO_M, 2), ACD, loc)
        t.add(tc, "approach_speed_kt", r.Approach_Speed_knot, ACD, loc)
        t.add(tc, "approach_speed_min_kt", r.Approach_Speed_minimum_knot, ACD, loc)
        t.add(tc, "approach_speed_max_kt", r.Approach_Speed_maximum_knot, ACD, loc)


# --- OpenAP ------------------------------------------------------------------------------------
def read_openap(t: Table, subs: list[dict]) -> list[str]:
    engines = pd.read_csv(SRC / "openap/engine/engines.csv").set_index("name")
    unmatched = []
    for path in sorted(glob.glob(str(SRC / "openap/aircraft/*.yml"))):
        d = yaml.safe_load(open(path))
        tc, loc = Path(path).stem.upper(), f"aircraft/{Path(path).name}"
        t.add(tc, "model", d["aircraft"], OPENAP, loc)
        for f, k in [("mtow_kg", "mtow"), ("mlw_kg", "mlw"), ("oew_kg", "oew"), ("vmo_kt", "vmo"), ("mmo", "mmo")]:
            t.add(tc, f, d.get(k), OPENAP, loc)
        t.add(tc, "wing_area_m2", d["wing"]["area"], OPENAP, loc)
        t.add(tc, "wing_span_m", d["wing"]["span"], OPENAP, loc)
        t.add(tc, "engine_mount", d["engine"]["mount"], OPENAP, loc)
        t.add(tc, "n_engines", d["engine"]["number"], OPENAP, loc)
        default = d["engine"]["default"]
        t.add(tc, "engine_model", default, OPENAP, loc, note="OpenAP default engine")
        if default in engines.index:
            e = engines.loc[default]
            eloc = f"engine/engines.csv, name {default}"
            t.add(tc, "takeoff_thrust_kN_each", e.max_thrust / 1000.0, OPENAP, eloc, note="max_thrust N / 1000")
            t.add(tc, "bpr", e.bpr, OPENAP, eloc)
        else:
            unmatched.append(f"{tc}:{default}")
        dp = SRC / f"openap/dragpolar/{Path(path).name}"
        if dp.exists():
            p = yaml.safe_load(open(dp))
            dloc = f"dragpolar/{dp.name}"
            t.add(tc, "cd0", p["clean"]["cd0"], OPENAP, dloc)
            t.add(tc, "k", p["clean"]["k"], OPENAP, dloc)
            t.add(tc, "oswald_e", p["clean"]["e"], OPENAP, dloc)
            t.add(tc, "cd0_gear", p["gears"], OPENAP, dloc)
            flaps, floc = p["flaps"], dloc
        elif d.get("drag"):
            t.add(tc, "cd0", d["drag"]["cd0"], OPENAP, loc)
            t.add(tc, "k", d["drag"]["k"], OPENAP, loc)
            t.add(tc, "oswald_e", d["drag"]["e"], OPENAP, loc)
            t.add(tc, "cd0_gear", d["drag"]["gears"], OPENAP, loc)
            flaps, floc = d["flaps"], loc
        else:
            flaps, floc = d["flaps"], loc
        t.add(tc, "flap_cf_c", flaps["cf/c"], OPENAP, floc)
        t.add(tc, "flap_sf_s", flaps["Sf/S"], OPENAP, floc)
        t.add(tc, "flap_lambda_f", flaps["lambda_f"], OPENAP, floc)
    for kind in ("aircraft", "dragpolar"):
        for r in csv.DictReader(open(SRC / f"openap/{kind}/_synonym.csv")):
            subs.append({"typecode": r["orig"].upper(), "substitute": r["new"].upper(), "origin": "openap",
                         "basis": f"OpenAP 2.6.2 {kind}/_synonym.csv"})
    return unmatched


# --- Poll-Schumann -----------------------------------------------------------------------------
def read_ps(t: Table, subs: list[dict]) -> None:
    df = pd.read_csv(PS_FILE)
    for i, r in df.iterrows():
        tc, loc = r.ICAO, f"row {i + 2} ({r.Type})"
        t.add(tc, "manufacturer", r.Manufacturer, PS, loc)
        t.add(tc, "model", r.Type, PS, loc)
        t.add(tc, "mtow_kg", r.MTOM_kg, PS, loc)
        t.add(tc, "mlw_kg", r.MLM_kg, PS, loc)
        t.add(tc, "oew_kg", r.OEM_i_kg, PS, loc)
        t.add(tc, "wing_area_m2", r.Sref_m2, PS, loc)
        t.add(tc, "wing_span_m", r.span_m, PS, loc)
        t.add(tc, "n_engines", int(r.n_engine), PS, loc)
        t.add(tc, "takeoff_thrust_kN_each", r.nominal_F00_ISA_kn / r.n_engine, PS, loc, derived=True,
              note="nominal_F00_ISA_kn (all engines) / n_engine")
        t.add(tc, "bpr", r.nominal_bpr, PS, loc)
        t.add(tc, "mmo", r.MMO, PS, loc)
        t.add(tc, "ps_psi0", r.psi_0, PS, loc)
        t.add(tc, "ps_delta2", r.delta_2, PS, loc)
        t.add(tc, "ps_cos_sweep", r.cos_sweep, PS, loc)
    for r in csv.DictReader(open(PS_SYN_FILE)):
        tc, sub = r["ICAO Aircraft Code"].strip().upper(), r["PS ATYP"].strip().upper()
        if tc != sub:
            subs.append({"typecode": tc, "substitute": sub, "origin": "poll_schumann",
                         "basis": "pycontrails ps-synonym-list-20250328.csv"})


# --- curation ----------------------------------------------------------------------------------
def read_curation(t: Table, subs: list[dict]) -> dict[str, dict]:
    sources = {r["source_id"]: r for r in csv.DictReader(open(ROOT / "curation/sources.csv"))}
    for r in csv.DictReader(open(ROOT / "curation/facts.csv")):
        if r["source_id"] not in sources:
            raise SystemExit(f"curation/facts.csv: unknown source {r['source_id']}")
        value = r["value"] if r["field"] == "engine_model" else float(r["value"])
        t.add(r["typecode"], r["field"], value, r["source_id"], r["locator"])
    for r in csv.DictReader(open(ROOT / "curation/substitutions.csv")):
        subs.append({"typecode": r["typecode"], "substitute": r["substitute"], "origin": "thesis_analysis",
                     "basis": r["basis"]})
    return sources


# --- selection ---------------------------------------------------------------------------------
def pick(rows: list[dict], field: str, curated_ids: set[str]) -> dict | None:
    for want in FIELD_PRIORITY[field]:
        for r in rows:
            if r["field"] == field and (r["source_id"] == want or (want == CURATED and r["source_id"] in curated_ids)):
                return r
    return None


def derive_clmax(t: Table, by_type: dict, curated_ids: set[str]) -> None:
    for tc, rows in by_type.items():
        v, m, s = (pick(rows, f, curated_ids) for f in ("approach_speed_kt", "mlw_kg", "wing_area_m2"))
        if not (v and m and s):
            continue
        for field, f in CLMAX_FACTORS.items():
            vs = float(v["value"]) * KT_TO_MS / f
            cl = 2.0 * float(m["value"]) * G0 / (RHO0 * float(s["value"]) * vs ** 2)
            t.add(tc, field, round(cl, 3), DERIVED, "", derived=True,
                  note=(f"2 m g / (rho0 S (V_app/{f})^2); V_app {v['value']} kt [{v['source_id']}], "
                        f"m {m['value']} kg [{m['source_id']}], S {s['value']} m2 [{s['source_id']}]; "
                        "IAS taken as sea-level EAS"))


def main() -> None:
    t, subs = Table(), []
    read_acd(t)
    unmatched = read_openap(t, subs)
    read_ps(t, subs)
    curated = read_curation(t, subs)
    curated_ids = set(curated)

    by_type: dict[str, list[dict]] = defaultdict(list)
    for r in t.rows:
        by_type[r["typecode"]].append(r)
    derive_clmax(t, by_type, curated_ids)
    by_type = defaultdict(list)
    for r in t.rows:
        by_type[r["typecode"]].append(r)

    OUT.mkdir(exist_ok=True)
    rows = sorted(t.rows, key=lambda r: (r["typecode"], list(FIELDS).index(r["field"]), r["source_id"]))
    cols = ["typecode", "field", "value", "unit", "source_id", "locator", "derived", "note"]
    with open(OUT / "parameters.csv", "w", newline="") as f:
        w = csv.DictWriter(f, cols)
        w.writeheader()
        w.writerows(rows)

    rec_fields = list(FIELD_PRIORITY)
    recommended = []
    for tc in sorted(by_type):
        row = {"typecode": tc}
        for field in rec_fields:
            p = pick(by_type[tc], field, curated_ids)
            row[field] = p["value"] if p else ""
            row[f"{field}_source"] = p["source_id"] if p else ""
        recommended.append(row)
    with open(OUT / "recommended.csv", "w", newline="") as f:
        w = csv.DictWriter(f, ["typecode"] + [c for fd in rec_fields for c in (fd, f"{fd}_source")])
        w.writeheader()
        w.writerows(recommended)

    used = {r["source_id"] for r in rows}
    src_rows = []
    for sid in sorted(used):
        if sid in FIXED_SOURCES:
            s = FIXED_SOURCES[sid]
            src_rows.append({"source_id": sid, "title": s["title"], "publisher": s["publisher"],
                             "revision": s["revision"], "url": s["url"], "retrieved": s["retrieved"],
                             "sha256": sha256(s["file"]) if s["file"] else "", "kind": s["kind"],
                             "licence": LICENCE[s["kind"]]})
        else:
            s = curated[sid]
            src_rows.append({**s, "licence": LICENCE[s["kind"]]})
    with open(OUT / "sources.csv", "w", newline="") as f:
        w = csv.DictWriter(f, ["source_id", "title", "publisher", "revision", "url", "retrieved", "sha256",
                               "kind", "licence"])
        w.writeheader()
        w.writerows(src_rows)

    subs = sorted(subs, key=lambda r: (r["typecode"], r["origin"]))
    with open(OUT / "substitutions.csv", "w", newline="") as f:
        w = csv.DictWriter(f, ["typecode", "substitute", "origin", "basis"])
        w.writeheader()
        w.writerows(subs)

    with open(OUT / "fields.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["field", "unit", "group", "in_recommended", "priority", "description"])
        for fd, (unit, desc, group, rec) in FIELDS.items():
            prio = " > ".join(FIELD_PRIORITY.get(fd, [])) if rec else ""
            w.writerow([fd, unit, group, "yes" if rec else "no", prio, desc])

    site = {
        "fields": [{"field": fd, "unit": u, "description": d, "group": g, "recommended": rec,
                    "priority": FIELD_PRIORITY.get(fd, [])} for fd, (u, d, g, rec) in FIELDS.items()],
        "sources": src_rows,
        "types": {tc: [{k: r[k] for k in ("field", "value", "source_id", "locator", "derived", "note")}
                       for r in sorted(by_type[tc], key=lambda r: list(FIELDS).index(r["field"]))]
                  for tc in sorted(by_type)},
        "recommended": recommended,
        "substitutions": subs,
    }
    (ROOT / "docs/downloads").mkdir(parents=True, exist_ok=True)
    (ROOT / "docs/data.json").write_text(json.dumps(site, ensure_ascii=False, separators=(",", ":")))
    for csv_file in OUT.glob("*.csv"):
        shutil.copy(csv_file, ROOT / "docs/downloads" / csv_file.name)

    per_src = defaultdict(int)
    for r in rows:
        per_src[r["source_id"] if r["source_id"] in FIXED_SOURCES else "curated"] += 1
    print(f"types {len(by_type)}, values {len(rows)}, sources {len(used)}, substitutions {len(subs)}")
    print("values per source:", dict(per_src))
    print("OpenAP default engines not in engines.csv (no thrust/bpr row):", unmatched)


if __name__ == "__main__":
    main()
