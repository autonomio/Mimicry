"""Forest plot for the constipation -> hospital survival study."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

df = pd.read_csv("const_forest.csv")
labels = {
    "adjusted:coded": "Adjusted: coded dx",
    "adjusted:lax_any": "Adjusted: laxative Rx",
    "adjusted:either": "Adjusted: either",
    "adjusted:both": "Adjusted: both",
    "adjusted+ICU:either": "Adjusted + ICU flag: either",
    "matched:either": "PS-matched: either",
    "matched:coded": "PS-matched: coded dx",
    "dose_1": "Dose: 1 lax fill",
    "dose_2+": "Dose: 2+ lax fills",
    "dose_coded_only": "Dose: coded, no lax",
    "recency_remote": "Recency: 6-12 mo",
    "recency_recent": "Recency: 0-6 mo",
    "subgroup:age<65": "Subgroup: age < 65",
    "subgroup:age65+": "Subgroup: age 65+",
    "subgroup:noICU": "Subgroup: never ICU",
    "subgroup:ICU": "Subgroup: ICU",
}
df = df.iloc[::-1].reset_index(drop=True)
y = range(len(df))
fig, ax = plt.subplots(figsize=(7.5, 7.0))
ax.axvline(1.0, color="k", lw=1)
for i, r in df.iterrows():
    sig = r["lo"] > 1 or r["hi"] < 1
    ax.errorbar(r["or"], i, xerr=[[r["or"] - r["lo"]], [r["hi"] - r["or"]]],
                fmt="o", ms=4, capsize=3,
                color="crimson" if sig else "steelblue",
                ecolor="crimson" if sig else "steelblue")
ax.set_yticks(list(y))
ax.set_yticks(list(y))
ax.set_yticklabels([labels.get(m, m) for m in df["model"]], fontsize=8)
ax.set_xlabel("Odds ratio for hospital death (95% CI, log scale)")
ax.set_xscale("log")
ax.set_title("Prior-year constipation vs hospital survival "
             "(n=546,028 admissions)")
fig.tight_layout()
fig.savefig("const_forest.png", dpi=130)
print("wrote const_forest.png")
