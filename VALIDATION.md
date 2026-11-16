# Validation record — November 16, 2026

- 11 automated tests passed: five model checks, four source-adapter fixture checks, and two Streamlit AppTest workflows (manual operation when every source fails; fetched tax selection/results/industry comparison).
- All Python files compiled successfully using Python's compile function.
- The independent HTML calculator's JavaScript was executed separately: numerical sample, equal yields, and zero debt passed. The calculator does not import the Python model.
- Required foreign spread isolation test passed: USD equity/debt/WACC and foreign equity stayed unchanged; foreign WACC changed by debt fraction × (1−tax) × change in foreign credit spread.
- Hypothetical numerical sample: beta 1.1, tax 25%, ERP 6.5%, debt 30%, yields 4%/7%, USD spread 1.5%. Levered beta 1.4535714286; USD equity 13.4482142857%, debt 5.5%, WACC 10.65125%; target equity 16.7207589286%, debt 8.5432692308%, WACC 13.6267668269%.
- Live Damodaran workbook retrieved after fixing multi-sheet detection; workbook update date January 5, 2026. BBB/Baa2 large-firm spread retrieved (1.11% at check time); table observation/publication date was not available. These are validation observations, not bundled app defaults.
- OECD live CSV retrieved using Accept: text/csv; 13,752 rows. Other attempted response headers produced server errors. App uses the working format and requires series confirmation.
- Trading Economics bonds HTML did not expose a usable yield table; US detail page returned HTTP 403. Live yield retrieval could not be verified. App correctly requires manual input instead of substituting values.

Local execution used Python 3.9 with Streamlit 1.50 and pandas 2.3.3. Python 3.11/3.12 is recommended for deployment; a GitHub Actions check is included for Python 3.11. No real GitHub repository or deployment was created. No full browser visual inspection or production deployment test is claimed. Confirm class formulas and validate live input definitions/dates before submission.
