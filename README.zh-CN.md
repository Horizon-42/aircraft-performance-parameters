# 机型性能参数库

本库收集**质点模型**要用的机型参数：质量、几何、阻力极曲线、着陆最大升力系数、推力、参考速度。
每个数值都标明来源文件、页码（或文件路径）和该来源的许可。

[English](README.md) · 浏览数据：`docs/index.html`（用 GitHub Pages 发布）

| | |
|---|---|
| 机型 | 391 个（ICAO 机型代码） |
| 数值 | 5,668 个，来自 103 份文件 |
| 有阻力极曲线的机型 | 37 个（OpenAP） |
| 有推导 C_L,max 的机型 | 122 个 |
| 许可 | GPL-3.0 |

本库为一个论文项目（AeroViz-4D）的终端区进近建模而建。只要下列来源中有一个给出了某机型的数据，这个机型就收进来，
不只限于那个项目用到的机型。

## 文件

| 文件 | 内容 |
|---|---|
| `data/recommended.csv` | 宽表。一个机型一行，每个字段一个值，按 `data/fields.csv` 的来源优先顺序选出，带 `<字段>_source` 列 |
| `data/parameters.csv` | 长表。所有来源的所有数值，一行一个 |
| `data/sources.csv` | 所有引用文件：标题、发布者、版本、链接、下载日期、sha256、许可 |
| `data/substitutions.csv` | "X 机型借用 Y 机型的参数"：OpenAP 同义表、Poll–Schumann 同义表、论文的分析结果 |
| `data/fields.csv` | 字段说明：单位、分组、来源优先顺序 |
| `sources/` | 构建脚本读的公开原始文件（OpenAP 2.6.2 数据、Poll–Schumann 参数表、FAA ACD 表格）和它们的许可文件 |
| `curation/` | 从型号合格证数据单（TCDS）和厂商文件手工读出的数值、文件清单、论文的替代决定 |
| `scripts/build.py` | 由 `sources/` 和 `curation/` 生成 `data/` 和 `docs/` |
| `docs/` | GitHub Pages 的静态页面 |

字段和来源优先顺序见 [README.md](README.md#fields)。

## 使用前要知道的事

- **C_L,max 是推导值，含近似。** 公开来源都不直接给着陆 C_L,max。本库用 FAA 进近速度反算：
  V_s = V_app / f，C_L,max = 2mg / (ρ₀ S V_s²)。f = 1.23 和 f = 1.3 各给一列。IAS 当作海平面 EAS，
  不做位置误差和压缩性修正。
- **一个 ICAO 代码对应多个型号。** 不同来源可能写的是不同型号（例：B763 的 MTOW，OpenAP 158.7 t，FAA ACD 186.9 t）。
  宽表只选一个值，长表列出全部。
- **Poll–Schumann 的阻力参数不换算。** 它的 C_D0 = C_f(Re)·ψ₀ 依赖雷诺数，所以只给原生的 `ps_*` 字段。
- **第一版留空的字段**：襟翼角、V_FE、V_LE、V_LO。
- **不用 ICAO 发动机排放数据库**（第一版）。

## 故意不收的来源

| 来源 | 原因 |
|---|---|
| BADA 3 / 4 | 许可规定数据和"任何计算结果"都保密 |
| EASA ANP | 未经数据提供方书面同意不得发布 |
| EUROCONTROL APD | 需要 EUROCONTROL 的版权许可 |
| 厂商文件和书籍的原文 | 有著作权。只保留数值和页码 |

## 许可和引用

整库用 GPL-3.0（OpenAP 的数据是 GPL-3.0，由它派生的数据库沿用这个许可）。Poll–Schumann 部分是 Apache-2.0，
见 `sources/poll_schumann/NOTICE`。FAA 数据是美国联邦政府作品。EASA 数据单注明出处即可转载。
用到 OpenAP 或 Poll–Schumann 的数值时，请引用 [README.md](README.md#citation) 里的两篇论文。

数值仅供研究和仿真，不可用于实际运行。
