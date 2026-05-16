# Replication Results Table

Auto-generated from `data/replication_results.json` by `scripts/aggregate_replication.mjs`.

- **Generated:** 2026-05-16T22:33:55.710Z
- **Findings:** 24
- **Verdict breakdown:** 9 REPLICATES, 5 REPLICATES (weak), 6 ADDS NUANCE, 2 INCONCLUSIVE, 2 CONTRADICTS

| ID  | Citation | Domain | Expected | r | n | Verdict |
| --- | --- | --- | :---: | ---: | ---: | --- |
| E1 | Barker et al. 2011 | Diabetes Belt geography | + | — | — | REPLICATES |
| E2 | Case & Deaton 2020 | Deaths of Despair geography | + | — | — | REPLICATES (weak) |
| E3 | Chetty et al. (related) | EITC peer clustering | + | — | — | REPLICATES |
| F | Kline & Moretti 2014 | TVA long-run infrastructure effect | + | — | — | REPLICATES (weak) |
| G | Markides & Coreil 1986; Ruiz 2013 | Hispanic Paradox via positive deviance | + | — | — | REPLICATES |
| H | ARC Distressed Counties (federal) | Peer alignment with ARC distressed-county list | + | — | — | ADDS NUANCE |
| I | RUPRI/HRSA | Rural health penalty (poverty-matched LE gap) | + | — | — | INCONCLUSIVE |
| J | Cutler & Lleras-Muney 2006 | Education–health gradient | + | 0.658 | 3062 | REPLICATES |
| K | Sommers et al. 2012 | Uninsurance–health link (EITC proxy) | + | 0.767 | 2931 | REPLICATES |
| L | Leung et al. 2017 | Food environment paradox (food access × diabetes) | - | -0.039 | 2945 | REPLICATES (weak) |
| M | Putnam 2000; Blakely et al. 2001 | Social capital × health (voter turnout, libraries) | + | 0.439 | 3038 | ADDS NUANCE |
| N | Meltzer & Schwartz 2016 | Housing cost × health tradeoff | + | — | — | REPLICATES |
| O | Pierce & Schott 2016; Autor 2013 | Manufacturing decline × mental health & diabetes | + | -0.199 | 2947 | CONTRADICTS |
| P | Whitacre et al. 2014 | Broadband × economic opportunity | + | 0.618 | 3134 | ADDS NUANCE |
| Q | Corak 2013 | Great Gatsby Curve (housing burden × poverty/EITC) | + | -0.034 | 3134 | REPLICATES (weak) |
| R | CDC/RWJF | Obesity Belt (obesity × diabetes co-geography) | + | 0.669 | 2947 | REPLICATES |
| S | Acemoglu & Restrepo 2017 | Aging × economic decline | - | -0.099 | 3134 | CONTRADICTS |
| T | Peri 2012; Card 2009 | Immigrant economic contribution | + | 0.411 | 3134 | ADDS NUANCE |
| U | DiPasquale & Glaeser 1999 | Homeownership × civic/social stability | + | 0.316 | 3104 | ADDS NUANCE |
| V | McLanahan & Sandefur 1994 | Single-parent households × child poverty | + | 0.282 | 3135 | ADDS NUANCE |
| W | Krueger 2017 | Disability–opioid nexus (mental-health proxy) | + | 0.473 | 2947 | REPLICATES |
| X | Glaeser & Mare 2001; Moretti 2004 | Urban wage premium (pop density × income, broadband) | + | 0.158 | 3134 | REPLICATES (weak) |
| Y | Wilson 1987 | Concentrated poverty (child poverty × health) | + | 0.563 | 2947 | REPLICATES |
| Z | Novaco & Gonzalez 2009 | Rural isolation × mental health | + | -0.010 | 2947 | INCONCLUSIVE |

---

## Per-sub-test verdict rule

Mirrors `checkDir()` in `tests/extended-replication.mjs` and `chk()` in `tests/research-domains-validation.mjs`:

- **REPLICATES** — sign matches expected direction AND |r| > 0.3
- **REPLICATES (weak)** — sign matches AND |r| ∈ [0.05, 0.3]
- **INCONCLUSIVE** — sign mismatch BUT |r| < 0.05
- **CONTRADICTS** — sign mismatch AND |r| ≥ 0.05

For `tests/known-effects-validation.mjs` (whose stdout lacks explicit `Verdict:` markers), the verdict is inferred from PASS/WARN/FAIL status plus label keywords (`partial`/`weak`).

## Per-finding rollup rule

1. ANY sub-test = CONTRADICTS → CONTRADICTS
2. ALL sub-tests = INCONCLUSIVE → INCONCLUSIVE
3. Mix of REPLICATES (strong) with INCONCLUSIVE or weak → ADDS NUANCE
4. All directional sub-tests = REPLICATES (strong) → REPLICATES
5. All directional sub-tests = REPLICATES (weak) only → REPLICATES (weak)

To regenerate: `node scripts/aggregate_replication.mjs` (requires network access to the live API).
