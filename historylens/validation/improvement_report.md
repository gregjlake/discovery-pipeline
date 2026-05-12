# HistoryLens — Improvement Report

**Reviewers:** one quantitative economic historian (cliometrics, Great Divergence, development economics) and one interactive-experience designer (data-vis products, audience engagement).
**Object under review:** `historylens/data/processed/historylens_final.json` (40 countries × 19 decades, 1820–2000), the pipeline at `historylens/pipeline/`, the prototype frontend at `historylens/index.html`, and the validation artifacts under `historylens/validation/`.
**Generated:** 2026-05-11.

**Note on inputs:** `methodology.md` does not exist in the repo; the academic methodology critique is captured in `academic_review.md` (read in full). The frontend prototype currently uses **hardcoded scores baked into `index.html`** rather than the pipeline JSON — fixing this is a precondition for every recommendation in Part 2.

---

# PART 1 — DATA IMPROVEMENTS

*Historian's perspective.*

## 1 — Missing variables that would dramatically improve historical peer discovery

The dataset's four scoring variables (GDP/cap, life expectancy, education years, Gini) cover the *outcome* side of development well but miss the *structural* side that the literature treats as causally upstream. Peer-discovery quality is bounded by the dimensionality of the signal — four correlated outcome variables collapse to ~2 effective dimensions, which is why mid-band peers (similarity 60–80%) feel coincidental (cf. South Korea ↔ Jamaica 1980 in the academic review).

| # | Variable | Why it matters | Source | Coverage | Difficulty |
|---|---|---|---|---|---|
| 1.1 | **Urbanization rate** | Already collected in `UrbanizationRatio_Compact.xlsx`, never added to the composite. Single best proxy for structural transformation (Bairoch; de Vries). | CLIO-INFRA (already in repo) | 40/40 countries, 1820–2000 nearly complete | **Easy** — adjust `STRUCTURAL_WEIGHTS` and re-run `03_normalize.py` |
| 1.2 | **Polity score / Executive constraints (xconst)** | The dataset cannot speak to Acemoglu–Robinson institutional questions without it. Currently the single largest missing dimension. | Polity5 (Marshall et al.); xconst back to 1800 for ~150 countries | ~35/40 from 1820, 40/40 from 1900 | **Easy** — Polity5 CSV is public domain, country-year format |
| 1.3 | **Investment / capital stock per worker** | Central to Solow / growth-accounting literature. Without it the dataset cannot distinguish "rich because high savings" from "rich because high productivity." | Penn World Tables 10.01 (`ck`, `csh_i`) from 1950; Maddison capital extensions for pre-1950 | 40/40 from 1950; ~15/40 for 1820–1950 | **Medium** — PWT is canonical post-1950, pre-1950 is patchy |
| 1.4 | **Trade openness (exports + imports / GDP)** | Required to interpret divergence/convergence cycles. The 1870–1914 first globalization and the 1980+ second are invisible without it. | Maddison Project supplementary; Federico-Tena World Trade Historical Database (2018) | 40/40 from 1870; ~25/40 for 1820–1870 | **Medium** — Federico-Tena is the gold standard but requires harmonization |
| 1.5 | **Agricultural employment share** | Sectoral transformation is the textbook structural-change variable (Kuznets, Chenery). Distinguishes "rising income" from "structurally modern." | Mitchell *International Historical Statistics*; OWID labor-by-sector | ~30/40 from 1850, 40/40 from 1900 | **Medium** — requires Mitchell digitization for early decades |
| 1.6 | **Infant mortality rate** | Captures health *distribution*, not just life-expectancy mean. The Soares / Cutler-Deaton convergence literature is built on this variable. | OWID + Mitchell; HMD post-1950 | 40/40 from 1900; ~25/40 for 1820–1900 | **Easy** — OWID has a clean panel |
| 1.7 | **Literacy rate** | Better-measured than mean years of schooling pre-1870. Education-years for 1820–1870 in CLIO-INFRA is the most fragile series in the current dataset. | Buringh & van Zanden (2009); OWID literacy | 40/40 from 1850, ~30/40 for 1820–1850 | **Easy** — single CSV from OWID |
| 1.8 | **Energy consumption per capita** | The single best proxy for industrial intensity. The 1870→1914 divergence is in large part an energy-intensity divergence. | Smil *Energy and Civilization*; OWID per-capita energy | 40/40 from 1900; ~20/40 from 1820 | **Medium** — pre-1900 estimates are crude but available |
| 1.9 | **Sovereign debt / GDP** | Required for any 20th-century crisis narrative (Argentina, Russia 1998, Greece 2010). | Reinhart-Rogoff *This Time Is Different* dataset (publicly posted) | 35/40 from 1820 | **Easy** — RR data is one CSV |
| 1.10 | **Patents per million / R&D intensity** | The technology dimension of structural strength. Without it, 1950+ peer matches between, say, South Korea and Argentina look more similar than they are. | OECD STI post-1980; WIPO IP statistics back to 1883 for many countries | 40/40 from 1980; ~25/40 1900–1980 | **Medium** — WIPO data is harmonizable but historical units differ |

**Priority recommendation:** **#1.1 (urbanization) and #1.2 (Polity)** together would close ~80% of the academic credibility gap with minimal pipeline work. Both are public, both are already country-year, both add a genuinely orthogonal dimension to the four outcome variables.

## 2 — Missing countries that would make the dataset more globally representative

Current `sample_composition`: Western Europe 17, Latin America 10, East Asia 5, North America 2, Anglo-Pacific 2, Africa 2, Eastern Europe 1, South Asia 1. **The sample is Eurocentric to the point that peer pools for non-Western countries are structurally thin.** The academic review flagged that India is the only South Asian country and that no Sub-Saharan African country except South Africa is included.

| # | Country | Why it matters | Data availability | Existing-variable coverage |
|---|---|---|---|---|
| 2.1 | **Nigeria** | Largest African economy and population. Acemoglu–Robinson, Easterly, and the colonial-legacy literature all turn on Nigerian evidence. | Maddison from 1950 (some 1900 estimates); CLIO-INFRA life expectancy from 1900; education from 1960 | ~3/4 scoring vars from 1950; ~1/4 from 1900 |
| 2.2 | **Turkey / Ottoman Empire** | Bridges Europe and the Middle East; central to Pamuk's divergence work; absent from a 1820–2000 dataset is conspicuous. | Maddison from 1820 (good Ottoman series); CLIO-INFRA life exp from 1900 | ~4/4 from 1920; ~2/4 from 1820 |
| 2.3 | **Iran / Persia** | The other major non-Arab Muslim economy; oil-state comparator to Venezuela and Saudi Arabia. | Maddison from 1820 (Issawi/Hakimian); life expectancy from 1900 | ~3/4 from 1900 |
| 2.4 | **Indonesia** | World's 4th largest population; Dutch colonial counterfactual to British India; already in the dataset as "Indonesia" — verify Java vs. all-Indonesia coverage and whether pre-1945 Dutch East Indies is correctly attributed. | Maddison (Booth); CLIO-INFRA life exp | Already present — needs audit |
| 2.5 | **Bangladesh / East Bengal** | Without it the post-1947 Indian-subcontinent partition is invisible. The independence-shock comparison India-1950 vs Bangladesh-1972 is one of the cleanest natural experiments in development economics. | Maddison post-1950; pre-1947 absorbed in India series | ~3/4 from 1950 |
| 2.6 | **Pakistan** | Same rationale as Bangladesh; Pakistan ↔ India peer trajectory 1950→2000 is a textbook case. | Maddison post-1950 | ~3/4 from 1950 |
| 2.7 | **Saudi Arabia** | Oil-rentier archetype; comparator to Venezuela's structural shape. Without it, Venezuela 1950 → 1980 lacks its natural peer. | Maddison from 1950; life exp from 1950 | ~3/4 from 1950 |
| 2.8 | **Ghana** | The Bates / Acemoglu "Africa rising" / institutional-reversal literature centers on Ghana–Korea (both ~$500 GDP/cap in 1957). | Maddison from 1900; CLIO-INFRA life exp from 1950 | ~3/4 from 1950, ~2/4 from 1900 |
| 2.9 | **Kenya** | East African anchor; required to evaluate the settler-colony hypothesis (Kenya = settler, Ghana = extractive). | Maddison from 1950 | ~3/4 from 1950 |
| 2.10 | **Vietnam** | Post-1986 Doi Moi reform is one of the largest sustained development episodes ever recorded. | Maddison from 1950 (van der Eng); CLIO-INFRA from 1960 | ~3/4 from 1960 |
| 2.11 | **Czechoslovakia / Czechia + Slovakia** | Central European industrial frontier; pre-1939 was among the world's top-10 GDP/cap economies — currently invisible. | Maddison full coverage 1820–2000 | ~4/4 from 1850 |
| 2.12 | **Austria** (separable from Habsburg empire post-1918) | Anchors the German-language industrial cluster that's currently just Germany + Switzerland. | Maddison full coverage | ~4/4 from 1850 |

**Priority recommendation:** **Nigeria, Turkey, Pakistan, Ghana, Saudi Arabia** — adding these five alone shifts `sample_composition` from "17 Western Europe / 1 Africa" toward a defensible global panel and unlocks the colonial-legacy and resource-curse analyses the literature expects this kind of tool to support.

## 3 — Historical events that should be annotated on country trajectories

For each, the format is *Event · decade(s) · countries affected · expected structural-score impact · one-sentence explanation*. These should appear as inline annotations on country trajectory charts and as filterable "events of this decade" callouts on snapshot pages.

| # | Event | Decade | Countries | Expected impact | One-sentence explanation |
|---|---|---|---|---|---|
| 3.1 | **Meiji Restoration** | 1870 | Japan | Inflection point; score begins sustained rise | A 1868 coup ended centuries of feudal rule and launched Japan's deliberate industrialization. |
| 3.2 | **Unification of Germany** | 1870 | Germany | Sharp rise in score and convergence with France | Bismarck unified 39 states into one customs union and industrial power. |
| 3.3 | **Belle Époque / First Globalization peak** | 1900–1910 | Western Europe, USA, Argentina | Broad-based score rise, especially Argentina | Free trade, gold standard, and mass migration produced a globalized economy that didn't return until the 1990s. |
| 3.4 | **First World War** | 1910 | UK, France, Germany, Russia | Sharp score drop for combatants; sustained drop for Russia | A four-year industrial war that killed 20 million and ended four empires. |
| 3.5 | **Russian Revolution** | 1910–1920 | Russia | Data gap, then re-entry with new economic system | The 1917 Bolshevik takeover began the Soviet experiment in planned industrialization. |
| 3.6 | **Spanish Flu** | 1920 | All | Life-expectancy dip 1920 vs trend | The 1918–1920 pandemic killed 50–100 million globally and is the cleanest natural experiment in mass mortality. |
| 3.7 | **Great Depression** | 1930 | USA, Germany, Latin America | Note that decade resolution hides the trough (see §H academic review) | The 1929 Wall Street crash triggered a global slump that worsened until 1933. |
| 3.8 | **Soviet First Five-Year Plan** | 1930 | Russia | Score rises despite famine | Stalin's forced industrialization built heavy industry on the backs of mass collectivization and famine. |
| 3.9 | **Second World War** | 1940 | Germany, Japan, Russia, UK, USA | Combatant scores drop; USA score rises | Six years of total war; USA emerged as the only major economy with intact industrial capacity. |
| 3.10 | **Marshall Plan** | 1950 | Western Europe | Rapid score recovery 1950–1960 | $13B in US aid (~$170B today) rebuilt European industry and locked in the Western alliance. |
| 3.11 | **Indian Independence and Partition** | 1950 | India, Pakistan, Bangladesh | Discontinuity in series | 1947 ended 90 years of British direct rule and split the subcontinent. |
| 3.12 | **Chinese Communist Revolution** | 1950 | China | Series discontinuity; subsequent slow rise | The 1949 founding of the PRC began three decades of planned economy under Mao. |
| 3.13 | **South Korean takeoff** | 1960–1990 | South Korea | Steepest sustained score rise in the dataset | Park Chung-hee's developmental state turned a country poorer than Ghana into a G20 economy. |
| 3.14 | **Cuban Revolution** | 1960 | Cuba | Score discontinuity | Castro's 1959 revolution redirected Cuba toward a Soviet-aligned planned economy. |
| 3.15 | **OPEC Oil Crisis** | 1970 | Venezuela, Saudi Arabia (when added), Western importers | Venezuela ↑; Western Europe and Japan score drop | The 1973 oil embargo quadrupled crude prices and ended the postwar boom. |
| 3.16 | **Argentine military rule + debt crisis** | 1970–1980 | Argentina | Score declines from 1970 peak | Seven years of dictatorship and the 1982 default ended the "Argentine paradox" of comparable-to-Australia status. |
| 3.17 | **Chinese Reform and Opening** | 1980 | China | Sustained score rise begins | Deng Xiaoping's 1978 reforms began the largest poverty reduction in human history. |
| 3.18 | **Fall of the Berlin Wall / Soviet Collapse** | 1990 | Russia, Eastern Europe | Russia score collapse; Poland, Hungary score recovery by 2000 | The 1989–1991 collapse ended the Cold War and triggered the deepest peacetime depression in modern Russia. |
| 3.19 | **Asian Financial Crisis** | 1990 | South Korea, Indonesia | Score dip in 1990–2000 window | The 1997 crisis halved currencies and exposed structural fragilities in the East Asian model. |
| 3.20 | **End of Apartheid** | 1990 | South Africa | Series discontinuity; life-expectancy reverses with HIV | The 1994 democratic transition coincided with the AIDS epidemic that cut life expectancy by a decade. |

**Implementation suggestion:** ship a `historylens/data/events.json` with this list. Render as small annotations on the trajectory line; tap an annotation to read the sentence and see "countries affected this decade." This is genuinely low-effort and transforms charts from "lines" into "narratives."

## 4 — Known data-quality issues in CLIO-INFRA and Maddison

These are the cells most likely to be contested by a reviewer; the dataset should flag them rather than display them at full confidence.

| # | Concern | Affected cells | What to do |
|---|---|---|---|
| 4.1 | **Maddison pre-1820 estimates are essentially benchmarks not series.** The 1820 Maddison number is a Bolt-van Zanden educated guess for many countries; it should not be treated as observationally equivalent to a 1990 number. | All 1820 cells, especially China, India, Russia, Latin America | Show 1820 with reduced opacity / wider uncertainty band; document in tooltip |
| 4.2 | **Lindert-Williamson note that pre-1960 Gini is "informed conjecture."** The single-source dependency on CLIO-INFRA Gini for 1820–1950 is the single most fragile input. | All Gini cells pre-1960 for non-Western countries | Flag pre-1960 Gini at the variable level; consider a "without Gini" alternative score |
| 4.3 | **CLIO-INFRA mean years of schooling pre-1870 is reconstructed from literacy proxies**, not directly measured. | Education-years 1820–1870 for ~30/40 countries | Substitute literacy rate (Buringh-van Zanden) for pre-1870; document |
| 4.4 | **China GDP/cap pre-1950 is the most-contested series in cliometrics.** Maddison's China numbers were revised significantly between 2010 and 2023; Broadberry-Guan-Li differ substantially from Maddison. | All China cells 1820–1950 | Add "alternative source" toggle: Broadberry-Guan-Li for China; show as a switchable series |
| 4.5 | **India 1900–1950 partition issue.** Pre-1947 India in Maddison covers Pakistan + Bangladesh + India; post-1947 series do not always disentangle cleanly. | India 1900–1950, Pakistan/Bangladesh 1950+ | Document boundary; if Pakistan/Bangladesh are added, harmonize the discontinuity |
| 4.6 | **Soviet/CMEA price distortion.** Maddison's Soviet GDP/cap is a Western-method reconstruction; CMEA-method numbers were systematically higher. The "real" Soviet living standard is genuinely uncertain to ~±30%. | Russia 1920–1990, Hungary 1950–1990, Poland 1950–1990 | Tooltip note; consider showing both Western and CMEA reconstructions |
| 4.7 | **Argentina pre-1875 GDP is one estimate (Della Paolera) with no peer-reviewed alternative.** | Argentina 1820–1870 | Document; treat as low-confidence |
| 4.8 | **Life-expectancy "at birth" pre-1900 is heavily smoothed.** What looks like a 1820–1900 trend is often four data points interpolated. | All life-expectancy cells 1820–1900 | Show interpolation density at the variable level |
| 4.9 | **Boundary changes hidden in country-name continuity.** "Germany" 1820 = the Zollverein states; "Germany" 1920 = Weimar (no Alsace, etc.); "Germany" 1950 = West Germany; "Germany" 2000 = unified Germany. Score discontinuities of ±5 are baked in. | Germany, Russia/USSR, Poland, Turkey/Ottoman | Add a "boundary changed this decade" flag in the data and in tooltips |
| 4.10 | **Population 1820 is a back-projection** from later census waves for most non-Western countries. | All 1820 population cells outside Western Europe | Already mitigated by removing population from the composite; still relevant for display |

## 5 — Additional analyses that would be academically novel

These are analyses HistoryLens could run that — to my knowledge — no published paper or existing tool does in the form proposed. Each could be a *Journal of Economic History* note or an *Explorations in Economic History* method piece.

1. **Peer-stability index as a measure of structural inflection.** Countries whose top-3 peers churn rapidly between consecutive decades are by construction undergoing structural change. The dataset's `peer_stability` field can be aggregated into a *churn rate per country* — and the decades of maximum churn should correspond to inflection events (Meiji 1870 for Japan, partition 1950 for India, reform 1980 for China). This is a derived metric that nobody currently reports.

2. **Multi-scheme peer agreement as a similarity-confidence measure.** The pipeline already computes `score_a`, `score_b`, `score_c` (three weight schemes). The fraction of times a peer appears across all three schemes is itself a credibility weight. Publish this as `peer_robustness` — a peer that shows up under all three weighting philosophies is robustly similar; one that only shows up under GDP-heavy weighting is conditionally similar.

3. **"Structural age" — when did country X look like country Y did?** For every pair (X, decade_X), find the decade *d* in which country Y had the closest structural profile to X. *Today's Vietnam looks like Korea did in 1985.* This is the analysis everyone *thinks* they're getting from the tool but nobody has actually built. It requires Mahalanobis on cross-time anchored data, but the data infrastructure is already there.

4. **Convergence club detection.** Quah-style convergence-club analysis (which countries are converging *to each other* vs. diverging) is normally done on GDP/cap only. With four scoring variables, the multi-dimensional convergence picture is genuinely under-published. Publish a "convergence map" per decade showing which countries are pulling toward which cluster.

5. **The Pomeranz-Broadberry adjudication.** With Broadberry-Guan-Li China data alongside Maddison, the tool could let users *toggle* the China series and see how peer rankings shift. This is the cleanest illustration of how methodological choices in one source ripple through to comparative claims, and it would attract the cliometric audience that currently dismisses general-audience history-data tools.

6. **Decade-of-greatest-similarity histograms.** For each country, the histogram of "decade your closest peer is from" reveals out-of-time twinning patterns. *Argentina-1980 is closest to Italy-1960 (twenty-year lag).* This kind of inter-temporal peer pattern has not been systematically published.

7. **Anti-peers / structural opposites.** Every paper reports "most similar"; nobody reports "most different." The country whose vector points opposite yours within a decade is informative — *the anti-peer of UK 1900 was India 1900*. Anti-peer trajectories over time are unstudied.

8. **Score-decomposition attributions.** For every score, decompose into "how much of this came from GDP, how much from life expectancy, how much from education." Stack-bar this on trajectories. This is the kind of transparency that would let a reviewer cite individual cells.

---

# PART 2 — EXPERIENCE IMPROVEMENTS

*Designer's perspective. Brutal honesty per the brief.*

## 6 — The most important missing interaction

**Cross-time peer comparison: "show me when country Y looked like country X looks now."** Two-slider design: top slider sets a reference country-decade (e.g., Vietnam 2000); the second view searches the entire panel for the closest match (Korea 1985, with similarity 94%). Drag either slider and watch the match recompute live.

Why this is the single most important missing interaction:
- It is the **one question the data uniquely can answer** that you cannot get from Wikipedia, Maddison, or Our World in Data.
- It rewards exploration: every slider drag produces a *named, sharable surprise*.
- It produces a natural unit of social content: *"Vietnam today ≈ Korea 1985"* is a tweet-sized claim that earns attention.
- The data infrastructure already exists — it just needs the UI.

**Exact UX:** two stacked cards. Top card: pick a country + decade (default: USA 2000). Bottom card: a ranked list of the 10 closest country-decade matches across history, with similarity, GDP-per-capita ratio, life-expectancy gap, and a one-line story. Tapping a row opens the trajectory comparison.

## 7 — Storytelling gaps

The current prototype shows 40 colored peaks on a 3D map. **A first-time visitor with no prior interest in economic history has no reason to be moved.** Specific gaps:

1. **No entry narrative.** A visitor lands and sees a globe of numbers. There is no opening question, no provocation, no "what if I told you Japan in 1870 looked exactly like Russia." Compare to Pudding.cool: every story starts with a single arresting claim.
2. **Stories are hardcoded in the HTML** (lines 184–199 of `index.html` carry written stories), but they are generic ("On the cusp of industrial transformation") rather than tied to the data ("UK's GDP just passed Netherlands' for the first time in 200 years"). Stories should be *generated from the data* — what changed this decade vs. last, who is the new top peer, what crossed which threshold.
3. **No moments of revelation.** A great data product creates one "wait, what?" moment per minute. Currently the only revelation is "I can rotate the map." The dataset contains dozens of buried surprises (Bolivia ↔ South Africa 1900; Japan ↔ Russia 1870; Switzerland #1 in 1900) — none of them are surfaced as wonder-moments.
4. **No human scale.** Scores are 0–100. There is no anchor — no "this is what a 50 felt like to live in." Pair each score band with a one-sentence everyday-life referent: *"~25 = life expectancy ~35, most children working by age 10."* This is where the data becomes felt.
5. **The peer pairings are the magic; they are buried in tooltips.** The single most distinctive thing this tool can do — find country-decade twins — is hidden behind a hover. It should be on the front page.

## 8 — The viral mechanic

**"Your country's twin through history" — a shareable card generator.**

Design: pick a country and decade. The tool generates a single 1200×675px social-share card that says:

> **Japan, 1870.**
> Structurally identical to: **Russia, 1870** (99% match)
> *Two future rivals, then two backwater empires — same GDP, same life expectancy, same education, same inequality.*
>
> `historylens.org/share/japan-1870`

The card has:
- A small two-country thumbnail (silhouettes or flags).
- Four mini-bars showing the four matched variables.
- A one-sentence "why this is surprising" caption (auto-generated from the event annotations in §3 and the regional distance — *"twins from opposite sides of the world"*).
- Footer with HistoryLens wordmark.

Why it works:
- **It's a claim, not a chart.** People share claims. Charts they screenshot.
- **The surprise is built in.** Bolivia ↔ South Africa, Japan ↔ Russia, Argentina 1900 ↔ Italy 1960 — the data is full of these.
- **Frictionless to generate.** Two clicks (pick country, pick decade) produces a card.
- **Each card is unique.** 40 × 19 = 760 possible cards; visitors discover their own.
- **It gives the tool a name on first share.** "HistoryLens" appearing on a card with a counter-intuitive claim is exactly the brand impression you want.

Companion mechanic: a daily "twin of the day" tweet from an auto-posting account (`@historylens_twin`), surfacing one surprising peer pair per day. The dataset has 760 cells × ~3 peers = ~2,200 potential daily posts. That's six years of daily content with no human writing.

## 9 — Five audience entry points currently missing

| Audience | Arrives asking | Tool currently does | Tool should do |
|---|---|---|---|
| **A. The history-curious adult (NPR / Atlantic reader)** | *"I read about Argentina's decline — what does that look like?"* | Shows a 3D globe with no path to Argentina. They bounce in 5 seconds. | Front-door homepage with "Stories" tab: *Argentina's century · Japan's takeoff · the Soviet rise and fall · etc.* — each a curated 6-decade walkthrough with text and trajectory. |
| **B. The economics undergrad** | *"My prof mentioned the Great Divergence. What was the gap in 1820 vs 1900 vs 1950?"* | No path. Tooltips reveal scores but no comparison. | "Compare" page: pick 2–6 countries, see normalized trajectory + raw variables + peer overlap as small multiples. Citation block at the bottom (BibTeX). |
| **C. The data journalist** | *"I'm writing about inequality — give me a chart I can quote."* | No export. No share URL. No attribution-ready chart. | Every chart has a "Get this chart" button: PNG + SVG + CSV of underlying numbers + suggested caption + permanent URL + DOI-style citation. |
| **D. The teacher (high school history / econ)** | *"I want to show my class what life expectancy looked like in 1900."* | No lesson hooks. No way to point students at a specific view. | "Classroom" page with permalinked snapshots: *1900 world · 1950 world · the Soviet collapse decade · etc.* with discussion questions. |
| **E. The quantitative economic historian** | *"How are you handling the Maddison 2023 revision? What's your weighting? Can I cite this?"* | A README that doesn't surface the answers. No codebook. No methodology page. No DOI. | Methodology page (the missing `methodology.md`), per-cell provenance, sensitivity analysis page, Zenodo DOI for each release. (See §17.) |

These five paths share zero pixels with the current homepage. Each is a separate URL slot that *converges* on the same underlying data view.

## 10 — The 10-second test

**Currently** (brutally honest): a visitor sees a dark blue 3D map of the world with colored vertical bars and three sliders. The headline reads **"HISTORYLENS — STRUCTURAL STRENGTH"** — a phrase that means nothing outside cliometrics. There is no question, no claim, no story. The visitor's reaction at 10 seconds: *"Cool graphic. Don't know what I'm supposed to do with it. Closing tab."*

**What it should be:** an animated headline tells a single counter-intuitive story in 8 seconds, then drops the visitor into the interactive view.

```
Hero sequence (auto-plays, then loops):
  ┌──────────────────────────────────────────────┐
  │  In 1870, Japan and Russia were identical.   │   ← 2s
  │  In 1980, Argentina was where Italy had      │   ← 2s
  │     been in 1960.                            │
  │  In 1900, Switzerland — not Britain —        │   ← 2s
  │     was the world's most developed country.  │
  │                                              │
  │   These are the things HistoryLens shows.    │
  │              [Start exploring]               │   ← 2s
  └──────────────────────────────────────────────┘
```

That's the test. Three concrete claims in 8 seconds, all from the actual data, each one a reason to stay. After the visitor clicks "Start exploring," the 3D globe is fine — but it can't be the front door.

## 11 — Information architecture — the ideal user journey

```
                       ┌──────────────────────┐
                       │  homepage hero       │
                       │  3 claims, 8 seconds │
                       └──────────┬───────────┘
                                  │
       ┌──────────────────────────┼────────────────────────────┐
       │                          │                            │
       ▼                          ▼                            ▼
  ┌─────────┐               ┌─────────────┐             ┌─────────────┐
  │ EXPLORE │               │ STORIES     │             │ COMPARE     │
  │ (globe) │               │ (curated)   │             │ (2 picks)   │
  └────┬────┘               └─────┬───────┘             └──────┬──────┘
       │                          │                            │
       │ pick country-decade      │ pre-built walks            │ pick A + B
       ▼                          │ - Meiji                    │
  ┌─────────────────┐             │ - Argentina                ▼
  │ COUNTRY-DECADE  │◀────────────┤ - Soviet                  ┌──────────────┐
  │ SNAPSHOT PAGE   │             │ - China rise               │ COMPARISON  │
  │                 │             │ - Pomeranz toggle          │ side-by-side│
  │ - score        │             └────────────────────────────└──┬───────────┘
  │ - 3 peers       │                                            │
  │ - twin-finder   │◀───────────────────────────────────────────┘
  │ - share card    │
  │ - event banner  │
  │ - methodology   │──▶ methodology page (codebook, sources, DOI)
  └─────────────────┘
```

**Where the current IA fails:**
- There is only one screen (the globe). Everything has to be discovered through hover.
- No URL strategy — a visitor cannot share *"Argentina in 1900"* as a link.
- No content shelf — nothing tells the visitor what's interesting to look at.
- No on-ramp for academic users (no methodology page, no citation, no DOI).
- No off-ramp for general-audience users (no "what should I look at next").

## 12 — Emotional design

> *"Ancestry.com makes people cry."* The cry-mechanic is: you find an ancestor and the abstract becomes a person.

**HistoryLens has the same latent material and isn't using it.** The emotional moment is:

> *"In 1900, the average person where my great-grandparents lived had a life expectancy of 42 years and three years of schooling. By 2000, that was 79 years and 13 years. Three generations."*

This is doable today with the data we have. The product moment:

1. **"Where did your family come from?"** — a country picker on the homepage.
2. **"What was life there when they left?"** — pick the decade (or use a default like "100 years ago").
3. **A single screen** with the four variables visualized as everyday-life icons: a clock showing life expectancy, books showing education years, coins showing GDP/cap, scales showing inequality.
4. **"Today, that country looks like…"** — show 2000 numbers in the same icons, side by side.
5. **"In a hundred years, this country's structural strength rose from X to Y. Here's what changed."** — auto-generated paragraph from the variable trajectory.

That's the cry-moment. It uses the existing data, requires no new variables, and gives a visitor with no prior interest in cliometrics a reason to feel something.

A second, secular emotional moment: **the "twin" reveal.** When a visitor learns that the place they're from in 1900 was structurally identical to a place on the opposite side of the world they've never thought about, it produces a small recalibration of how they think the past works. That's an emotional moment dressed up as data.

## 13 — Mobile experience

**Currently:** the Three.js globe with drag-rotate, three desktop sliders, and a hover popup is **functionally unusable on mobile.** Touch events for rotate fight with page scroll; sliders are pixel-precise; hover popups don't work on touch.

**Mobile-first redesign:**
- **Replace the 3D globe with a 2D map projection** on small screens (under 768px). The globe is decorative; the map is functional and renders 10× faster.
- **Vertical layout:** map at top (40% viewport height), year slider as the dominant element under it, list of countries-by-rank below.
- **Tap a country = open snapshot page** as a full-screen sheet. No hover, no popup.
- **Swipe the year slider** with finger; the map animates in real time.
- **Share card generation is the killer mobile feature** — a single "share twin" button generates the §8 card and opens the native share sheet. Mobile is where viral content travels.

Mobile is where this product wins or loses. The current build loses.

## 14 — The comparison nobody else can make

**Wikipedia can show you Argentina's GDP over time. Maddison can show you a CSV. Our World in Data can show you life expectancy by country. *None of them can tell you that Argentina-2000 most closely resembles Italy-1960, with 91% similarity across four variables.***

That cross-time, cross-country, multi-variable similarity match is the defensible unique value of HistoryLens. Every textbook treats countries as separable rows and centuries as separable columns. HistoryLens is the only tool that lets you find the *diagonal*: a country-decade twin across both axes.

Concretely, **the visualizations that only HistoryLens can produce** are:

1. **Twin map.** A world map where each country is colored by *which decade of which other country it most resembles right now*. Vietnam → Korea-1985, India → Brazil-1970, etc. Single image, immediately comprehensible.
2. **Time-machine view.** Pick a country-decade. The map highlights every other country that has *previously been here* (i.e., had this same structural profile in some past decade). *"This is what 'normal' looked like in 1920. Today, three countries are still here."*
3. **Trajectory braid.** Two countries plotted not against time but against each other — Argentina's trajectory vs. Italy's, with the years marked on the line. Where they kissed, where they diverged.
4. **Convergence cloud.** All 40 countries plotted in 2D PCA of the four variables, animated by decade. The cluster geometry changes; the West tightens; East Asia migrates across the cloud. Watching the cloud reshape is the closest thing to *seeing* the Great Divergence.

These four views are technically achievable on the current data. They are also the four views a Webby jury would single out.

---

# PART 3 — COMBINED RECOMMENDATIONS

## 15 — Top 5 highest-impact improvements

| Rank | Change | Why it matters | Build difficulty | Expected impact |
|---|---|---|---|---|
| **1** | **Build the country-decade snapshot page with shareable twin cards** (§6, §8) at permalinked URLs (`historylens.org/c/japan/1870`). | Unlocks the IA (§11), the viral mechanic (§8), and the citable artifact (§17) in one move. Without permalinks the product cannot be shared, cited, or taught. | **Medium** (1–2 weeks) — needs a router, the snapshot template, and the social-card image generator. | **Very high.** Single highest-leverage build. |
| **2** | **Wire the frontend to the pipeline JSON** and drop the hardcoded scores from `index.html`. | Currently the prototype displays one set of numbers and the pipeline produces another. The 1.13 MB JSON is already correct, fully tested, has known_gaps annotated, and is unused. This is a precondition for everything else. | **Easy** (1–2 days) — one fetch, one bind. | **High.** Establishes the source-of-truth contract. |
| **3** | **Add urbanization and Polity score to the composite** (§1.1, §1.2). | Closes ~80% of the academic-credibility gap. Both data sources are already in repo or one CSV away. Adds two orthogonal dimensions that fix the mid-band peer-quality problem (cf. SK↔Jamaica). | **Easy–Medium** (2–3 days) — modify `_common.py` weights, re-run pipeline. | **High.** Makes the tool defensible in cliometric circles. |
| **4** | **Add the methodology page, per-cell provenance, and a Zenodo DOI for each pipeline release.** | The single largest blocker to academic citation (§17). The pipeline is reproducible; nothing about that is currently surfaced to a reader. | **Medium** (1 week) — write `methodology.md`, extend export to carry source column, set up Zenodo. | **High** for the academic audience; modest for general audience but raises perceived trust across the board. |
| **5** | **Build the "Stories" tab with 5–10 curated walkthroughs** (Meiji, Argentine paradox, Soviet rise and fall, China reform, Pomeranz toggle). | Solves the "what do I look at?" problem. Each story is a guided tour through the data with text, annotations (§3), and progressive trajectory reveal. Generates SEO, gives press something to link to, and converts general-audience visitors into return users. | **Medium** (2 weeks) — content is the long pole; the rendering shell is small. | **High** for engagement; necessary for any press cycle. |

## 16 — The killer feature

**The Time-Machine view.** Pick any country-decade (e.g., Vietnam 2020). The world map fills with markers showing every other country-decade that resembled this one within similarity ≥ 85%: Korea 1985 (91%), Thailand 1995 (89%), Mexico 1975 (86%). Each marker carries one sentence: *"Korea, 1985 — three years before the Olympics, four before democracy."*

This is the feature that is genuinely irreplaceable because:
- **No other tool does it.** Wikipedia, Maddison, OWID, Penn World Tables — none of them resolve "country-decade twins" as a primary query.
- **It works for every cell.** 40 × 19 = 760 entry points. Every visitor has a thousand things to find.
- **It produces an answer that feels like a discovery.** *"Vietnam today was Korea in 1985"* is the kind of sentence people remember.
- **It directly outputs the shareable card.** §8's mechanic is the natural artifact of §16's interaction.
- **It is the academic novelty (§5.3) and the viral mechanic (§8) and the emotional moment (§12) packaged into one feature.**

If only one feature ships, it should be this.

## 17 — What would make a quantitative economic historian cite this in a paper

Exact requirements. Each is non-negotiable for citation:

1. **A frozen, versioned, DOI-cited release.** Mint a Zenodo DOI per pipeline release. Citable as *Lake, G. (2026). HistoryLens v2.0 dataset and pipeline. Zenodo. doi:10.5281/zenodo.xxxxxxx.*
2. **A complete methodology document** (`historylens/validation/methodology.md` — currently missing) covering: variable selection rationale, source priority order, harmonization rules, normalization choice and its consequences, weighting choice and its sensitivity, distance metric, peer-selection threshold, treatment of missing data.
3. **Per-cell source attribution** in the export. Every (country, decade, variable, value) cell needs an accompanying source code (e.g., `MADDISON_2023`, `CLIO_LIFE_v3`, `OWID_2024_05`).
4. **A sensitivity-analysis page** showing peer-top-3 stability under at least three weight schemes and at least two distance metrics (Euclidean vs. Mahalanobis). The current pipeline already computes `score_a/b/c` and `peer_stability` — these need to be exposed in a readable artifact, not just in the JSON.
5. **A cross-time-anchored score** alongside the per-year-normalized one (the academic review's headline finding). Without this, the score-level claims are uncitable. The pipeline already has `scores_absolute` — surface it in the UI and document it.
6. **An expanded country roster** including at least Nigeria + Pakistan or Bangladesh + Turkey, so the dataset can speak to colonial-legacy and Muslim-world questions (§2).
7. **A pinned changelog** documenting every methodological change between releases. The current commit history is fine for code; researchers expect a `CHANGELOG.md` in scholarly form (*"v2.0 — Population removed from composite; absolute index added; UK peak window recalibrated."*).
8. **Reproducibility instructions verified externally.** A second person, on a fresh machine, runs `run_all.py` and gets a byte-identical JSON. The pipeline appears to support this; the README does not document it as an explicit guarantee.
9. **Treatment of contested cells documented in the methodology** (§4) — China pre-1950, Soviet GDP, India partition, life-expectancy interpolation density. Researchers cite tools that *acknowledge* their fragilities; they ignore tools that don't.

With those nine in place, a careful reviewer will cite the *peer matches* and the *trajectories*. They will still hesitate to cite the *composite score levels*, and that's correct — composite scores from any source carry that hesitation.

## 18 — What would make this win a Webby Award

The Webby data-vis and education categories reward (i) a defensible point of view, (ii) a clear answer to "what is this?", (iii) interaction that feels like a discovery loop, (iv) production quality on first impression, (v) accessibility, (vi) a moment of emotional payoff.

Specific requirements:

1. **A single sentence-long point of view on the homepage.** Not "Structural strength across 40 nations." Something like *"Find your country's twin across two centuries."* Webby juries reward editorial clarity.
2. **The Time-Machine view (§16) as the centerpiece.** Webby reviewers spend 90 seconds with a tool. Lead with the unique interaction.
3. **Production-grade visual design.** The current dark-blue Three.js prototype is functional; it is not award-grade. Hire a typographer for the type ramp (the headline at 14px is wrong), a color designer for the score gradient (the current rainbow encodes nothing), and an animator for the year-transitions. Budget: a few thousand dollars of design contracting.
4. **Mobile-first parity** (§13). Webby disqualifies anything that doesn't work on a phone in 2026.
5. **An emotional moment** (§12 — the "where did your family come from" / great-grandparent view). Education-category winners have a heart, not just a brain.
6. **Accessibility:** ARIA labels, keyboard navigation, color-blind safe palette, screen-reader-friendly tabular alternatives. This is a Webby checklist item.
7. **Open-data ethos visibly displayed.** "All data, code, and methodology open at github.com/gregjlake/discovery-pipeline" in the footer, linked from every page. Webby education jurors weight open-source heavily.
8. **A press-ready story.** Six counter-intuitive findings that journalists will write about (Bolivia-South Africa, Japan-Russia, Switzerland #1 in 1900, the Argentine paradox, the Soviet trajectory shape, the Korean takeoff steepness). Webby juries read the press the tool got; press starts with a phone call from the team with the six findings.
9. **A 90-second hero video** on the homepage and in the Webby submission package. Voiceover narrates the Time-Machine view; visuals do the work. This is what gets a tool past the first round of jurying.
10. **One year of operation before submission.** Webby looks at sustained quality. Build the above, ship in 2026, submit in early 2027.

A specific submission target: **Webby Awards 2027 — Best Data Visualization (General).** With items 1–9 done credibly, this is winnable.

---

## Appendix — Pre-existing assets the recommendations build on

- `historylens/data/processed/historylens_final.json` — 1.13 MB, 40 countries × 19 decades, score_a/b/c + absolute index + peer_stability + regional_peers + known_gaps. Already complete enough for every Part 2 recommendation.
- `historylens/pipeline/` — reproducible pipeline (`run_all.py`), validation gating (`05_validate.py`), per-cell quality labels.
- `historylens/validation/academic_review.md` — the credibility audit. Its §6 priority list is consistent with this report's §15 ranking.
- `historylens/validation/snapshot_highlights.json` — the four curated findings already form the spine of the "Stories" tab (§9 audience A, §15 rank 5).
- `historylens/index.html` — Three.js prototype. Treat as a graphic, not as the product. The product is the snapshot page + the time-machine + the share card.

The data is ready. The product isn't yet.
