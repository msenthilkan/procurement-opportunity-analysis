"""Checks that the synthetic sample data triggers every scenario the queries handle.

Run after the other three scripts:
    python scripts/generate_sample_data.py
    python scripts/preview_dashboard.py
    python scripts/preview_country_actions.py
    python scripts/check_scenarios.py

Prints PASS/FAIL per scenario and writes docs/simulation/scenario_results.md.
Scenario IDs match docs/scenarios.md. Exits with code 1 if any scenario fails.
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA, SIM = ROOT / "sample-data", ROOT / "docs" / "simulation"


def key(s):
    return " ".join(str(s).replace("\u00a0", " ").split()).lower() if pd.notna(s) else ""


dq = pd.read_csv(SIM / "data_quality_summary.csv")
opp = pd.read_csv(SIM / "opportunities.csv")
ca = pd.read_csv(SIM / "country_actions.csv")
cp = pd.read_csv(SIM / "commodity_plan.csv")
flags = pd.read_csv(SIM / "pcard_flag_summary.csv", keep_default_na=False).set_index("Flag")
spend = pd.read_excel(DATA / "qSpend.xlsx", dtype=str)
tax = pd.read_excel(DATA / "qTaxonomy.xlsx")
users = pd.read_excel(DATA / "qUserMaster.xlsx")
card = pd.read_excel(DATA / "qPCard.xlsx", dtype={"PO Reference": str})


def dq_lines(check, value):
    row = dq[(dq["Check"] == check) & (dq["Value"].astype(str) == value)]
    return int(row["Lines"].iloc[0]) if len(row) else 0


def action(country, commodity):
    row = ca[(ca["Country"] == country) & (ca["Commodity"] == commodity)]
    return row["Action Type"].iloc[0] if len(row) else "(no row)"


def opp_col(commodity, col):
    row = opp[opp["Commodity"] == commodity]
    return row[col].iloc[0] if len(row) else None


def plan(commodity, col="Recommended Approach"):
    row = cp[cp["Commodity"] == commodity]
    return str(row[col].iloc[0]) if len(row) else ""


short_names = set(tax["Level 3 (Commodity) - Short"].map(key)) - set(tax["Level 3 (Commodity) - Long"].map(key))
short_used = spend["[REQ]Commodity (Commodity (L3))"].map(key).isin(short_names).sum()
dup = users[users.duplicated("Name", keep=False)]
dates_ok = pd.to_datetime(spend["[REQ]Requisition Date (Date)"], format="%m/%d/%Y", errors="coerce").notna().all()
card_po = card["PO Reference"].fillna("").map(key)
po_ids = set(spend["[REQ] PO Id"].map(key))
card_paid_pos = int(card_po.isin(po_ids - {""}).sum())
excluded = ["Customer Rebates", "Office Rent", "Freight Forwarding", "Hotels and Accommodation"]
translation_lines = spend["[REQ]Commodity (Commodity (L3))"].eq("Translation Services").sum()

S = []   # (id, area, scenario, expected, actual, passed)


def check(sid, area, scenario, expected, actual, passed):
    S.append((sid, area, scenario, expected, str(actual), bool(passed)))


# ---- A. Data quality and matching (Output.pq)
check("A1", "Matching", "Spend uses the L3 short name", "short-name lines are matched", f"{short_used} lines", short_used > 0)
check("A2", "Matching", "Commodity not in taxonomy", "Taxonomy Match = Unmapped", f"{dq_lines('Taxonomy Match', 'Unmapped')} lines",
      dq_lines("Taxonomy Match", "Unmapped") > 0)
check("A3", "Matching", "Short name shared by two L3s (Lab Testing)", "Taxonomy Match = Ambiguous",
      f"{dq_lines('Taxonomy Match', 'Ambiguous')} lines", dq_lines("Taxonomy Match", "Ambiguous") == 3)
check("A4", "Matching", "Purchasing org BR01 not in CountryMap", "Country = 'BR01 (not mapped)'",
      f"{dq_lines('Country', 'Country not mapped')} lines", dq_lines("Country", "Country not mapped") == 3)
check("A5", "Matching", "Approver missing from user master", "listed in Approvers Not In List",
      f"{dq_lines('Approvers', 'Requisitions with approver not in user master')} requisitions",
      dq_lines("Approvers", "Requisitions with approver not in user master") > 0)
check("A6", "Matching", "Same name twice in user master (one inactive)", "active account's email is used",
      f"{len(dup)} rows for {dup['Name'].iloc[0] if len(dup) else '-'}", len(dup) == 2 and set(dup["Active"]) == {"Yes", "No"})
check("A7", "Matching", "Text dates in M/D/YYYY", "all dates parse month-first", "all parse" if dates_ok else "some fail", dates_ok)

# ---- B. Buying channels (Output.pq, qPCardOut.pq, qAllSpend.pq)
for sid, ch in [("B1", "Catalogue"), ("B2", "Contract"), ("B3", "Non-catalogue"), ("B4", "Unclassified"),
                ("B5", "P-card on PO"), ("B6", "P-card (off-platform)")]:
    check(sid, "Channel", f"Buying Channel = {ch}", "lines exist", f"{dq_lines('Buying Channel', ch)} lines",
          dq_lines("Buying Channel", ch) > 0)
check("B7", "Channel", "Card-paid Ariba PO also on card statement", "removed from card feed (no double count)",
      f"{card_paid_pos} removed; {dq_lines('Buying Channel', 'P-card (off-platform)')} card lines kept of {len(card)}",
      dq_lines("Buying Channel", "P-card (off-platform)") == len(card) - card_paid_pos)

# ---- C. Approval routes (Output.pq)
for sid, r in [("C1", "Business/Finance only"), ("C2", "Procurement + Business/Finance"), ("C3", "Procurement only"),
               ("C4", "No approval data")]:
    check(sid, "Approval", f"Approval Route = {r}", "lines exist", f"{dq_lines('Approval Route', r)} lines",
          dq_lines("Approval Route", r) > 0)

# ---- D. Scope tiers (qTaxonomyPolicy.pq)
for sid, t in [("D1", "A"), ("D2", "B"), ("D3", "C"), ("D4", "D"), ("D5", "E"), ("D6", "Not classified")]:
    check(sid, "Scope tier", f"Scope Tier {t}", "lines exist", f"{dq_lines('Scope Tier', t)} lines", dq_lines("Scope Tier", t) > 0)

# ---- E. Opportunity ranking (qOpportunities.pq)
present = [c for c in excluded if c in set(opp["Commodity"])]
check("E1", "Opportunities", "Tier D/E commodities", "left out of the ranking", "none present" if not present else present, not present)
tr_route = opp_col("Translation Services", "Suggested Route")
check("E2", "Opportunities", f"Many small lines ({translation_lines}) but playbook is a contract", "category route replaces 'Catalogue'",
      tr_route, isinstance(tr_route, str) and "rate card" in tr_route)
cs_route, cs_cat = opp_col("Corporate Strategy Advisory", "Suggested Route"), opp_col("Corporate Strategy Advisory", "Category Route")
check("E3", "Opportunities", "Tier C commodity", "Suggested Route = Category Route", cs_route, cs_route == cs_cat)
os_route = opp_col("Office Supplies and Stationery", "Suggested Route")
check("E4", "Opportunities", "Playbook allows a catalogue", "'Catalogue' kept", os_route, os_route == "Catalogue")
pc = opp["Suggested Route"].astype(str).str.contains("P-card")
check("E5", "Opportunities", "Small, mostly-on-card tail in an Allowed category", "a P-card route", f"{pc.sum()} commodities", pc.sum() > 0)
pr = opp["Suggested Route"].astype(str).str.startswith("Prohibited")
check("E6", "Opportunities", "Card spend at cash/gambling/bar MCCs", "'Prohibited: follow up with cardholder'",
      f"{pr.sum()} commodities", pr.sum() > 0)

# ---- F. Country actions (qCountryActions.pq)
expect = [("F1", "UAE", "Protective Workwear", "Quick win: leakage"),
          ("F2", "Turkey", "Courier Services", "Quick win: extend agreement"),
          ("F3", "Turkey", "Pest Control Services", "Replicate other country"),
          ("F4", "South Africa", "Pest Control Services", "Replicate other country"),
          ("F5", "USA", "Digital Analytics Services", "Regional deal"),
          ("F6", "Turkey", "Digital Analytics Services", "Regional deal"),
          ("F7", "Germany", "Translation Services", "New agreement"),
          ("F8", "Canada", "Translation Services", "New agreement"),
          ("F9", "USA", "Corporate Strategy Advisory", "Business-led"),
          ("F10", "Germany", "Customer Rebates", "Exclude (non-addressable)"),
          ("F11", "Germany", "Office Rent", "Exclude (non-addressable)"),
          ("F12", "Germany", "Laboratory Supplies", "Classify first"),
          ("F13", "USA", "Lab Testing (not in taxonomy)", "Classify first"),
          ("F14", "BR01 (not mapped)", "Office Supplies and Stationery", "Replicate other country")]
for sid, c, com, t in expect:
    got = action(c, com)
    check(sid, "Country action", f"{c} x {com}", t, got, got == t)
dx = ca[ca["Commodity"].isin(["Freight Forwarding", "Hotels and Accommodation"])]["Action Type"].unique().tolist()
check("F15", "Country action", "Freight / hotels (tier D)", "Exclude (other channel)", dx, dx == ["Exclude (other channel)"])
ex_pri = ca.loc[ca["Action Type"].str.startswith("Exclude"), "Priority"].unique().tolist()
check("F16", "Country action", "Excluded rows", "Priority = Excluded", ex_pri, ex_pri == ["Excluded"])
high = ca[ca["Priority"].eq("High")]["Country"].nunique()
check("F17", "Country action", "Priority within each country", "every country has High rows",
      f"{high} of {ca[~ca['Priority'].eq('Excluded')]['Country'].nunique()} countries",
      high == ca[~ca["Priority"].eq("Excluded")]["Country"].nunique())

# ---- G. Commodity plan (qCommodityPlan.pq)
check("G1", "Commodity plan", "Same commodity off-catalogue in 3+ countries", "one regional agreement",
      plan("Digital Analytics Services")[:70], "one regional agreement covering 3" in plan("Digital Analytics Services"))
check("G2", "Commodity plan", "Bought in fewer than 3 countries", "local agreements",
      plan("Translation Services")[:70], "local agreements" in plan("Translation Services"))
check("G3", "Commodity plan", "Countries to copy a set-up to", "Replicate Countries listed",
      plan("Pest Control Services", "Replicate Countries"), plan("Pest Control Services", "Replicate Countries") == "South Africa, Turkey")
check("G4", "Commodity plan", "Quick-win countries", "Quick Win Countries listed",
      plan("Courier Services", "Quick Win Countries"), plan("Courier Services", "Quick Win Countries") == "Turkey")
check("G5", "Commodity plan", "Tier E commodity", "approach starts 'Exclude'", plan("Office Rent")[:50],
      plan("Office Rent").startswith("Exclude"))
check("G6", "Commodity plan", "Unclassified commodity", "approach starts 'Classify first'", plan("Laboratory Supplies")[:50],
      plan("Laboratory Supplies").startswith("Classify first"))

# ---- H. P-card compliance (qPCardOut.pq)
for sid, f in [("H1", "Blocked category"), ("H2", "Restricted category"), ("H3", "Over single limit"),
               ("H4", "Possible split"), ("H5", "Catalogue/contract supplier"), ("H6", "Missing receipt"), ("H7", "None")]:  # "None" = compliant, no flag
    n = int(flags.loc[f, "Transactions"]) if f in flags.index else 0
    check(sid, "P-card", f"Flag: {f}", "transactions flagged", f"{n} transactions", n > 0)

# ---- report
res = pd.DataFrame(S, columns=["ID", "Area", "Scenario", "Expected", "Actual", "Passed"])
res["Result"] = res["Passed"].map({True: "PASS", False: "FAIL"})
for r in res.itertuples():
    print(f"{r.Result}  {r.ID:4} {r.Area:15} {r.Scenario} -> {r.Actual}")
md = ["| ID | Area | Scenario | Expected | Actual | Result |", "| --- | --- | --- | --- | --- | --- |"]
md += [f"| {r.ID} | {r.Area} | {r.Scenario} | {r.Expected} | {r.Actual.replace('|', '/')} | {r.Result} |" for r in res.itertuples()]
(SIM / "scenario_results.md").write_text("# Scenario check results\n\nGenerated by `scripts/check_scenarios.py`.\n\n"
                                         + "\n".join(md) + "\n")
failed = (~res["Passed"]).sum()
print(f"\n{len(res) - failed} of {len(res)} scenarios passed. Results in docs/simulation/scenario_results.md")
sys.exit(1 if failed else 0)
