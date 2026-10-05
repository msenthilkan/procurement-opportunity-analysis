"""Re-implements the Power Query logic in pandas to cross-check results and render
preview charts for the README. Run after generate_sample_data.py:
    python scripts/preview_dashboard.py
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA, IMG = ROOT / "sample-data", ROOT / "docs" / "images"
IMG.mkdir(parents=True, exist_ok=True)

COUNTRY = {"AE01": "UAE", "CA01": "Canada", "DE01": "Germany", "ID01": "Indonesia",
           "JP01": "Japan", "TR01": "Turkey", "US01": "USA", "ZA01": "South Africa"}
COLORS = {"Catalogue": "#0E7C6B", "Contract": "#3E56C8", "Non-catalogue": "#C8463D", "Unclassified": "#A3ACB6"}
TARGET, MIN_LINES, MAX_AVG = 0.75, 20, 1000


def key(s):
    return " ".join(str(s).replace("\u00a0", " ").split()).lower() if pd.notna(s) else ""


spend = pd.read_excel(DATA / "qSpend.xlsx", dtype={"[REQ] Requisition ID": str})
appr = pd.read_excel(DATA / "qApproverRaw.xlsx", dtype={"[REQ] Requisition ID": str})
tax = pd.read_excel(DATA / "qTaxonomy.xlsx")
users = pd.read_excel(DATA / "qUserMaster.xlsx")
proc = {key(e) for e in pd.read_excel(DATA / "tblProcurementGroup.xlsx")["Email"]}

# Taxonomy: match on short or long name; keys mapping to >1 distinct row are ambiguous
alias = pd.concat([tax.assign(_k=tax["Level 3 (Commodity) - Short"].map(key)),
                   tax.assign(_k=tax["Level 3 (Commodity) - Long"].map(key))]).drop_duplicates()
counts = alias.groupby("_k").size()
lookup = alias[alias["_k"].map(counts) == 1].set_index("_k")
spend["_k"] = spend["[REQ]Commodity (Commodity (L3))"].map(key)
df = spend.join(lookup[["Level 1 (Family)", "Level 2 (Category)", "Level 3 (Commodity) - Long",
                        "Procurement Or Business Led"]], on="_k")

# Buying channel
lt = df["[REQ] Line Type"].map(key)
has_contract = ~df["[REQ]Contract (Contract)"].map(key).isin(["", "null", "n/a", "-", "none"])
df["Buying Channel"] = "Unclassified"
df.loc[lt.eq("non-catalog item"), "Buying Channel"] = "Non-catalogue"
df.loc[has_contract & ~lt.eq("catalog item"), "Buying Channel"] = "Contract"
df.loc[lt.eq("catalog item"), "Buying Channel"] = "Catalogue"
df["Country"] = df["[REQ]Purchasing Company (Purchase Organization Id)"].map(COUNTRY)

# Approvers: name -> email (active first) -> procurement flag, one row per requisition
users["_rank"] = users["Active"].map(key).isin(["yes", "true", "1"]).map({True: 0, False: 1})
emails = users.sort_values("_rank").assign(_n=lambda u: u["Name"].map(key)).drop_duplicates("_n").set_index("_n")
a = appr[["[REQ] Requisition ID", "[APS]Approved by User (User)"]].drop_duplicates()
a["email"] = a["[APS]Approved by User (User)"].map(key).map(emails["Business Email Address"])
a["proc"] = a["email"].map(key).isin(proc)
route = a.groupby("[REQ] Requisition ID")["proc"].agg(["any", "all"])
route["Approval Route"] = route.apply(lambda r: "Procurement only" if r["all"] else
                                      ("Procurement + Business/Finance" if r["any"] else "Business/Finance only"), axis=1)
df = df.join(route["Approval Route"], on="[REQ] Requisition ID")

amt = "sum(PO Spend)"
non = df[df["Buying Channel"].isin(["Non-catalogue", "Unclassified"])].copy()
total, non_total = df[amt].sum(), non[amt].sum()
print(f"Total spend {total:,.0f} | non-catalogue {non_total:,.0f} ({non_total / total:.1%})")

# Chart 1: spend by country and channel
pv = df.pivot_table(index="Country", columns="Buying Channel", values=amt, aggfunc="sum", fill_value=0)
pv = pv.loc[pv.sum(axis=1).sort_values().index]
fig, ax = plt.subplots(figsize=(9, 4.6))
left = None
for ch in [c for c in COLORS if c in pv.columns]:
    ax.barh(pv.index, pv[ch] / 1e3, left=None if left is None else left / 1e3, color=COLORS[ch], label=ch)
    left = pv[ch] if left is None else left + pv[ch]
ax.set_xlabel("Spend (thousands, synthetic)")
ax.set_title("Spend by country and buying channel", loc="left", fontweight="bold")
ax.legend(frameon=False, ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.14), fontsize=9)
ax.spines[["top", "right"]].set_visible(False)
fig.tight_layout()
fig.savefig(IMG / "spend_by_country.png", dpi=150)

# Chart 2: non-catalogue spend by family, coloured by who leads it
non["Led by"] = non["Procurement Or Business Led"].fillna("Not in taxonomy").str.replace(" Led", "")
non["Family"] = non["Level 1 (Family)"].fillna("Not in taxonomy")
fam = non.groupby(["Led by", "Family"])[amt].sum().sort_values()
fig, ax = plt.subplots(figsize=(9, 5))
cols = [{"Business": "#B7791F", "Procurement": "#0E7C6B"}.get(l, "#A3ACB6") for l, _ in fam.index]
ax.barh([f if l == f else f"{f} ({l})" for l, f in fam.index], fam.values / non_total * 100, color=cols)
ax.set_xlabel("% of non-catalogue spend")
ax.set_title("Non-catalogue spend by category family and lead", loc="left", fontweight="bold")
ax.spines[["top", "right"]].set_visible(False)
fig.tight_layout()
fig.savefig(IMG / "noncat_by_category.png", dpi=150)

# Chart 3: opportunity Pareto (same rules as qOpportunities.pq)
non["Commodity"] = non["Level 3 (Commodity) - Long"].fillna(non["[REQ]Commodity (Commodity (L3))"] + " (not in taxonomy)")
g = non.groupby("Commodity").agg(spend=(amt, "sum"), lines=("sum(Line Count)", "sum"),
                                 suppliers=("[REQ]Supplier (Common Supplier)", "nunique")).sort_values("spend", ascending=False)
g["cum"] = g["spend"].cumsum() / g["spend"].sum()
g["before"] = g["cum"] - g["spend"] / g["spend"].sum()
g["in_scope"] = g["before"] < TARGET
g["route"] = ["Catalogue" if (r.lines >= MIN_LINES and r.spend / r.lines <= MAX_AVG) else "Contract" for r in g.itertuples()]
top = g.head(15)
fig, ax = plt.subplots(figsize=(10, 4.8))
ax.bar(range(len(top)), top["spend"] / 1e3,
       color=[(COLORS["Catalogue"] if r == "Catalogue" else COLORS["Contract"]) if s else "#A3ACB6"
              for r, s in zip(top["route"], top["in_scope"])])
ax.set_xticks(range(len(top)), [c if len(c) <= 28 else c[:26] + "…" for c in top.index], rotation=45, ha="right", fontsize=8)
ax.set_ylabel("Non-catalogue spend (thousands)")
ax2 = ax.twinx()
ax2.plot(range(len(top)), top["cum"] * 100, color="#18212B", marker="o", ms=3)
ax2.axhline(TARGET * 100, color="#C8463D", ls="--", lw=1)
ax2.set_ylim(0, 100)
ax2.set_ylabel("Cumulative %")
ax.set_title("Opportunity Pareto: coloured bars are within the 75% target (green = catalogue, blue = contract route)",
             loc="left", fontweight="bold", fontsize=10)
ax.spines[["top"]].set_visible(False)
ax2.spines[["top"]].set_visible(False)
fig.tight_layout()
fig.savefig(IMG / "opportunity_pareto.png", dpi=150)

print(f"{int(g['in_scope'].sum())} in-scope candidates cover {g.loc[g['in_scope'], 'spend'].sum() / g['spend'].sum():.0%} "
      f"of non-catalogue spend. Charts written to {IMG}")
