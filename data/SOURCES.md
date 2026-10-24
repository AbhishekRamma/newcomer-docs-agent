# Sources

Twenty official government pages. The ingest script fetches them into the gitignored `data/local/` folder. **No page text is committed to this repository.** Only the URLs below and my own code are.

- **Fetched:** 2026-10-24 (America/Toronto), with `python -m src.ingest` (httpx first, headless Chrome as a fallback).
- **Page updated:** the "Date modified" (Canada.ca) or "Updated" (ontario.ca) value printed on the page at fetch time. "—" means the page did not show one.
- **Reuse terms:** checked against each site's general terms on 2026-10-24. I did not check every page for page-specific notices, so the per-page status is marked **unverified**.

| id | topic | owner | URL | page updated | fetched | reuse terms |
|---|---|---|---|---|---|---|
| s01 | sin | Employment and Social Development Canada (Service Canada) | <https://www.canada.ca/en/employment-social-development/services/sin.html> | 2026-10-09 | 2026-10-24 | Canada.ca terms (see note A); unverified |
| s02 | sin | Employment and Social Development Canada (Service Canada) | <https://www.canada.ca/en/employment-social-development/services/sin/apply.html> | 2026-07-15 | 2026-10-24 | Canada.ca terms (see note A); unverified |
| s03 | sin | Employment and Social Development Canada (Service Canada) | <https://www.canada.ca/en/employment-social-development/services/sin/required-documents.html> | 2026-05-20 | 2026-10-24 | Canada.ca terms (see note A); unverified |
| s04 | ohip | Government of Ontario, Ministry of Health / ServiceOntario | <https://www.ontario.ca/page/apply-ohip-and-get-health-card> | July 21, 2025 | 2026-10-24 | Crown copyright, King's Printer for Ontario (see note B); OGL-Ontario unverified |
| s05 | ohip | Government of Ontario, Ministry of Health | <https://www.ontario.ca/page/what-ohip-covers> | April 22, 2026 | 2026-10-24 | Crown copyright, King's Printer for Ontario (see note B); OGL-Ontario unverified |
| s06 | ohip | Government of Ontario, Ministry of Health / ServiceOntario | <https://www.ontario.ca/page/health-card-renewal> | October 23, 2026 | 2026-10-24 | Crown copyright, King's Printer for Ontario (see note B); OGL-Ontario unverified |
| s07 | ohip | Government of Ontario, Ministry of Health | <https://www.ontario.ca/page/ohip-coverage-while-outside-canada> | January 16, 2026 | 2026-10-24 | Crown copyright, King's Printer for Ontario (see note B); OGL-Ontario unverified |
| s08 | banking | Financial Consumer Agency of Canada | <https://www.canada.ca/en/financial-consumer-agency/services/banking/opening-bank-account.html> | — | 2026-10-24 | Canada.ca terms (see note A); unverified |
| s09 | banking | Financial Consumer Agency of Canada | <https://www.canada.ca/en/financial-consumer-agency/services/banking/bank-accounts/low-cost-no-cost.html> | — | 2026-10-24 | Canada.ca terms (see note A); unverified |
| s10 | tax | Canada Revenue Agency | <https://www.canada.ca/en/revenue-agency/services/tax/international-non-residents/individuals-leaving-entering-canada-non-residents/newcomers-canada-immigrants.html> | 2026-08-03 | 2026-10-24 | Canada.ca terms (see note A); unverified |
| s11 | tax | Canada Revenue Agency | <https://www.canada.ca/en/revenue-agency/services/tax/international-non-residents/individuals-leaving-entering-canada-non-residents/newcomers-canada-immigrants/completing-return-newcomers.html> | 2026-09-17 | 2026-10-24 | Canada.ca terms (see note A); unverified |
| s12 | tax | Canada Revenue Agency | <https://www.canada.ca/en/services/taxes/income-tax/personal-income-tax/who-should-file-tax.html> | 2026-01-20 | 2026-10-24 | Canada.ca terms (see note A); unverified |
| s13 | tax | Canada Revenue Agency | <https://www.canada.ca/en/revenue-agency/services/tax/individuals/topics/important-dates-individuals.html> | 2026-09-17 | 2026-10-24 | Canada.ca terms (see note A); unverified |
| s14 | tax | Canada Revenue Agency | <https://www.canada.ca/en/revenue-agency/news/newsroom/tax-tips/tax-tips-2026/tax-tip-taxes-made-simple-newcomers-canada.html> | 2026-03-10 | 2026-10-24 | Canada.ca terms (see note A); unverified |
| s15 | tax | Canada Revenue Agency | <https://www.canada.ca/en/revenue-agency/services/child-family-benefits/canada-groceries-essentials-benefit/who-eligible.html> | 2026-03-02 | 2026-10-24 | Canada.ca terms (see note A); unverified |
| s16 | tax | Canada Revenue Agency | <https://www.canada.ca/en/revenue-agency/services/child-family-benefits/canada-groceries-essentials-benefit/get-benefit.html> | 2026-06-08 | 2026-10-24 | Canada.ca terms (see note A); unverified |
| s17 | driving | Government of Ontario, Ministry of Transportation | <https://www.ontario.ca/page/exchange-out-province-drivers-licence> | September 23, 2026 | 2026-10-24 | Crown copyright, King's Printer for Ontario (see note B); OGL-Ontario unverified |
| s18 | driving | Government of Ontario, Ministry of Transportation | <https://www.ontario.ca/page/get-g-drivers-licence-new-drivers> | September 11, 2026 | 2026-10-24 | Crown copyright, King's Printer for Ontario (see note B); OGL-Ontario unverified |
| s19 | driving | Government of Ontario, Ministry of Transportation | <https://www.ontario.ca/document/official-mto-drivers-handbook/getting-your-drivers-licence> | September 14, 2026 | 2026-10-24 | Crown copyright, King's Printer for Ontario (see note B); OGL-Ontario unverified |
| s20 | id | Government of Ontario / ServiceOntario | <https://www.ontario.ca/page/ontario-photo-card> | October 23, 2026 | 2026-10-24 | Crown copyright, King's Printer for Ontario (see note B); OGL-Ontario unverified |

**Note A, Canada.ca.** Canada.ca [Terms and conditions](https://www.canada.ca/en/transparency/terms.html): non-commercial reproduction allowed with attribution and a link to the original. Page-specific copyright notices not checked: **unverified**.

**Note B, ontario.ca.** Crown copyright, © King's Printer for Ontario ([copyright page](https://www.ontario.ca/page/copyright-information)): non-commercial reproduction allowed with credit and no changes. Whether this page carries an Open Government Licence – Ontario label: **unverified**.

## How this repo uses the pages

- The pages are fetched and stored only on the machine that runs the code. The `data/local/` folder is gitignored.
- At answer time, the agent quotes or paraphrases short passages. Each one cites its chunk id and the original URL.
- CI does not use these pages. It uses short fixture documents I wrote myself in `ci/fixtures/docs/` (CC0). They keep the real URLs only as identifiers.
- `eval_runs/*/per_question.jsonl` stores ids, routes, cited URLs and any missing key facts. It does not store answer text. The full answers are kept in the gitignored `data/local/eval_answers/`.
