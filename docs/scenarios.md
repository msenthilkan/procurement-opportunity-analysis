# Scenario guide

The sample data is built so that **every rule in the queries fires at least once**. This page explains each scenario: what situation it represents, how the synthetic data creates it, which query handles it, and what you should see. `scripts/check_scenarios.py` verifies all 60 scenarios automatically; the latest run is in [simulation/scenario_results.md](simulation/scenario_results.md).

All data is synthetic. Supplier names such as `Supplier CR-1` are invented; the letters hint at the scenario (CR = courier, PC = pest control).

## How to run it

```
pip install pandas openpyxl matplotlib
python scripts/generate_sample_data.py      # writes sample-data/
python scripts/preview_dashboard.py         # Output, qOpportunities, P-card -> docs/simulation/
python scripts/preview_country_actions.py   # qCountryActions, qCommodityPlan -> docs/simulation/
python scripts/check_scenarios.py           # PASS/FAIL per scenario
```

The Python scripts re-implement the Power Query rules, so the same scenarios appear when you load `sample-data/` into Excel with the queries from `powerquery/`.

## How the sample data is built

The sample has three layers:

| Layer | What it contains | Why |
| --- | --- | --- |
| Random base | 1,400 requisitions across 8 countries and 22 commodities, with random catalogue, contract and approver patterns | Realistic volume and noise for the dashboard and Pareto |
| Low-value tail | 410 one-off requisitions under 500 (courier, training, venues, research, print) | Tests the P-card tail rule |
| **Scenario layer** | Scripted requisitions for 11 extra commodities, each built to trigger one specific rule | Makes every rule fire on purpose, with predictable results |

Each layer uses its own random seed, so adding a layer never changes the rows of the layers before it. The P-card statement (`qPCard.xlsx`) and the MCC map are generated on top; see the P-card section of the README.

The scope matrix for the sample (`sample-data/tblScopeMatrix.xlsx`, defined in `scripts/sample_scope_matrix.py`) gives each commodity a scope tier and proposed route. Three taxonomy rows are deliberately left out of it to test the "not classified" path.

### Scenario commodities

| Commodity | Tier | What the scripted data does | Scenario it tests |
| --- | --- | --- | --- |
| Protective Workwear | A | Catalogue with Supplier WW-1 in UAE, but UAE also buys from WW-1 off-catalogue | Leakage |
| Courier Services | A | Catalogue with Supplier CR-1 in USA only; Turkey buys from CR-1 off-catalogue | Extend agreement |
| Pest Control Services | A | Contract with PC-1 in Germany; Turkey uses PC-2, South Africa PC-3 | Replicate |
| Digital Analytics Services | B | No agreement anywhere; DA-1 is the top supplier in USA, UAE and Turkey | Regional deal |
| Translation Services | A | No agreement; 30 small lines, different supplier per country | New agreement; category route overrides "Catalogue" |
| Corporate Strategy Advisory | C | Two large lines in USA, no agreement | Business-led |
| Customer Rebates | E | 24 lines of 80k in four countries, raised as requisitions | Non-addressable exclusion |
| Office Rent | E | Monthly rent in Germany and UAE; one line has no approver | Non-addressable; no approval data |
| Laboratory Supplies | none | In the taxonomy but not in the scope matrix | Classify first |
| Lab Testing - Microbiology / - Chemistry | none | Both have the short name "Lab Testing"; spend uses that short name | Ambiguous taxonomy match |
| Office Supplies (BR01) | A | Three lines from purchasing org BR01, which is not in CountryMap | Country not mapped |

### How these map to your real taxonomy

| Sample scenario | Typical real L3s with the same pattern |
| --- | --- |
| Customer Rebates (E) | Sales Rebates, Trade Agent Fees & Commissions, Marketing Campaign Contribution, In-Store Marketing Support |
| Office Rent (E) | Rent / Lease, Office/building rent and common area maintenance, Lease of Warehouse |
| Freight, Hotels (D) | Road, Air, Airfare, Hotel Accommodation, Car Rental, Meals (External), Diesel & Gasoline |
| Corporate Strategy Advisory (C) | Corporate Strategy Consulting, Post-Merger Integration Consulting, Tax Advisory Services, Litigation |
| Digital Analytics Services (B, regional) | Any agency or service bought from the same supplier in several countries |
| Laboratory Supplies (not classified) | Any taxonomy L3 that was not in your list of 188 |
| Lab Testing (ambiguous) | Two taxonomy rows that share a short name |

## Scenario catalogue

### A. Data quality and matching (`Output.pq`)

| ID | Scenario | How the data creates it | What you see |
| --- | --- | --- | --- |
| A1 | Requester picked the L3 short name | Half the random lines use the short name | Matched like the long name; `Taxonomy Match = Matched` |
| A2 | Commodity not in taxonomy | "Miscellaneous Services", "Other Goods" | `Taxonomy Match = Unmapped`; commodity shows "(not in taxonomy)" |
| A3 | Short name belongs to two L3s | "Lab Testing" | `Taxonomy Match = Ambiguous`; no L3 is picked at random |
| A4 | New country not yet in CountryMap | Purchasing org BR01 | `Country = BR01 (not mapped)`; add the code to CountryMap |
| A5 | Approver not in user master | "Former Employee" on about 2% of requisitions | Name appears in `Approvers Not In List` |
| A6 | Same person twice in user master | One active and one inactive account | The active account's email is used |
| A7 | Text dates in M/D/YYYY | All exports | Parsed month-first; 8/11 = 11 August |

### B. Buying channels (`Output.pq`, `qPCardOut.pq`, `qAllSpend.pq`)

| ID | Scenario | What you see |
| --- | --- | --- |
| B1-B4 | Catalogue, contract-linked, non-catalogue and service ("Unclassified") lines | One `Buying Channel` per line; pivots always reconcile |
| B5 | Low-value PO paid by card | `Buying Channel = P-card on PO` |
| B6 | Card bought outside Ariba | `Buying Channel = P-card (off-platform)` |
| B7 | Card-paid PO also on the card statement | 309 of 1,457 card transactions removed, so nothing is counted twice |

Without a card programme, `qAllSpend` uses Output only and B5-B7 simply never occur.

### C. Approval routes (`Output.pq`)

| ID | Scenario | What you see |
| --- | --- | --- |
| C1 | Only business/finance approved | `Approval Route = Business/Finance only` |
| C2 | Procurement and business approved | `Procurement + Business/Finance` |
| C3 | Only procurement approved (2 Workwear lines) | `Procurement only` |
| C4 | Requisition missing from the approver export (1 Office Rent line) | `No approval data` |

### D. Scope tiers (`qTaxonomyPolicy.pq`)

| ID | Tier | Sample commodities | Meaning |
| --- | --- | --- | --- |
| D1 | A. Procurement-led | Office supplies, cleaning, courier, workwear, translation | Procurement owns the catalogue/contract |
| D2 | B. Co-managed | Media, consulting, software, digital analytics | Business chooses from a procurement-built frame |
| D3 | C. Business-led | Legal, corporate strategy advisory | Business selects; procurement reviews terms |
| D4 | D. Other channel | Freight, hotels | Travel tool / TMS; report separately |
| D5 | E. Out of scope | Customer rebates, office rent | Non-addressable |
| D6 | Not classified | Laboratory supplies, unmapped and ambiguous lines | No scope decision yet |

### E. Opportunity ranking (`qOpportunities.pq`)

| ID | Scenario | Rule | Result in the sample |
| --- | --- | --- | --- |
| E1 | Tier D/E spend | `ExcludeTiers = {"D","E"}` removes it before ranking | Rebates, rent, freight and hotels are not in the list (34 commodities remain) |
| E2 | Many small lines, but the playbook is a contract | Frequency rule says "Catalogue"; the category route replaces it | Translation: "Contract: rate card (per word/hour)" |
| E3 | Tier C | Category route always wins | Corporate strategy: "Engagement letter + PO; procurement commercial review" |
| E4 | Playbook allows a catalogue | Frequency rule kept | Office supplies: "Catalogue" |
| E5 | Small, mostly-on-card tail in an Allowed category | P-card tail rule | 4 commodities get a P-card route |
| E6 | Card spend at cash, bar or gambling MCCs | Prohibited rule | "Prohibited: follow up with cardholder" |

### F. Country actions (`qCountryActions.pq`)

The query checks these rules in order and takes the first that applies, so every country × commodity gets exactly one action:

| Order | Action type | Rule | Sample example (ID) |
| --- | --- | --- | --- |
| 1 | Exclude (non-addressable) | Tier E | Germany × Customer Rebates, Germany × Office Rent (F10, F11) |
| 2 | Exclude (other channel) | Tier D | Freight and hotels in every country (F15) |
| 3 | Classify first | No scope tier | Germany × Laboratory Supplies; USA × Lab Testing (F12, F13) |
| 4 | Quick win: leakage | Top off-catalogue supplier already has a catalogue/contract **in this country** | UAE × Protective Workwear: "Supplier WW-1 already has a catalogue in UAE …, yet 85% of this off-catalogue spend still goes to Supplier WW-1 outside it." (F1) |
| 5 | Quick win: extend agreement | That supplier has a catalogue/contract **in another country** | Turkey × Courier Services: "Supplier CR-1 is already on catalogue in USA; extend that agreement to Turkey." (F2) |
| 6 | Replicate other country | The commodity is on catalogue/contract elsewhere with **another supplier** | Turkey × Pest Control: "… already on contract in Germany (Supplier PC-1); use that set-up for Turkey." (F3, F4) |
| 7 | Regional deal | Same top supplier off-catalogue in 2+ countries, no agreement anywhere | USA × Digital Analytics: "Supplier DA-1 is the top off-catalogue supplier … in 3 countries; negotiate one regional agreement." (F5, F6) |
| 8 | Business-led | Tier C | USA × Corporate Strategy Advisory (F9) |
| 9 | New agreement | None of the above; uses the matrix playbook steps | Germany and Canada × Translation Services (F7, F8) |

Why this order: a quick win needs no sourcing, only a change in buying behaviour or a contract extension, so it is the fastest saving. Replicating a proven set-up is faster than a new tender. A regional deal is worth more than several local ones.

**Priority** is set within each country over addressable rows only: High for the commodities that make up the first 50% of that country's addressable off-catalogue spend, Medium up to 80%, Low after that. Excluded rows always show `Priority = Excluded` (F16). In the sample: 20 High, 33 Medium, 120 Low, 22 Excluded.

The BR01 row (F14) shows the actions still work for an unmapped country: office supplies are on catalogue elsewhere, so the action is "Replicate other country".

### G. Commodity plan (`qCommodityPlan.pq`)

| ID | Scenario | Result in the sample |
| --- | --- | --- |
| G1 | Bought off-catalogue in 3+ countries | Digital Analytics: "Target one regional agreement covering 3 countries (start with USA, UAE, Turkey), via Contract: agency roster + SOW per project." |
| G2 | Bought in fewer than 3 countries | Translation: "Target local agreements in Germany, Canada …" |
| G3 | Countries that can copy a set-up | Pest Control: "Copy an existing country set-up for South Africa, Turkey." |
| G4 | Countries with quick wins | Courier: Quick Win Countries = Turkey |
| G5 | Tier E | Office Rent: "Exclude: non-addressable …" |
| G6 | Not classified | Laboratory Supplies: "Classify first …" |

### H. P-card compliance (`qPCardOut.pq`, optional module)

| ID | Flag | How the simulation creates it | Status |
| --- | --- | --- | --- |
| H1 | Blocked category | Card used for consulting, legal, cleaning, hotels and similar | Non-compliant |
| H2 | Restricted category | Office supplies, IT, software on card | Review |
| H3 | Over single limit | About 3% of transactions above 2,500 | Non-compliant |
| H4 | Possible split | 20 cases of 2-3 buys, same cardholder, merchant and day | Non-compliant |
| H5 | Catalogue/contract supplier | About 8% of card buys from a supplier with a catalogue or contract | Non-compliant |
| H6 | Missing receipt | About 8% of transactions | Review |
| H7 | No flag | Everything else | Compliant |

## Behaviours to confirm in Excel

These depend on Power Query itself, so the Python mirror cannot test them:

| Behaviour | How to confirm |
| --- | --- |
| qTaxonomy replaces only the columns the matrix has | The sample matrix has no P-card Policy column, so qTaxonomy keeps the taxonomy's own P-card Policy |
| P-card logic switches off without card data | Leave `qAllSpend` on `Combined = Output` with a spend export that has no payment-method column: qOpportunities has no P-card columns |
| No Formula.Firewall error | qTaxonomy reads the matrix through the `tblScopeMatrix` query, not `Excel.CurrentWorkbook()` |
| Older matrix headers accepted | A matrix with `L3 Long` / `Proposed Scope Tier` / `Proposed Execution` still loads |
