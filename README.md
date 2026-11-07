# Aircraft Performance Parameters

Open per-type parameters for **point-mass aircraft performance models**: mass, geometry, drag polar, landing
lift, thrust and reference speeds. Every value carries the document it came from, the page or file it was read
at, and that document's licence.

[中文说明](README.zh-CN.md) · Browse the data: `docs/index.html` (published with GitHub Pages)

| | |
|---|---|
| Aircraft types | 391 (ICAO type designators) |
| Values | 5,668, from 103 documents |
| Types with a drag polar (C_D0, k, e, gear, flaps) | 37 (OpenAP) |
| Types with a derived landing C_L,max | 122 |
| Licence | GPL-3.0 (see [Licence](#licence)) |

The set was assembled for terminal-area approach modelling in a thesis project (AeroViz-4D). It contains every
type for which at least one of the sources below gives data, not only the types that project flies.

## Files

| File | Content |
|---|---|
| `data/recommended.csv` | One row per type. One value per field, chosen by the source priority in `data/fields.csv`; each field has a `<field>_source` column. |
| `data/parameters.csv` | Every value from every source, one row each: `typecode, field, value, unit, source_id, locator, derived, note`. |
| `data/sources.csv` | Every cited document: title, publisher, revision, URL, retrieval date, sha256, licence. |
| `data/substitutions.csv` | "Type X uses type Y's parameters" statements: OpenAP synonyms, Poll–Schumann synonyms, and the thesis analysis (`thesis_analysis`). |
| `data/fields.csv` | Field dictionary: unit, group, source priority, description. |
| `sources/` | The public source files the build reads (OpenAP 2.6.2 data, Poll–Schumann parameter file, FAA ACD spreadsheet), with their licence files. |
| `curation/` | Values read by hand from type-certificate data sheets and manufacturer documents (`facts.csv`), the documents (`sources.csv`), and the thesis substitution decisions. |
| `scripts/build.py` | Builds `data/` and `docs/` from `sources/` and `curation/`. |
| `scripts/import_thesis_curation.py` | One-time export of `curation/` from the thesis repository. |
| `docs/` | Static page for GitHub Pages (`index.html`, `data.json`, CSV copies). |

## Fields

Grouped as in the point-mass model
V̇ = (δ·T_max − D)/m − g·sinγ, D = ½ρV²S·C_D, C_D = C_D0 + k·C_L² (+ gear and flap increments), C_L ≤ C_L,max.
"→" means "else".

| Field | Unit | Source priority |
|---|---|---|
| `manufacturer`, `model` | – | FAA ACD → OpenAP → Poll–Schumann |
| `aircraft_class`, `propulsion_class` | – | FAA ACD |
| `mtow_kg` | kg | curated → FAA ACD → OpenAP → Poll–Schumann |
| `mlw_kg` | kg | curated → FAA ACD → OpenAP → Poll–Schumann |
| `oew_kg` | kg | curated → OpenAP → Poll–Schumann |
| `wing_area_m2` | m² | curated → OpenAP → Poll–Schumann |
| `wing_span_m`, `wing_span_winglets_m` | m | FAA ACD → OpenAP → Poll–Schumann |
| `engine_mount` | – | OpenAP |
| `cd0`, `k`, `oswald_e`, `cd0_gear` | – | OpenAP |
| `flap_cf_c`, `flap_sf_s`, `flap_lambda_f` | – | OpenAP |
| `flap_angles_deg`, `vfe_kt`, `vle_kt`, `vlo_kt` | °, kt | **empty in this release** |
| `cl_max_landing_f123`, `cl_max_landing_f130` | – | derived (below) |
| `n_engines` | – | FAA ACD → curated → OpenAP → Poll–Schumann |
| `engine_model` | – | curated → OpenAP |
| `takeoff_thrust_kN_each` | kN | curated → OpenAP → Poll–Schumann |
| `takeoff_power_kW_each` | kW | curated |
| `bpr` | – | OpenAP → Poll–Schumann |
| `vmo_kt` | kt | OpenAP |
| `mmo` | – | OpenAP → Poll–Schumann |
| `approach_speed_kt`, `_min_kt`, `_max_kt` | kt (IAS) | FAA ACD |
| `ps_psi0`, `ps_delta2`, `ps_cos_sweep` | – | Poll–Schumann native (long table only) |

"Curated" values exist only where a type-certificate data sheet or manufacturer document gives the value and the
public tables lack it or are wrong. Example: the FAA ACD prints `MALW_lb` = 71,400 for B739 (= 32,386 kg, less
than half its MTOW of 187,700 lb; the number looks like a kilogram figure in the pound column), so `mlw_kg` for B739
comes from the Boeing 737NG airport-planning document (71,350 kg). The ACD value stays in `parameters.csv`.

## Read before use

- **Derived C_L,max is an approximation.** No public source gives a landing C_L,max. It is computed from the FAA
  approach speed at maximum landing weight:
  V_s = V_app / f, C_L,max = 2·m·g / (ρ₀·S·V_s²), ρ₀ = 1.225 kg/m³, g = 9.80665 m/s².
  Two columns: f = 1.23 (current certification, V_REF ≥ 1.23·V_SR) and f = 1.3 (FAA approach category, 1.3·V_SO).
  The IAS is taken as sea-level EAS (no position-error or compressibility correction). The note of each derived
  row names the three inputs and their sources.
- **One ICAO code, several variants.** Sources may describe different certified variants (B763 MTOW 158.7 t in
  OpenAP vs 186.9 t in the FAA ACD). `recommended.csv` picks one value by the fixed priority; `parameters.csv`
  shows all of them.
- **Poll–Schumann drag is not converted.** Its C_D0 = C_f(Re)·ψ₀ depends on Reynolds number, so ψ₀, δ₂ and the
  sweep are given as native `ps_*` fields and do not fill `cd0` or `k`.
- **Poll–Schumann thrust per engine** is derived: `nominal_F00_ISA_kn` (all engines) / `n_engine`.
- **OpenAP engines not in its engine table** (A318: CFM56-5B9; B37M, B38M, B39M, B3XM: LEAP-1B) have no OpenAP
  thrust or bypass ratio row.
- **Book values.** Three wing areas (BE40, FA10, FA50; `kind = book` in `data/sources.csv`) come from aircraft
  encyclopaedias. They are cited single facts; no text is reproduced.
- **ICAO Engine Emissions Databank** is not used in this release.

## What is deliberately not here

| Source | Why |
|---|---|
| BADA 3 / 4 (EUROCONTROL) | The licence makes the datasets and "any calculation results/output thereof" confidential. |
| EASA ANP database | Its terms forbid publication without the data provider's written consent. |
| EUROCONTROL Aircraft Performance Database | "Copyright permission must be sought from EUROCONTROL." |
| Verbatim text of manufacturer documents and books | Copyrighted. Only the factual value and its page are kept. |

## Licence

- The data and code in this repository are released under the **GNU General Public License v3.0** (`LICENSE`).
  OpenAP's data directory is GPL-3.0, and a database built from it carries that licence.
- `sources/openap/`: OpenAP 2.6.2 data, © Junzi Sun / TU Delft, GPL-3.0 (`sources/openap/LICENSE`).
- `sources/poll_schumann/`: pycontrails 0.63.5 parameter files, © Contrails.org and the Breakthrough Energy
  Foundation, Apache-2.0 (`sources/poll_schumann/LICENSE`, `NOTICE`).
- `sources/faa_acd/`: FAA Aircraft Characteristics Database, a US federal government work.
- EASA type-certificate data sheet values: "Reproduction is authorised, provided the source is acknowledged."
  Each value names its sheet in `data/sources.csv`.

## Citation

If you use the OpenAP or Poll–Schumann values, cite them:

- J. Sun, J. M. Hoekstra, J. Ellerbroek. *OpenAP: An Open-Source Aircraft Performance Model for Air Transportation
  Studies and Simulations*. Aerospace 7(8):104, 2020. doi:10.3390/aerospace7080104
- D. I. A. Poll, U. Schumann. *An estimation method for the fuel burn and other performance characteristics of
  civil transport aircraft. Part 3: Full flight profile when the trajectory is specified*. The Aeronautical
  Journal 129(1334):825–861, 2025. doi:10.1017/aer.2024.141

## Rebuild

```bash
pip install pandas openpyxl pyyaml
python scripts/build.py
```

`scripts/import_thesis_curation.py <thesis-repo>` regenerates `curation/` from the thesis repository; it is not
needed to rebuild.

## Publish the page

GitHub → Settings → Pages → Source: *Deploy from a branch*, branch `main`, folder `/docs`.

## Disclaimer

The values are for research and simulation. They are not for operational use.
