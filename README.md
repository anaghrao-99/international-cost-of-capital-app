# International Cost of Capital

A GitHub-ready Streamlit project comparing USD and target-country currency equity costs, debt costs, and WACC. Includes industry comparisons, source diagnostics, input overrides, CSV/JSON exports, an independent offline calculator, and calculation tests. No API keys, fabricated observations, or preloaded market snapshots.

## Run locally

Use Python 3.11 or 3.12 (recommended).

```sh
python -m venv .venv
source .venv/bin/activate
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Defaults: Software (System & Application), United States target country, United States tax jurisdiction, 6.5% USD ERP, 30% debt. Source-derived fields have no invented defaults. If a source fails, enable its manual override and enter a verified observation; zero is only used when explicitly entered by the user. OECD series must be confirmed before use.

## Sources and refresh

| Input | Source | Adapter / safeguards |
|---|---|---|
| US industry unlevered beta | [Damodaran XLS](https://pages.stern.nyu.edu/~adamodar/pc/datasets/betas.xls) | Detects Industry Name header; uses exact Unlevered beta, not cash-adjusted beta; workbook preamble shown as date context. |
| USD BBB/Baa2 spread | [Large nonfinancial firms table](https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/ratings.htm) | First large-firm panel, exact Baa2/BBB and adjacent percent. Canonical `.htm` replaces assignment's `.html` URL. |
| Statutory tax | [OECD database](https://www.oecd.org/en/data/datasets/corporate-income-tax-rates-database.html) / [SDMX flow](https://sdmx.oecd.org/public/rest/v1/data/OECD.CTP.TPS,DSD_TAX_CIT@DF_CIT,2.0/.) | Latest numeric year within selected country/series; exposes dimensions for explicit confirmation of standard combined central + subcentral rate. Never guesses central-only vs combined or SME rate. |
| US/target 10-year yield | [Trading Economics bonds](https://tradingeconomics.com/bonds) | Parses explicitly named actual/yield/last table columns; retains row date and country detail link. No forecast parsing. |

All requests use timeouts and HTTP status checks. Cached for one hour; **Refresh all source data** clears the cache and retries all sources. Retrieval UTC is distinct from observation date. Where a publication date cannot be parsed it is marked unavailable; never relabel retrieval as publication. The current URL is requested on each refresh, but no claim is made that it is a real-time quote or the newest observation available elsewhere. Source outages and schema changes appear in diagnostics.

Trading Economics can return dynamic HTML, robots restrictions, or 403/429 without an API key. This app does not bypass access controls. On failure use the linked source in a browser and manually enter the latest actual 10-year observation with date. OECD can block requests or change dataflow versions: download an original SDMX CSV with `REF_AREA`, `TIME_PERIOD`, `OBS_VALUE`, and dimension columns, upload it, select/confirm the correct series, or manually override tax. If beta/spread parsing fails, manual input is required. Manual overrides are never described as fetched data and take priority after refresh. Clear an override to restore fetched values. Manual notes are warnings, not enforced gates.

The country selector covers ISO countries; automatic yield coverage is limited to countries the source actually quotes. Unmatched aliases or countries with no 10-year benchmark require manual input and a disclosed proxy. Verify the benchmark's currency: euro-area countries share EUR, and some countries use USD or quote foreign-currency bonds. The app labels the target by country rather than inventing a currency assignment.

## Methodology

Class formulas were absent from the available reference. This is an explicit, reviewable model, **not a claim that the instructor supplied these equations**. Confirm before submission. All rates below are decimals.

For unlevered beta `bu`, debt fraction `d`, tax rate `t`, US yield `ru`, foreign yield `rf`, USD spread `s`, and USD ERP `p`:

```text
D/E = d/(1-d)
bL = bu * [1 + (1-t)*D/E]
Ke_USD = ru + bL*p
Kd_USD = ru + s
q = (1+rf)/(1+ru)
Ke_foreign = (1+Ke_USD)*q - 1
s_foreign_auto = s*q
Kd_foreign = rf + (manual foreign spread if enabled, else s_foreign_auto)
WACC_currency = (1-d)*Ke_currency + d*Kd_currency*(1-t)
```

Thus automatic foreign debt also equals `(1+Kd_USD)*q-1`. Foreign spread override changes foreign debt and foreign WACC only. It is a credit spread **above the selected foreign government yield**, not the total borrowing cost.

Assumptions: debt beta zero; market-value target capital weights; full use of statutory tax shield; constant leverage; same selected tax rate in both currency calculations. OECD standard combined statutory rate proxies the marginal tax rate. Tax jurisdiction is separate from target country/currency. No separate sovereign/country risk premium is added.

The government-yield ratio is an assumed nominal currency conversion proxy, not a measured inflation ratio or an FX forecast. Sovereign yields embed default, liquidity, and other risks, so the proxy is imperfect. Discount nominal cash flows in the matching currency. Convert equity and pre-tax debt, then weight and apply the tax shield. Directly converting USD WACC would produce a different tax-shield treatment and is intentionally not the model used here.

Debt must be below 100%; yields can be negative but above -100%; beta/ERP/spreads nonnegative. Extreme inputs are permitted within UI bounds and need economic judgment. Industry comparison uses each fetched industry beta with current tax, debt, ERP, yields and spreads; it does not apply the selected industry's manual beta to every industry.

## Independent verification

Open `verification.html` directly in any modern browser. It works offline with editable inputs, independently implemented JavaScript equations, and a hand-audit sample. It imports nothing from `model.py`; its hypothetical sample is not market data.

```sh
python -m unittest discover -s tests -v
```

Required invariants: equal yields + automatic spread ⇒ equal currency costs; zero debt ⇒ beta equals unlevered beta and WACC equals equity; foreign spread override ⇒ no change to USD metrics or foreign equity. Numerical sample: beta 1.1, tax 25%, ERP 6.5%, debt 30%, US yield 4%, target yield 7%, USD spread 1.5% ⇒ USD WACC **10.6512500000%**, target WACC **13.6267668269%**. See calculator for intermediate values.

## Deploy to Streamlit Community Cloud

1. Unzip the project and create a GitHub repository in your own account. Upload the **contents** of this folder, including app.py and requirements.txt at the repository root (or select the corresponding subfolder path at deployment).
2. Sign in at [Streamlit Community Cloud](https://share.streamlit.io/), choose Create app, select repository/branch, and set main file path to `app.py`.
3. Choose Python 3.11 or 3.12 in deployment settings and deploy. See the [official deployment guide](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy). No secrets required.
4. Check source diagnostics from the deployed environment; source access there may differ from your laptop. Refresh, supply any verified manual inputs, export the audit, and verify the numerical sample in the independent calculator.
5. Insert the actual GitHub and deployment URLs in `SUBMISSION.md` only after creating them.

No actual repository or deployed URL is created by distributing this package. Dependency ranges allow security/patch updates; for a reproducible class submission, record installed versions (`pip freeze`) after testing in your environment.

## Validation status for this package

Calculation tests and Python compilation are run during packaging. Network source adapters are defensive, but live fetching depends on provider availability and schema. Live checks on November 16, 2026 retrieved the Damodaran beta workbook and spread, and 13,752 OECD observations after using its supported `text/csv` response format. Trading Economics returned no usable table and its US detail page returned HTTP 403; no yield was substituted. Eleven automated tests passed, including Streamlit app tests of the missing-source/manual-input workflow and fetched-data industry comparison. End-to-end live yield retrieval remains unverified; missing-data/manual workflows are part of the design. Do not submit without checking fetched data, dates, selected OECD series, and instructor methodology in your deployment.
