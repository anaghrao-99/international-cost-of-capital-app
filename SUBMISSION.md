# Submission: International Cost of Capital

- Name / course / date: [fill in]
- GitHub repository: [actual URL after upload]
- Deployed app: [actual URL after deployment]
- Selected industry / country / currency / tax jurisdiction: [fill in]
- ERP / debt share: [fill in]
- Data observation dates: beta [ ], BBB spread [ ], tax year [ ], US 10y [ ], target 10y [ ]; retrieval UTC [ ].
- Manual inputs/proxies and source links: [fill in; include reasons].
- Results: USD Ke [ ], Kd [ ], WACC [ ]; target Ke [ ], Kd [ ], WACC [ ].
- Attach exported audit JSON, results CSV, and verification calculator output/screenshot.

Verification: equal yields [pass/date]; zero debt [pass/date]; foreign-spread isolation [pass/date]. Hypothetical sample gives USD WACC 10.65125% and target WACC 13.6267668269%.

Method: relever US industry beta using target D/E and selected statutory tax; CAPM in USD; convert equity/debt with `(1 + target government yield)/(1 + US government yield)`; apply capital weights and tax shield. Foreign credit spread override affects foreign debt only. Assumes zero debt beta, full tax-shield use, no additional country risk premium. Government-yield conversion is a proxy, not an FX or inflation forecast. Confirmed against class formulas: [describe any differences and adjustments].

Limitations and source failures encountered: [fill in]. I independently checked calculations and input definitions using the included calculator: [date/details].
