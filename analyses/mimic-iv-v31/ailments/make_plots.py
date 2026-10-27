"""Plots for the prior-year ailments vs serious illness screen.

Inputs (fetched from s0): ail_screen.csv, ail_forest.csv
Outputs: ail_screen_heatmap.png, forest_<outcome>.png
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

PRETTY = {
    "constip": "Constipation (ref)", "gerd": "GERD", "sleep": "Sleep disorder",
    "anxiety": "Anxiety", "depress": "Depression", "backpain": "Back pain",
    "headache": "Headache/migraine", "allergy": "Allergy",
    "hyperlip": "Hyperlipidemia", "hypothy": "Hypothyroidism",
    "hyperten": "Hypertension (ctrl)", "diabetes": "Diabetes (ctrl)",
    "asthma_copd": "Asthma/COPD", "anemia": "Anemia", "uti": "UTI",
    "obesity": "Obesity",
}
OUTCOMES = ["death", "icu", "unexpected_icu"]
OLABEL = {"death": "Death", "icu": "ICU",
          "unexpected_icu": "Elective->ICU"}
OTITLE = {"death": "hospital death", "icu": "any ICU stay",
          "unexpected_icu": "elective -> ICU transfer"}


def model_label(m):
    if m.startswith("adjusted-dx:"):
        return f"Adj dx only: {PRETTY[m.split(':')[1]]}"
    if m.startswith("adjusted-rx:"):
        return f"Adj Rx only: {PRETTY[m.split(':')[1]]}"
    if m.startswith("adjusted:"):
        return PRETTY[m.split(":")[1]]
    if m.startswith("matched:"):
        return f"PS-matched: {PRETTY[m.split(':')[1]]}"
    if m.startswith("dose_"):
        k, a = m.split(":")
        dose = {"coded_only": "coded-only"}.get(k[5:], k[5:])
        return f"Dose {dose}: {PRETTY[a]}"
    if m.startswith("rec_"):
        k, a = m.split(":")
        return f"Recency {k[4:]}: {PRETTY[a]}"
    return m


# ---- screen heatmap ----
scr = pd.read_csv("ail_screen.csv")
piv = scr.pivot(index="ailment", columns="outcome", values="adj_or")
piv = piv.reindex(index=list(PRETTY), columns=OUTCOMES)
qsig = scr.pivot(index="ailment", columns="outcome",
                 values="q").reindex(index=list(PRETTY),
                                     columns=OUTCOMES) < 0.05
fig, ax = plt.subplots(figsize=(7.5, 8.5))
vmax = max(1 / piv.min().min(), piv.max().max())
im = ax.imshow(np.log(piv.values), cmap="RdBu_r",
               vmin=-np.log(vmax), vmax=np.log(vmax))
ax.set_xticks(range(3))
ax.set_xticks(range(3))
ax.set_xticklabels([OLABEL[o] for o in OUTCOMES], fontsize=9)
ax.set_yticks(range(len(PRETTY)))
ax.set_yticklabels([PRETTY[a] for a in PRETTY], fontsize=9)
for i in range(len(PRETTY)):
    for j in range(3):
        v = piv.values[i, j]
        star = "*" if qsig.values[i, j] else ""
        ax.text(j, i, f"{v:.2f}{star}", ha="center", va="center",
                fontsize=8, color="white" if abs(np.log(v)) > 0.1 else "black")
fig.colorbar(im, ax=ax, label="log adjusted OR (red=harm, blue=protective)")
ax.set_title("Prior-year ailments vs serious illness: adjusted OR screen\n"
             "* = BH-FDR q<0.05 over 48 cells")
fig.tight_layout()
fig.savefig("ail_screen_heatmap.png", dpi=130)
print("wrote ail_screen_heatmap.png")

# ---- forest plots per outcome ----
fst = pd.read_csv("ail_forest.csv")
for oname in OUTCOMES:
    sub = fst[fst["outcome"] == oname].iloc[::-1].reset_index(drop=True)
    if len(sub) == 0:
        continue
    fig, ax = plt.subplots(figsize=(7.5, max(4.5, 0.42 * len(sub) + 1.2)))
    ax.axvline(1.0, color="k", lw=1)
    for i, r in sub.iterrows():
        sig = r["lo"] > 1 or r["hi"] < 1
        ax.errorbar(r["or"], i, xerr=[[r["or"] - r["lo"]],
                                      [r["hi"] - r["or"]]],
                    fmt="o", ms=4, capsize=3,
                    color="crimson" if sig else "steelblue",
                    ecolor="crimson" if sig else "steelblue")
    ax.set_yticks(range(len(sub)))
    ax.set_yticklabels([model_label(m) for m in sub["model"]], fontsize=8)
    ax.set_xlabel("Odds ratio (95% CI, log scale)")
    ax.set_xscale("log")
    ax.set_title(f"Prior-year ailments vs {OTITLE[oname]}")
    fig.tight_layout()
    fig.savefig(f"forest_{oname}.png", dpi=130)
    print(f"wrote forest_{oname}.png")
