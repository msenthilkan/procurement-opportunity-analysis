"""Builds the pivot views shown on GitHub: one chart per business question, a dashboard overview,
and the underlying pivot tables as markdown (docs/pivots.md).

Uses the same logic as the Power Query files (via the two preview scripts). Run after
generate_sample_data.py:
    python scripts/build_visuals.py
"""
import contextlib
import io
import runpy
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
IMG = ROOT / "docs" / "images" / "pivots"
IMG.mkdir(parents=True, exist_ok=True)

with contextlib.redirect_stdout(io.StringIO()):
    dash = runpy.run_path(str(ROOT / "scripts" / "preview_dashboard.py"))
    acts = runpy.run_path(str(ROOT / "scripts" / "preview_country_actions.py"))
df, opp_all, ca, cp = dash["df"].copy(), dash["g"].copy(), acts["ca"].copy(), acts["cp"].copy()
AMT = "sum(PO Spend)"
TARGET, ASSUME = 0.75, {"A": 0.9, "B": 0.7, "C": 0.2}   # same as the scope workbook's Coverage sheet

# ---------------------------------------------------------------- style
INK, MUTED, GRID = "#18212B", "#6B7785", "#E6E9ED"
CH = {"Catalogue": "#0E7C6B", "Contract": "#3E56C8", "P-card on PO": "#E0A526",
      "P-card (off-platform)": "#F2C76E", "Non-catalogue": "#C8463D", "Unclassified": "#A3ACB6"}
TIER = {"A": "#0E7C6B", "B": "#3E56C8", "C": "#E0A526", "D": "#8C96A3", "E": "#C8463D", "Not classified": "#CDD3DA"}
TIER_NAME = {"A": "A. Procurement-led", "B": "B. Co-managed", "C": "C. Business-led", "D": "D. Other channel",
             "E": "E. Out of scope", "Not classified": "Not classified"}
ACT = {"Quick win: leakage": "#0E7C6B", "Quick win: extend agreement": "#3FA796", "Replicate other country": "#3E56C8",
       "Regional deal": "#7A8BE0", "New agreement": "#E0A526", "Business-led": "#B7791F",
       "Classify first": "#A3ACB6", "Exclude (other channel)": "#8C96A3", "Exclude (non-addressable)": "#C8463D"}
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": GRID, "axes.labelcolor": MUTED,
                     "xtick.color": MUTED, "ytick.color": MUTED, "axes.titlecolor": INK})


def money(v, d=1):
    return f"{v / 1e6:.{d}f}M" if abs(v) >= 1e6 else f"{v / 1e3:.0f}k"


def tidy(ax, grid="x"):
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis=grid, color=GRID, lw=0.8)
    ax.set_axisbelow(True)


def title(ax, q, sub=None):
    ax.set_title(q, loc="left", fontsize=11, fontweight="bold", pad=18 if sub else 8)
    if sub:
        ax.text(0, 1.015, sub, transform=ax.transAxes, fontsize=8.5, color=MUTED, va="bottom")


# ---------------------------------------------------------------- derived fields
df["Tier"] = df["Scope Tier"].fillna("Not classified").map(lambda t: t if t == "Not classified" else t[0])
df["Family"] = df["Level 1 (Family)"].fillna("Not in taxonomy")
df["Month"] = pd.to_datetime(df["[REQ]Requisition Date (Date)"], format="%m/%d/%Y", errors="coerce").dt.to_period("M")
req = df[df["Source System"].eq("Ariba requisition")]
off = req[~req["Buying Channel"].isin(["Catalogue", "Contract"])]          # off-catalogue requisition spend
tier_tot = off.groupby("Tier")[AMT].sum()
addressable = sum(tier_tot.get(t, 0) for t in "ABC")
feasible = sum(tier_tot.get(t, 0) * ASSUME[t] for t in "ABC")
on_platform = df.loc[df["Buying Channel"].isin(["Catalogue", "Contract"]), AMT].sum()
quick = ca[ca["Action Type"].str.startswith("Quick win")]


# ---------------------------------------------------------------- charts (each draws on an axis)
def chart_country_channel(ax):
    pv = df.pivot_table(index="Country", columns="Buying Channel", values=AMT, aggfunc="sum", fill_value=0)
    pv = pv.loc[pv.sum(axis=1).sort_values().index]
    left = np.zeros(len(pv))
    for ch in [c for c in CH if c in pv.columns]:
        ax.barh(pv.index, pv[ch] / 1e6, left=left, color=CH[ch], label=ch, height=0.7)
        left += pv[ch].values / 1e6
    ax.set_xlim(0, left.max() * 1.05)
    tidy(ax)
    ax.set_xlabel("Spend (M, synthetic)")
    ax.legend(frameon=False, ncol=3, fontsize=7.5, loc="lower right")
    title(ax, "Where does spend go, by country?", "Pivot: Country x Buying Channel")


def chart_coverage_bridge(ax):
    tot = off[AMT].sum()
    steps = [("Off-catalogue\nspend", tot, "total"), ("E. Out of\nscope", -tier_tot.get("E", 0), "E"),
             ("D. Other\nchannel", -tier_tot.get("D", 0), "D"), ("Not\nclassified", -tier_tot.get("Not classified", 0), "Not classified"),
             ("Addressable\n(A+B+C)", addressable, "total"), ("Feasible\ncoverage", feasible, "feasible")]
    run = 0
    for i, (lab, v, kind) in enumerate(steps):
        if kind == "total":
            ax.bar(i, v / 1e6, color=INK, width=0.6)
            run = v
            y = v
        elif kind == "feasible":
            ax.bar(i, v / 1e6, color=TIER["A"], width=0.6)
            y = v
        else:
            ax.bar(i, -v / 1e6, bottom=(run + v) / 1e6, color=TIER[kind], width=0.6)
            run += v
            y = run - v
        ax.text(i, y / 1e6, money(abs(v)), ha="center", va="bottom", fontsize=8, color=INK)
    ax.axhline(TARGET * addressable / 1e6, color=TIER["E"], ls="--", lw=1)
    ax.text(len(steps) - 0.5, TARGET * addressable / 1e6, f" 75% target\n of addressable", color=TIER["E"],
            fontsize=7.5, va="center")
    ax.set_xticks(range(len(steps)), [s[0] for s in steps], fontsize=8)
    ax.set_ylabel("Spend (M)")
    tidy(ax, "y")
    title(ax, "How much can realistically be covered?",
          f"Feasible = {feasible / addressable:.0%} of addressable (assumes A 90%, B 70%, C 20%)")


def chart_tier_family(ax):
    pv = off.pivot_table(index="Family", columns="Tier", values=AMT, aggfunc="sum", fill_value=0)
    pv = pv.loc[pv.sum(axis=1).sort_values().index]
    left = np.zeros(len(pv))
    for t in [t for t in TIER if t in pv.columns]:
        ax.barh(pv.index, pv[t] / 1e6, left=left, color=TIER[t], label=TIER_NAME[t], height=0.7)
        left += pv[t].values / 1e6
    ax.set_xlim(0, left.max() * 1.05)
    tidy(ax)
    ax.set_xlabel("Off-catalogue spend (M)")
    ax.legend(frameon=False, fontsize=7.5, loc="lower right")
    title(ax, "Which families are in procurement's scope?", "Pivot: L1 Family x Scope Tier (off-catalogue)")


def chart_action_heatmap(ax):
    order = [a for a in ACT if a in set(ca["Action Type"])]
    pv = ca.pivot_table(index="Country", columns="Action Type", values="Off-catalogue Spend", aggfunc="sum", fill_value=0)
    pv = pv[[a for a in order if a in pv.columns]]
    pv = pv.loc[pv.sum(axis=1).sort_values(ascending=False).index]
    m = pv.values / 1e3
    ax.imshow(np.log1p(m), cmap="Blues", aspect="auto")
    for i in range(m.shape[0]):
        for j in range(m.shape[1]):
            if m[i, j] > 0:
                ax.text(j, i, f"{m[i, j]:,.0f}" if m[i, j] >= 1 else "<1", ha="center", va="center", fontsize=6.5,
                        color="white" if np.log1p(m[i, j]) > np.log1p(m).max() * 0.6 else INK)
    ax.set_xticks(range(len(pv.columns)), [c.replace("Quick win: ", "QW: ").replace(" (", "\n(") for c in pv.columns],
                  rotation=35, ha="right", fontsize=7)
    ax.set_yticks(range(len(pv.index)), pv.index, fontsize=8)
    ax.spines[:].set_visible(False)
    title(ax, "What should each country do?", "Pivot: Country x Action Type, off-catalogue spend (k)")


def chart_quick_wins(ax):
    pv = quick.pivot_table(index="Country", columns="Action Type", values="Off-catalogue Spend", aggfunc="sum", fill_value=0)
    pv = pv.loc[pv.sum(axis=1).sort_values().index]
    left = np.zeros(len(pv))
    for a in [a for a in ACT if a in pv.columns]:
        ax.barh(pv.index, pv[a] / 1e6, left=left, color=ACT[a], label=a.replace("Quick win: ", ""), height=0.7)
        left += pv[a].values / 1e6
    for i, v in enumerate(left):
        ax.text(v, i, f" {v:.1f}M", va="center", fontsize=7.5, color=INK)
    tidy(ax)
    ax.set_xlabel("Off-catalogue spend with an existing agreement (M)")
    ax.legend(frameon=False, fontsize=7.5, loc="lower right")
    title(ax, "Quick wins: spend that already has an agreement", "Leakage = same country; extend = agreement in another country")


def chart_involvement(ax):
    r = req[req["Procurement Or Business Led"].notna() & ~req["Approval Route"].eq("No approval data")].copy()
    r["Intent"] = r["Procurement Or Business Led"].str.replace(" Led", "-led")
    r["Procurement approved"] = r["Approval Route"].str.contains("Procurement")
    pv = r.groupby(["Intent", "Procurement approved"])[AMT].sum().unstack(fill_value=0)
    share = pv.div(pv.sum(axis=1), axis=0)
    y = np.arange(len(share))
    ax.barh(y, share.get(True, 0) * 100, color=TIER["A"], label="Procurement approved", height=0.55)
    ax.barh(y, share.get(False, 0) * 100, left=share.get(True, 0) * 100, color=CH["Non-catalogue"],
            label="Business/finance only", height=0.55)
    for i, v in enumerate(share.get(True, pd.Series(0, index=share.index))):
        ax.text(v * 100 / 2, i, f"{v:.0%}", ha="center", va="center", color="white", fontsize=9, fontweight="bold")
    ax.set_yticks(y, [f"{i} categories" for i in share.index])
    ax.set_xlim(0, 100)
    ax.set_xlabel("% of spend")
    tidy(ax)
    ax.legend(frameon=False, fontsize=7.5, loc="upper center", bbox_to_anchor=(0.5, -0.22), ncol=2)
    title(ax, "Is procurement involved where it should be?", "Pivot: Taxonomy intent x Approval route")


def chart_monthly(ax):
    pv = df.dropna(subset=["Month"]).pivot_table(index="Month", columns="Buying Channel", values=AMT,
                                                 aggfunc="sum", fill_value=0)
    bottom = np.zeros(len(pv))
    x = np.arange(len(pv))
    for ch in [c for c in CH if c in pv.columns]:
        ax.bar(x, pv[ch] / 1e6, bottom=bottom, color=CH[ch], label=ch, width=0.75)
        bottom += pv[ch].values / 1e6
    ax.set_ylim(0, bottom.max() * 1.3)
    ax.set_xticks(x, [p.strftime("%b %y") for p in pv.index], rotation=45, ha="right", fontsize=7.5)
    ax.set_ylabel("Spend (M)")
    tidy(ax, "y")
    ax.legend(frameon=False, ncol=3, fontsize=7.5, loc="upper left")
    title(ax, "Is the channel mix changing over time?", "Pivot: Month x Buying Channel")


def chart_top_opportunities(ax):
    top = opp_all.sort_values("spend", ascending=False).head(10).iloc[::-1]
    cols = [TIER.get(t[0], TIER["Not classified"]) if isinstance(t, str) else TIER["Not classified"] for t in top["tier"]]
    ax.barh(range(len(top)), top["spend"] / 1e6, color=cols, height=0.7)
    for i, (v, rt) in enumerate(zip(top["spend"], top["route"])):
        rt = rt if len(rt) <= 46 else rt[:44] + "…"
        ax.text(v / 1e6, i, f"  {money(v)}  {rt}", va="center", fontsize=7.2, color=INK)
    ax.set_yticks(range(len(top)), [c if len(c) <= 34 else c[:32] + "…" for c in top.index], fontsize=8)
    ax.set_xlim(0, top["spend"].max() / 1e6 * 1.75)
    ax.set_xlabel("Off-catalogue spend (M)")
    tidy(ax)
    title(ax, "Top 10 opportunities and their route", "Colour = scope tier; tiers D and E already excluded")


CHARTS = [("01_spend_by_country_channel", chart_country_channel, (9, 5)),
          ("02_coverage_bridge", chart_coverage_bridge, (9, 5)),
          ("03_scope_by_family", chart_tier_family, (9, 5.2)),
          ("04_country_action_heatmap", chart_action_heatmap, (10, 5.4)),
          ("05_quick_wins_by_country", chart_quick_wins, (9, 4.8)),
          ("06_procurement_involvement", chart_involvement, (9, 3.6)),
          ("07_monthly_channel_trend", chart_monthly, (10, 4.6)),
          ("08_top_opportunities", chart_top_opportunities, (10, 5))]
for name, fn, size in CHARTS:
    fig, ax = plt.subplots(figsize=size)
    fn(ax)
    fig.tight_layout()
    fig.savefig(IMG / f"{name}.png", dpi=150)
    plt.close(fig)

# ---------------------------------------------------------------- dashboard overview
fig = plt.figure(figsize=(16, 11))
gs = fig.add_gridspec(3, 2, height_ratios=[0.22, 1, 1], hspace=0.5, wspace=0.28)
kpis = [("Total spend", money(df[AMT].sum())),
        ("On catalogue / contract", f"{on_platform / df[AMT].sum():.1%}"),
        ("Off-catalogue spend", money(off[AMT].sum())),
        ("Addressable (A+B+C)", f"{addressable / off[AMT].sum():.0%}"),
        ("Feasible coverage*", f"{feasible / addressable:.0%}"),
        ("Quick-win spend", money(quick["Off-catalogue Spend"].sum()))]
from matplotlib.patches import FancyBboxPatch  # noqa: E402
kax = fig.add_subplot(gs[0, :])
kax.set_xlim(0, 6), kax.set_ylim(0, 1), kax.axis("off")
for i, (lab, val) in enumerate(kpis):
    kax.add_patch(FancyBboxPatch((i + 0.04, 0.05), 0.92, 0.9, boxstyle="round,pad=0,rounding_size=0.06",
                                 fc="#F4F6F8", ec="none"))
    kax.text(i + 0.12, 0.58, val, fontsize=20, fontweight="bold", color=INK, va="center")
    kax.text(i + 0.12, 0.22, lab, fontsize=9.5, color=MUTED, va="center")
for (r, c), fn in zip([(1, 0), (1, 1), (2, 0), (2, 1)],
                      [chart_country_channel, chart_coverage_bridge, chart_tier_family, chart_action_heatmap]):
    fn(fig.add_subplot(gs[r, c]))
fig.suptitle("Procurement catalogue and contract opportunity dashboard (synthetic data)", x=0.125, y=0.95,
             ha="left", fontsize=15, fontweight="bold", color=INK)
fig.text(0.125, 0.06, "* Feasible coverage = share of addressable spend that can move to catalogue/contract, "
         "assuming A 90%, B 70%, C 20%. Addressable = off-catalogue spend excluding tiers D, E and unclassified.",
         fontsize=8.5, color=MUTED)
fig.savefig(ROOT / "docs" / "images" / "dashboard.png", dpi=130, bbox_inches="tight")
plt.close(fig)


# ---------------------------------------------------------------- pivot tables as markdown
def md(frame, money_cols=(), pct_cols=(), index=True):
    f = frame.reset_index() if index else frame.copy()
    for c in money_cols:
        f[c] = f[c].map(lambda v: f"{v:,.0f}")
    for c in pct_cols:
        f[c] = f[c].map(lambda v: f"{v:.1%}")
    head = "| " + " | ".join(map(str, f.columns)) + " |"
    sep = "| " + " | ".join("---:" if c in money_cols or c in pct_cols else "---" for c in f.columns) + " |"
    rows = ["| " + " | ".join(str(v).replace("|", "/") for v in r) + " |" for r in f.values]
    return "\n".join([head, sep] + rows)


p1 = df.pivot_table(index="Country", columns="Buying Channel", values=AMT, aggfunc="sum", fill_value=0)
p1 = p1[[c for c in CH if c in p1.columns]]
p1["Total"] = p1.sum(axis=1)
p1["On catalogue/contract %"] = (p1.get("Catalogue", 0) + p1.get("Contract", 0)) / p1["Total"]
p1 = p1.sort_values("Total", ascending=False)
p2 = off.groupby("Tier")[AMT].sum().rename(index=TIER_NAME).to_frame("Off-catalogue spend")
p2["Share"] = p2["Off-catalogue spend"] / p2["Off-catalogue spend"].sum()
p2["Coverage assumption"] = [f"{ASSUME[t]:.0%}" if t in ASSUME else "excluded"
                             for t in off.groupby("Tier")[AMT].sum().index]
p3 = off.pivot_table(index="Family", columns="Tier", values=AMT, aggfunc="sum", fill_value=0)
p3.columns = [TIER_NAME[c] for c in p3.columns]
p3["Total"] = p3.sum(axis=1)
p3 = p3.sort_values("Total", ascending=False)
p4 = ca.pivot_table(index="Country", columns="Action Type", values="Off-catalogue Spend", aggfunc="sum", fill_value=0)
p4 = p4[[a for a in ACT if a in p4.columns]]
p5 = ca.groupby("Action Type").agg(Rows=("Commodity", "size"), Spend=("Off-catalogue Spend", "sum"))
p5 = p5.loc[[a for a in ACT if a in p5.index]]
top10 = opp_all.sort_values("spend", ascending=False).head(10)
p6 = pd.DataFrame({"Commodity": top10.index, "Scope tier": top10["tier"].fillna("Not classified").values,
                   "Off-catalogue spend": top10["spend"].values, "Suggested route": top10["route"].values})
r = req[req["Procurement Or Business Led"].notna()]
p7 = r.pivot_table(index="Procurement Or Business Led", columns="Approval Route", values=AMT, aggfunc="sum", fill_value=0)

doc = f"""# Pivot views

Every chart answers one business question and is built from a pivot on the query output, exactly as you would in Excel
(recipes in [dashboard-pivots.md](dashboard-pivots.md)). All numbers are **synthetic**. Regenerate with
`python scripts/build_visuals.py`.

![Dashboard](images/dashboard.png)

## 1. Where does spend go, by country?

Pivot on **Output / AllSpend**: rows `Country`, columns `Buying Channel`, values `sum(PO Spend)`.

![Spend by country and channel](images/pivots/01_spend_by_country_channel.png)

{md(p1, money_cols=[c for c in p1.columns if c != 'On catalogue/contract %'], pct_cols=['On catalogue/contract %'])}

**Read it as:** only {on_platform / df[AMT].sum():.1%} of spend runs through a catalogue or contract today; the rest is the opportunity.

## 2. How much can realistically be covered?

Pivot on **Output**: filter `Buying Channel` = off-catalogue, rows `Taxonomy.Scope Tier`. The bridge removes non-addressable (E),
other-channel (D) and not-yet-classified spend, then applies the coverage assumptions from the scope workbook.

![Coverage bridge](images/pivots/02_coverage_bridge.png)

{md(p2, money_cols=['Off-catalogue spend'], pct_cols=['Share'])}

**Read it as:** addressable spend is {money(addressable)}; feasible coverage is {money(feasible)}, or {feasible / addressable:.0%} of
addressable, against a 75% target. Reporting on *total* off-catalogue spend would understate what procurement can influence.

## 3. Which families are in procurement's scope?

Pivot on **Output**: rows `Taxonomy.Level 1 (Family)`, columns `Taxonomy.Scope Tier`, filter off-catalogue.

![Scope by family](images/pivots/03_scope_by_family.png)

{md(p3, money_cols=list(p3.columns))}

## 4. What should each country do?

Pivot on **qCountryActions**: rows `Country`, columns `Action Type`, values `Off-catalogue Spend`.

![Country x action heatmap](images/pivots/04_country_action_heatmap.png)

{md(p4, money_cols=list(p4.columns))}

{md(p5, money_cols=['Spend'])}

## 5. Quick wins: spend that already has an agreement

Pivot on **qCountryActions** filtered on `Action Type` starting with "Quick win". These need no sourcing event: either
requesters bypass an agreement that exists in their own country (leakage), or the supplier already has one in another
country that can be extended.

![Quick wins](images/pivots/05_quick_wins_by_country.png)

## 6. Is procurement involved where it should be?

Pivot on **Output**: rows `Taxonomy.Procurement Or Business Led`, columns `Approval Route`.

![Procurement involvement](images/pivots/06_procurement_involvement.png)

{md(p7, money_cols=list(p7.columns))}

## 7. Is the channel mix changing over time?

Pivot on **Output**: rows `Month`, columns `Buying Channel`.

![Monthly trend](images/pivots/07_monthly_channel_trend.png)

## 8. Top 10 opportunities and their route

From **qOpportunities** (tiers D and E excluded, category route applied).

![Top opportunities](images/pivots/08_top_opportunities.png)

{md(p6, money_cols=['Off-catalogue spend'], index=False)}
"""
(ROOT / "docs" / "pivots.md").write_text(doc)
print(f"Wrote {len(CHARTS)} pivot charts to {IMG}, docs/images/dashboard.png and docs/pivots.md")
