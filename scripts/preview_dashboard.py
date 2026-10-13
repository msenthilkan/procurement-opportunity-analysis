"""Re-implements the Power Query logic in pandas to cross-check results and render
preview charts for the README. Also runs the P-card simulation (qPCardOut / qAllSpend)
and writes result tables to docs/simulation/. Run after generate_sample_data.py:
    python scripts/preview_dashboard.py
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA, IMG, SIM = ROOT / "sample-data", ROOT / "docs" / "images", ROOT / "docs" / "simulation"
IMG.mkdir(parents=True, exist_ok=True)
SIM.mkdir(parents=True, exist_ok=True)

COUNTRY = {"AE01": "UAE", "CA01": "Canada", "DE01": "Germany", "ID01": "Indonesia",
           "JP01": "Japan", "TR01": "Turkey", "US01": "USA", "ZA01": "South Africa"}
COLORS = {"Catalogue": "#0E7C6B", "Contract": "#3E56C8", "P-card on PO": "#E0A526",
          "P-card (off-platform)": "#F2C76E", "Non-catalogue": "#C8463D", "Unclassified": "#A3ACB6"}
TARGET, MIN_LINES, MAX_AVG = 0.75, 20, 1000
EXCLUDE_TIERS = ("D", "E")   # same as ExcludeTiers in qOpportunities.pq
SINGLE_LIMIT, PCARD_LINE_MAX, PCARD_MIN_SHARE = 2500, 500, 0.5   # same settings as the .pq files


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
lookup = alias[alias["_k"].map(counts) == 1].set_index("_k").copy()
# Scope matrix (qTaxonomyPolicy): Scope Tier and Proposed Route by L3 long name, then short name
matrix = pd.read_excel(DATA / "tblScopeMatrix.xlsx")
mx = matrix.assign(_m=matrix["L3 Commodity"].map(key)).drop_duplicates("_m").set_index("_m")
for col in ("Scope Tier", "Proposed Route"):
    by_long = lookup["Level 3 (Commodity) - Long"].map(key).map(mx[col])
    by_short = lookup["Level 3 (Commodity) - Short"].map(key).map(mx[col])
    lookup[col] = by_long.fillna(by_short)
spend["_k"] = spend["[REQ]Commodity (Commodity (L3))"].map(key)
TAXCOLS = ["Level 1 (Family)", "Level 2 (Category)", "Level 3 (Commodity) - Long",
           "Procurement Or Business Led", "P-card Policy", "Scope Tier", "Proposed Route"]
df = spend.join(lookup[TAXCOLS], on="_k")
df["Taxonomy Match"] = df["_k"].map(lambda k: "Blank" if k == "" else "Unmapped" if k not in counts.index
                                    else "Matched" if counts[k] == 1 else "Ambiguous")

# Buying channel
lt = df["[REQ] Line Type"].map(key)
has_contract = ~df["[REQ]Contract (Contract)"].map(key).isin(["", "null", "n/a", "-", "none"])
pay_card = df.get("[PO-P&I] Payment Method", pd.Series("", index=df.index)).map(key).str.contains("card")
df["Payment Method"] = pay_card.map({True: "P-card", False: "Invoice"})
df["Buying Channel"] = "Unclassified"
df.loc[lt.eq("non-catalog item"), "Buying Channel"] = "Non-catalogue"
df.loc[pay_card & ~lt.eq("catalog item") & ~has_contract, "Buying Channel"] = "P-card on PO"
df.loc[has_contract & ~lt.eq("catalog item"), "Buying Channel"] = "Contract"
df.loc[lt.eq("catalog item"), "Buying Channel"] = "Catalogue"
df["Source System"] = "Ariba requisition"
def country(code):
    code = str(code).strip().upper() if pd.notna(code) else ""
    return "Blank" if code == "" else COUNTRY.get(code, f"{code} (not mapped)")


df["Country"] = df["[REQ]Purchasing Company (Purchase Organization Id)"].map(country)

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
df["Approval Route"] = df["Approval Route"].fillna("No approval data")
not_in_list = a.loc[a["email"].isna(), "[REQ] Requisition ID"].nunique()

# ---------------------------------------------------------------- P-card (qPCardOut)
card = pd.read_excel(DATA / "qPCard.xlsx", dtype={"PO Reference": str})
mcc = pd.read_excel(DATA / "qMCCMap.xlsx")
mcc["_m"] = mcc["MCC"].astype(str).str.zfill(4)
mcc = mcc.drop_duplicates("_m").set_index("_m")
n_card = len(card)
po_ids = set(df["[REQ] PO Id"].map(key)) - {""}
card["_po"] = card["PO Reference"].map(key)
dup = card["_po"].isin(po_ids)
card = card[~dup].copy()                          # card-paid Ariba POs are already in Output
card["_m"] = card["MCC"].astype(str).str.zfill(4)
card = card.join(mcc[["MCC Description", "Level 3 (Commodity) - Long", "MCC Policy"]].rename(
    columns={"Level 3 (Commodity) - Long": "_mccL3"}), on="_m")
coded = card["Commodity (Cardholder Coded)"].fillna("").astype(str).str.strip()
card["[REQ]Commodity (Commodity (L3))"] = coded.where(coded != "", card["_mccL3"].fillna(""))
blank = card["[REQ]Commodity (Commodity (L3))"].eq("")
card.loc[blank, "[REQ]Commodity (Commodity (L3))"] = "MCC " + card.loc[blank, "_m"] + " " + card.loc[blank, "MCC Description"].fillna("")
card["_k"] = card["[REQ]Commodity (Commodity (L3))"].map(key)
card = card.join(lookup[TAXCOLS], on="_k")
card["P-card Policy"] = card["P-card Policy"].fillna(card["MCC Policy"]).fillna("Unknown")
amt_c = "Amount (Reporting Currency)"
card["_d"] = pd.to_datetime(card["Transaction Date"], format="%m/%d/%Y")
grp = card.groupby([card["Cardholder Name"].map(key), card["Merchant Name"].map(key), "_d"])[amt_c]
card["_n"], card["_sum"] = grp.transform("count"), grp.transform("sum")
on_platform = set(df.loc[df["Buying Channel"].isin(["Catalogue", "Contract"]), "[REQ]Supplier (Common Supplier)"].map(key))


def flags(r):
    f = []
    if r["P-card Policy"] == "Blocked": f.append("Blocked category")
    if r["P-card Policy"] == "Restricted": f.append("Restricted category")
    if r[amt_c] > SINGLE_LIMIT: f.append("Over single limit")
    if r["_n"] > 1 and r["_sum"] > SINGLE_LIMIT and r[amt_c] <= SINGLE_LIMIT: f.append("Possible split")
    if key(r["Merchant Name"]) in on_platform: f.append("Catalogue/contract supplier")
    if key(r["Receipt Attached"]) not in {"yes", "y", "true", "1"}: f.append("Missing receipt")
    return "; ".join(f) or "None"


card["P-card Flags"] = card.apply(flags, axis=1)
hard = ("Blocked", "Over single", "split", "Catalogue/contract")
card["P-card Compliance"] = card["P-card Flags"].map(
    lambda f: "Compliant" if f == "None" else ("Non-compliant" if any(h in f for h in hard) else "Review"))
cardout = pd.DataFrame({
    "[REQ] Requisition ID": "PCARD-" + card["Transaction ID"].astype(str),
    "[REQ]Supplier (Common Supplier)": card["Merchant Name"],
    "[REQ]Requisition Date (Date)": card["Transaction Date"],
    "[REQ]Commodity (Commodity (L3))": card["[REQ]Commodity (Commodity (L3))"],
    "sum(Line Count)": 1, "sum(Requisition Spend)": card[amt_c], "sum(PO Spend)": card[amt_c],
    "Country": card["Purchase Org"].map(country), "Buying Channel": "P-card (off-platform)",
    "Payment Method": "P-card", "Approval Route": "Card (no requisition)", "Source System": "P-card statement",
    "Cardholder": card["Cardholder Name"], "MCC": card["_m"], "MCC Description": card["MCC Description"],
    "P-card Flags": card["P-card Flags"], "P-card Compliance": card["P-card Compliance"],
    "Card Policy": card["P-card Policy"], **{c: card[c] for c in TAXCOLS if c != "P-card Policy"}})
cardout["P-card Policy"] = card["P-card Policy"].values
df = pd.concat([df, cardout], ignore_index=True)             # qAllSpend
df["Channel Group"] = df["Buying Channel"].map({"Catalogue": "Catalogue + Contract", "Contract": "Catalogue + Contract",
                                                "P-card on PO": "P-card", "P-card (off-platform)": "P-card"}).fillna(df["Buying Channel"])
print(f"P-card statement: {n_card} transactions, {int(dup.sum())} removed as card-paid Ariba POs "
      f"(no double count), {len(cardout)} off-platform lines added")

amt = "sum(PO Spend)"
non = df[df["Buying Channel"].isin(["Non-catalogue", "Unclassified"]) | df["Channel Group"].eq("P-card")].copy()
total, non_total = df[amt].sum(), non[amt].sum()
print(f"Total spend {total:,.0f} | non-catalogue {non_total:,.0f} ({non_total / total:.1%})")

# Chart 1: spend by country and channel
pv = df.pivot_table(index="Country", columns="Buying Channel", values=amt, aggfunc="sum", fill_value=0)
pv = pv.loc[pv.sum(axis=1).sort_values().index]
fig, ax = plt.subplots(figsize=(9, 5))
left = None
for ch in [c for c in COLORS if c in pv.columns]:
    ax.barh(pv.index, pv[ch] / 1e3, left=None if left is None else left / 1e3, color=COLORS[ch], label=ch)
    left = pv[ch] if left is None else left + pv[ch]
ax.set_xlabel("Spend (thousands, synthetic)")
ax.set_title("Spend by country and buying channel", loc="left", fontweight="bold")
ax.legend(frameon=False, ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.14), fontsize=9)
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
non = non[~non["Scope Tier"].fillna("").str[:1].isin(EXCLUDE_TIERS)].copy()   # ExcludeTiers
non["Commodity"] = non["Level 3 (Commodity) - Long"].fillna(non["[REQ]Commodity (Commodity (L3))"] + " (not in taxonomy)")
non["_card"] = non[amt].where(non["Channel Group"].eq("P-card"), 0)
_req_non = non["Buying Channel"].isin(["Non-catalogue", "Unclassified"]) & non["sum(Requisition Spend)"].le(PCARD_LINE_MAX)
non["_cand"] = non["sum(Requisition Spend)"].where(_req_non, 0)
non["_cand_n"] = _req_non.astype(int)
non["_card_n"] = non["Channel Group"].eq("P-card").astype(int)
g = non.groupby("Commodity").agg(spend=(amt, "sum"), lines=("sum(Line Count)", "sum"),
                                 suppliers=("[REQ]Supplier (Common Supplier)", "nunique"),
                                 card_spend=("_card", "sum"), cand=("_cand", "sum"), cand_n=("_cand_n", "sum"), card_n=("_card_n", "sum"),
                                 policy=("P-card Policy", lambda x: x.dropna().iloc[0] if x.notna().any() else None),
                                 category=("Level 2 (Category)", lambda x: x.dropna().iloc[0] if x.notna().any() else "Not in taxonomy"),
                                 tier=("Scope Tier", lambda x: x.dropna().iloc[0] if x.notna().any() else None),
                                 cat_route=("Proposed Route", lambda x: x.dropna().iloc[0] if x.notna().any() else None)
                                 ).sort_values("spend", ascending=False)
top_share = non.groupby(["Commodity", "[REQ]Supplier (Common Supplier)"])[amt].sum().groupby(level=0).max()
g["top_share"] = top_share / g["spend"]
g["cum"] = g["spend"].cumsum() / g["spend"].sum()
g["before"] = g["cum"] - g["spend"] / g["spend"].sum()
g["in_scope"] = g["before"] < TARGET


def route(r):
    avg = r.spend / max(r.lines, 1)
    if r.lines >= MIN_LINES and avg <= MAX_AVG:
        freq = "Catalogue"
    elif r.top_share >= 0.6:
        freq = "Contract with top supplier"
    else:
        freq = "Contract, consolidate suppliers" if r.suppliers >= 5 else "Contract"
    # Category playbook wins for tier C, and wherever it rules out a catalogue
    tier = r.tier[0] if isinstance(r.tier, str) else ""
    if not isinstance(r.cat_route, str):
        base = freq
    elif tier == "C":
        base = r.cat_route
    elif freq == "Catalogue" and "catalogue" not in r.cat_route.lower():
        base = r.cat_route
    else:
        base = freq
    tail_fit = r.policy == "Allowed" and (r.cand_n + r.card_n) / max(r.lines, 1) >= PCARD_MIN_SHARE
    if r.category == "Not in taxonomy" and r.policy == "Blocked":
        return "Prohibited: follow up with cardholder"
    if r.category == "Not in taxonomy" and r.policy == "Restricted":
        return "Card policy review (T&E or other channel)"
    if tail_fit and base == "Catalogue":
        return "Catalogue"
    if tail_fit and avg <= MAX_AVG:
        return "P-card (tail spend)"
    return base + " + P-card for tail" if tail_fit else base


def card_action(r):
    if r.card_spend == 0:
        return f"Move {r.cand_n} low-value POs to card" if (r.policy == "Allowed" and r.cand > 0) else ""
    if r.route.startswith(("Prohibited", "Card policy")): return r.route
    if r.policy == "Blocked": return f"Stop card use; move to {r.route}"
    if r.policy == "Restricted": return f"Review card use; prefer {r.route}"
    if "P-card" in r.route:
        return "Keep on card" + (f"; move {r.cand_n} low-value POs to card" if r.cand_n else "")
    return f"Card allowed; consider {r.route}"


g["route"] = [route(r) for r in g.itertuples()]
g["card_action"] = [card_action(r) for r in g.itertuples()]
top = g.head(15)
fig, ax = plt.subplots(figsize=(10, 4.8))
ax.bar(range(len(top)), top["spend"] / 1e3,
       color=[(COLORS["Catalogue"] if r == "Catalogue" else COLORS["P-card on PO"] if "P-card" in r
               else COLORS["Contract"]) if s else "#A3ACB6" for r, s in zip(top["route"], top["in_scope"])])
ax.set_xticks(range(len(top)), [c if len(c) <= 28 else c[:26] + "…" for c in top.index], rotation=45, ha="right", fontsize=8)
ax.set_ylabel("Non-catalogue spend (thousands)")
ax2 = ax.twinx()
ax2.plot(range(len(top)), top["cum"] * 100, color="#18212B", marker="o", ms=3)
ax2.axhline(TARGET * 100, color="#C8463D", ls="--", lw=1)
ax2.set_ylim(0, 100)
ax2.set_ylabel("Cumulative %")
ax.set_title("Opportunity Pareto: coloured bars are within the 75% target (green = catalogue, blue = contract, amber = P-card)",
             loc="left", fontweight="bold", fontsize=10)
ax.spines[["top"]].set_visible(False)
ax2.spines[["top"]].set_visible(False)
fig.tight_layout()
fig.savefig(IMG / "opportunity_pareto.png", dpi=150)

print(f"{int(g['in_scope'].sum())} in-scope candidates cover {g.loc[g['in_scope'], 'spend'].sum() / g['spend'].sum():.0%} "
      f"of non-catalogue spend. Charts written to {IMG}")

# Chart 4: P-card compliance (spend by flag; a line can carry several flags)
pc = df[df["Source System"].eq("P-card statement")].copy()
fl = pc.assign(Flag=pc["P-card Flags"].str.split("; ")).explode("Flag")
by_flag = fl.assign(Flag=fl["Flag"].replace("None", "No flag (compliant)")).groupby("Flag")[amt].sum().sort_values()
by_comp = pc.groupby("P-card Compliance")[amt].sum()
fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.6), gridspec_kw={"width_ratios": [2.2, 1]})
fcol = {"No flag (compliant)": "#0E7C6B", "Restricted category": "#E0A526", "Missing receipt": "#E0A526"}
a1.barh(by_flag.index, by_flag.values / 1e3, color=[fcol.get(i, "#C8463D") for i in by_flag.index])
a1.set_xlabel("Card spend (thousands, synthetic)")
a1.set_title("Off-platform P-card spend by compliance flag", loc="left", fontweight="bold", fontsize=10)
a1.spines[["top", "right"]].set_visible(False)
ccol = {"Compliant": "#0E7C6B", "Review": "#E0A526", "Non-compliant": "#C8463D"}
order = [c for c in ccol if c in by_comp.index]
a2.pie(by_comp[order], labels=[f"{c}\n{by_comp[c] / by_comp.sum():.0%}" for c in order],
       colors=[ccol[c] for c in order], startangle=90, wedgeprops={"width": 0.45})
a2.set_title("Share of card spend", fontsize=10, fontweight="bold")
fig.tight_layout()
fig.savefig(IMG / "pcard_compliance.png", dpi=150)

# Simulation result tables (CSV renders as a table on GitHub)
out = g.reset_index()[["Commodity", "category", "spend", "cum", "in_scope", "tier", "route", "cat_route",
                       "card_spend", "policy", "card_action",
                       "cand_n", "cand", "lines", "suppliers", "top_share"]]
out.columns = ["Commodity", "Category", "Off-catalogue Spend", "Cumulative Share", "In Scope", "Scope Tier",
               "Suggested Route", "Category Route",
               "P-card Spend", "P-card Policy", "P-card Action", "P-card Candidate Lines", "P-card Candidate Spend",
               "Lines", "Suppliers", "Top Supplier Share"]
out.round(3).to_csv(SIM / "opportunities.csv", index=False)
req = df[df["Source System"].eq("Ariba requisition")]
dq = pd.concat([
    req.groupby("Taxonomy Match")[amt].agg(["size", "sum"]).assign(Check="Taxonomy Match"),
    req.groupby(req["Country"].str.contains("not mapped").map({True: "Country not mapped", False: "Country mapped"}))[amt]
       .agg(["size", "sum"]).assign(Check="Country"),
    req.groupby(req["Scope Tier"].fillna("Not classified").str[:1].replace("N", "Not classified"))[amt]
       .agg(["size", "sum"]).assign(Check="Scope Tier"),
    df.groupby("Buying Channel")[amt].agg(["size", "sum"]).assign(Check="Buying Channel"),
    req.groupby("Approval Route")[amt].agg(["size", "sum"]).assign(Check="Approval Route"),
    pd.DataFrame({"size": [not_in_list], "sum": [None]}, index=["Requisitions with approver not in user master"])
       .assign(Check="Approvers")])
dq = dq.reset_index().rename(columns={"index": "Value", "size": "Lines", "sum": "Spend"})
dq[["Check", "Value", "Lines", "Spend"]].round(0).to_csv(SIM / "data_quality_summary.csv", index=False)
ch = df.pivot_table(index="Country", columns="Buying Channel", values=amt, aggfunc="sum", fill_value=0).round(0)
ch = ch[[c for c in COLORS if c in ch.columns]]
ch["Total"] = ch.sum(axis=1)
ch.to_csv(SIM / "spend_by_country_channel.csv")
cs = pc.groupby(["P-card Compliance", "P-card Policy"]).agg(Transactions=(amt, "size"), Spend=(amt, "sum")).round(0)
cs.to_csv(SIM / "pcard_compliance_summary.csv")
fl.groupby("Flag")[amt].agg(Transactions="size", Spend="sum").round(0).to_csv(SIM / "pcard_flag_summary.csv")
flagged = pc[pc["P-card Compliance"].eq("Non-compliant")].sort_values(amt, ascending=False)
flagged[["[REQ] Requisition ID", "Country", "Cardholder", "[REQ]Supplier (Common Supplier)", "MCC", "MCC Description",
         "[REQ]Commodity (Commodity (L3))", amt, "P-card Policy", "P-card Flags"]].head(50).round(2).to_csv(
    SIM / "pcard_top50_noncompliant.csv", index=False)

total_all = df[amt].sum()
print(f"All spend {total_all:,.0f}: " + ", ".join(f"{k} {v / total_all:.1%}" for k, v in
      df.groupby("Buying Channel")[amt].sum().sort_values(ascending=False).items()))
print(f"P-card off-platform {pc[amt].sum():,.0f}: " + ", ".join(f"{k} {v / by_comp.sum():.0%}" for k, v in by_comp.items()))
print(f"Simulation tables written to {SIM}")
