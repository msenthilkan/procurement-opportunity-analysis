# Setup guide

Builds the workbook from the five input files. Works in Excel for Microsoft 365 or Excel 2019+ on Windows.

## 1. Folder

Put the five files from `sample-data/` (or your own exports with the same columns) in one folder, then create a new workbook in the same folder, for example `Spend Opportunity Report.xlsx`. All queries, pivots and the dashboard live in this workbook.

| File | Query name | Contents |
| --- | --- | --- |
| qSpend.xlsx | `qSpend` | One row per requisition line |
| qApproverRaw.xlsx | `qApproverRaw` | Each line repeated once per approver |
| qTaxonomy.xlsx | `qTaxonomy` | Category taxonomy, Level 0 to Level 3 |
| qUserMaster.xlsx | `qUserMaster` | User names, active flag and email |
| tblProcurementGroup.xlsx | `qProcurementGroup` | One column, `Email`, listing procurement approvers |

## 2. Load the five inputs

For each file:

1. **Data → Get Data → From File → From Workbook**, pick the file, select its sheet or table, then **Transform Data**.
2. If headers show as Column1, Column2 and so on, use **Home → Use First Row as Headers**.
3. **Delete the automatic "Changed Type" step.** It hard-codes every column name and breaks when an export changes. The Output query handles types itself.
4. Rename the query as in the table above.

## 3. Add the two queries

For `Output` and then `qOpportunities`:

1. **Home → New Source → Other Sources → Blank Query**.
2. **Advanced Editor**, delete everything, and paste the matching file from `powerquery/`.
3. Rename the query to `Output` or `qOpportunities`.

In `Output.pq`, check the settings block at the top: the taxonomy code column, the user master name and email columns, and the `CountryMap` codes.

## 4. Load destinations

- **Close & Load To… → Only Create Connection** for the five inputs.
- `Output` → **Table** on a new sheet. Confirm the table name is `Output` (**Table Design → Table Name**).
- `qOpportunities` → **Table** on a new sheet named `Opportunities`.

## 5. Checks after each refresh

- [ ] Row count of Output equals the spend export (the joins never add rows).
- [ ] Total spend equals the source report total.
- [ ] `Taxonomy Match` other than Matched: add the missing commodities to the taxonomy.
- [ ] `Approvers Not In List`: names not found in the user master.
- [ ] `Country` values ending in "(not mapped)": add the code to `CountryMap`.

## Monthly refresh

Save new exports over the same files, then **Data → Refresh All** twice (queries first, then pivots).

## Troubleshooting

| Message | Fix |
| --- | --- |
| The column '…' of the table wasn't found | A column name differs from the code. If it is in an input query, delete its Changed Type step. If it is in Output, update the settings block. |
| Token 'else' expected | A partial paste lost a line. Replace the whole query with the file from `powerquery/`. |
| Month shows the wrong month | Source dates are M/D/YYYY. Leave `ToDate` on `en-US` unless your export differs. |
| Lines / Avg Spend per Line show Error | Fixed in `qOpportunities.pq`: it falls back to counting rows when `sum(Line Count)` is missing or text. |
