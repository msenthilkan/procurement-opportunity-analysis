"""Re-implements qCountryActions.pq and qCommodityPlan.pq in pandas on the sample data,
to cross-check the rules and show example output. Run after generate_sample_data.py:
    python scripts/preview_country_actions.py
Writes docs/simulation/country_actions.csv and docs/simulation/commodity_plan.csv.
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA, SIM = ROOT / "sample-data", ROOT / "docs" / "simulation"
SIM.mkdir(parents=True, exist_ok=True)
COUNTRY = {"AE01": "UAE", "CA01": "Canada", "DE01": "Germany", "ID01": "Indonesia",
           "JP01": "Japan", "TR01": "Turkey", "US01": "USA", "ZA01": "South Africa"}
SPEND, MIN_SPEND, REGIONAL_MIN, HIGH, MEDIUM, PLAN_REGIONAL_MIN = "sum(PO Spend)", 0, 2, 0.5, 0.8, 3


def key(s):
    return " ".join(str(s).replace("\u00a0", " ").split()).lower() if pd.notna(s) else ""


def listtext(items):
    return ", ".join(sorted(set(items)))


# ---- Output (requisition lines) with taxonomy and scope tier
spend = pd.read_excel(DATA / "qSpend.xlsx", dtype={"[REQ] Requisition ID": str})
tax = pd.read_excel(DATA / "qTaxonomy.xlsx")
matrix = pd.read_excel(DATA / "tblScopeMatrix.xlsx")
mx = matrix.assign(_k=matrix["L3 Commodity"].map(key)).drop_duplicates("_k").set_index("_k")
tax["Scope Tier"] = tax["Level 3 (Commodity) - Long"].map(key).map(mx["Scope Tier"])
tax["Proposed Route"] = tax["Level 3 (Commodity) - Long"].map(key).map(mx["Proposed Route"])
alias = pd.concat([tax.assign(_k=tax["Level 3 (Commodity) - Short"].map(key)),
                   tax.assign(_k=tax["Level 3 (Commodity) - Long"].map(key))]).drop_duplicates()
counts = alias.groupby("_k").size()
lookup = alias[alias["_k"].map(counts) == 1].set_index("_k")
df = spend.join(lookup[["Level 2 (Category)", "Level 3 (Commodity) - Long", "Scope Tier", "Proposed Route"]],
                on=spend["[REQ]Commodity (Commodity (L3))"].map(key))
lt = df["[REQ] Line Type"].map(key)
has_contract = ~df["[REQ]Contract (Contract)"].map(key).isin(["", "null", "n/a", "-", "none"])
df["Buying Channel"] = "Unclassified"
df.loc[lt.eq("non-catalog item"), "Buying Channel"] = "Non-catalogue"
df.loc[has_contract & ~lt.eq("catalog item"), "Buying Channel"] = "Contract"
df.loc[lt.eq("catalog item"), "Buying Channel"] = "Catalogue"
df["Country"] = df["[REQ]Purchasing Company (Purchase Organization Id)"].map(
    lambda c: COUNTRY.get(str(c).strip().upper(), f"{str(c).strip().upper()} (not mapped)"))

# ---- qCountryActions
rows = pd.DataFrame({
    "Country": df["Country"],
    "Commodity": df["Level 3 (Commodity) - Long"].fillna(df["[REQ]Commodity (Commodity (L3))"] + " (not in taxonomy)"),
    "Category": df["Level 2 (Category)"],
    "Tier": df["Scope Tier"].fillna("Not classified"),
    "Route": df["Proposed Route"],
    "Amount": df[SPEND].fillna(0),
    "Lines": df["sum(Line Count)"].fillna(1),
    "Supplier": df["[REQ]Supplier (Common Supplier)"].fillna("(blank supplier)"),
    "Channel": df["Buying Channel"]})
on = rows[rows["Channel"].isin(["Catalogue", "Contract"])]
off = rows[~rows["Channel"].isin(["Catalogue", "Contract"])]


def chname(chs):
    chs = set(chs)
    return ("catalogue and contract" if {"Catalogue", "Contract"} <= chs
            else "catalogue" if "Catalogue" in chs else "contract")


k = lambda *c: "|".join(key(x) for x in c)
on_same = on.groupby(on.apply(lambda r: k(r.Country, r.Commodity, r.Supplier), axis=1))["Channel"].agg(chname)
on_sup = on.groupby(on.apply(lambda r: k(r.Commodity, r.Supplier), axis=1)).agg(
    Countries=("Country", lambda x: list(dict.fromkeys(x))), Ch=("Channel", chname))
on_com = on.groupby(on["Commodity"].map(key)).agg(
    Countries=("Country", lambda x: list(dict.fromkeys(x))), Ch=("Channel", chname),
    Suppliers=("Supplier", lambda x: list(dict.fromkeys(x))))
on_cell = on.groupby(on.apply(lambda r: k(r.Country, r.Commodity), axis=1))["Amount"].sum()

cells = off.groupby(["Country", "Commodity"]).agg(
    Category=("Category", lambda x: x.dropna().iloc[0] if x.notna().any() else None),
    Tier=("Tier", "first"), Route=("Route", lambda x: x.dropna().iloc[0] if x.notna().any() else None),
    Spend=("Amount", "sum"), Lines=("Lines", "sum"), Suppliers=("Supplier", "nunique")).reset_index()
top = off.groupby(["Country", "Commodity", "Supplier"])["Amount"].sum().reset_index().sort_values(
    "Amount", ascending=False).drop_duplicates(["Country", "Commodity"])
cells = cells.merge(top.rename(columns={"Supplier": "Top Supplier", "Amount": "_top"}), on=["Country", "Commodity"])
cells = cells[cells["Spend"] > MIN_SPEND].copy()
cells["Top Supplier Share"] = cells["_top"] / cells["Spend"]
cells["_tk"] = cells.apply(lambda r: k(r.Commodity, r["Top Supplier"]), axis=1)
regional = cells.groupby("_tk")["Country"].nunique()
mlook = mx[["Lead", "Practical solution"]]


def action(r):
    t = r.Tier[0]
    route = r.Route.strip().rstrip(".") if isinstance(r.Route, str) else "the category playbook route"
    ctry, com, top_ = r.Country, r.Commodity, r["Top Supplier"]
    same = on_same.get(k(ctry, com, top_))
    sup = on_sup.loc[k(com, top_)] if k(com, top_) in on_sup.index else None
    sup_other = [c for c in sup.Countries if c != ctry] if sup is not None else []
    com_on = on_com.loc[key(com)] if key(com) in on_com.index else None
    com_other = [c for c in com_on.Countries if c != ctry] if com_on is not None else []
    reg = regional.get(r._tk, 1)
    m = mlook.loc[key(com)] if key(com) in mlook.index else None
    if t == "E":
        return "Exclude (non-addressable)", f"Out of procurement scope: {route}."
    if t == "D":
        return "Exclude (other channel)", f"Bought through another channel: {route}."
    if r.Tier == "Not classified":
        return "Classify first", ("Commodity is not in the taxonomy (or matches more than one L3), so it has no scope decision."
                                  if com.endswith("(not in taxonomy)") else
                                  "Commodity is in the taxonomy but not in the scope matrix, so it has no scope decision.")
    if same is not None:
        return "Quick win: leakage", (f"{top_} already has a {same} in {ctry} for {com}, yet "
                                      f"{round(r['Top Supplier Share'] * 100)}% of this off-catalogue spend still goes to {top_} outside it.")
    if sup_other:
        return "Quick win: extend agreement", f"{top_} is already on {sup.Ch} in {listtext(sup_other)}; extend that agreement to {ctry}."
    if com_other:
        return "Replicate other country", (f"{com} is already on {com_on.Ch} in {listtext(com_other)} "
                                           f"({listtext(com_on.Suppliers[:3])}); use that set-up for {ctry}.")
    if reg >= REGIONAL_MIN:
        return "Regional deal", f"{top_} is the top off-catalogue supplier for {com} in {reg} countries; negotiate one regional agreement."
    if t == "C":
        return "Business-led", f"Business selects supplier; {route}."
    return "New agreement", f"No agreement anywhere yet: {route}."


cells[["Action Type", "Recommended Action"]] = cells.apply(lambda r: pd.Series(action(r)), axis=1)
cells["Owner"] = cells["Commodity"].map(key).map(mlook["Lead"])
cells["On-catalogue/Contract Spend"] = cells.apply(lambda r: on_cell.get(k(r.Country, r.Commodity), 0), axis=1)
cells["Current Coverage"] = cells["On-catalogue/Contract Spend"] / (cells["Spend"] + cells["On-catalogue/Contract Spend"])
excl = cells["Tier"].str[0].isin(["D", "E"])
cells["Priority"], cells["Country Rank"] = "Excluded", pd.NA
for c, g in cells[~excl].groupby("Country"):
    g = g.sort_values("Spend", ascending=False)
    before = (g["Spend"].cumsum() - g["Spend"]) / g["Spend"].sum()
    cells.loc[g.index, "Priority"] = ["High" if b < HIGH else "Medium" if b < MEDIUM else "Low" for b in before]
    cells.loc[g.index, "Country Rank"] = range(1, len(g) + 1)
order = {"High": 0, "Medium": 1, "Low": 2, "Excluded": 3}
ca = cells.assign(_p=cells["Priority"].map(order)).sort_values(["Country", "_p", "Spend"], ascending=[True, True, False])
ca = ca.rename(columns={"Tier": "Scope Tier", "Spend": "Off-catalogue Spend", "Route": "Category Route"})
cols = ["Country", "Priority", "Country Rank", "Category", "Commodity", "Scope Tier", "Action Type",
        "Recommended Action", "Owner", "Off-catalogue Spend", "On-catalogue/Contract Spend", "Current Coverage",
        "Lines", "Suppliers", "Top Supplier", "Top Supplier Share", "Category Route"]
ca[cols].round(3).to_csv(SIM / "country_actions.csv", index=False)

# ---- qCommodityPlan
def plan(g):
    t = g["Scope Tier"].iloc[0][0]
    route = (g["Category Route"].dropna().iloc[0].strip().rstrip(".") if g["Category Route"].notna().any()
             else "the category playbook route")
    n = g["Country"].nunique()
    topc = ", ".join(g.sort_values("Off-catalogue Spend", ascending=False)["Country"].head(3))
    quick = listtext(g.loc[g["Action Type"].str.startswith("Quick win"), "Country"])
    rep = listtext(g.loc[g["Action Type"].eq("Replicate other country"), "Country"])
    scale = (f"one regional agreement covering {n} countries (start with {topc})" if n >= PLAN_REGIONAL_MIN
             else f"local agreements in {topc}")
    if g["Scope Tier"].iloc[0] == "Not classified":
        approach = "Classify first: add this commodity to the taxonomy / scope matrix, then refresh."
    elif t == "E":
        approach = f"Exclude: non-addressable ({route}). Report as exclusion."
    elif t == "D":
        approach = f"Exclude from catalogue target: bought via {route}."
    elif t == "C":
        approach = f"Business-led: {route}. Procurement reviews terms; {scale} where the business agrees."
    else:
        parts = [p for p in [f"Quick wins now in {quick}: enforce or extend the existing agreements." if quick else None,
                             f"Copy an existing country set-up for {rep}." if rep else None,
                             f"Target {scale}, via {route}."] if p]
        approach = " ".join(f"{i + 1}) {p}" for i, p in enumerate(parts))
    off_s, on_s = g["Off-catalogue Spend"].sum(), g["On-catalogue/Contract Spend"].sum()
    return pd.Series({"Category": g["Category"].dropna().iloc[0] if g["Category"].notna().any() else None,
                      "Scope Tier": g["Scope Tier"].iloc[0], "Recommended Approach": approach,
                      "Off-catalogue Spend": off_s, "On-catalogue/Contract Spend": on_s,
                      "Current Coverage": on_s / (off_s + on_s), "Countries": n, "Top Countries": topc,
                      "Quick Win Countries": quick, "Replicate Countries": rep})


cp = ca.groupby("Commodity").apply(plan, include_groups=False).sort_values("Off-catalogue Spend", ascending=False)
cp.round(3).to_csv(SIM / "commodity_plan.csv")
print(f"{len(ca)} country x commodity rows; action types: " +
      ", ".join(f"{k} {v}" for k, v in ca["Action Type"].value_counts().items()))
print(f"{len(cp)} commodities in the plan. Written to {SIM}")
