"""Adversarial-test plots. OR/AUC numbers hardcoded from adversarial.out
(verified run output). Outputs: adv_or.png, adv_auc.png.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# 1. DNR->death OR across specifications (48h landmark)
specs = [
    ("Crude", 4.55, None),
    ("Adjusted (base)", 3.88, None),
    ("Adjusted (rich)", 4.09, None),
    ("PS-matched", 2.92, (2.66, 3.22)),
    ("SOFA tert low", 5.74, None),
    ("SOFA tert mid", 3.66, None),
    ("SOFA tert hi", 3.57, None),
    ("DNR<24h", 3.48, None),
    ("DNR 24-48h", 7.40, None),
]
fig, ax = plt.subplots(figsize=(8, 5))
y = np.arange(len(specs))
ors = [s[1] for s in specs]
ax.barh(y, ors, color="steelblue")
ax.errorbar([s[1] for s in specs], y,
            xerr=[[s[1] - s[2][0] if s[2] else 0 for s in specs],
                  [s[2][1] - s[1] if s[2] else 0 for s in specs]],
            fmt="none", ecolor="k", capsize=3)
ax.set_yticks(y)
ax.set_yticklabels([s[0] for s in specs], fontsize=9)
ax.axvline(1.0, color="k", lw=1)
ax.set_xlabel("Odds ratio for hospital death (DNR before 48h)")
ax.set_title("DNR effect survives every adjustment (E-value 5.5)")
for i, v in enumerate(ors):
    ax.text(v + 0.1, i, f"{v:.2f}", va="center", fontsize=8)
fig.tight_layout()
fig.savefig("adv_or.png", dpi=130)
print("wrote adv_or.png")

# 2. CV AUCs with gap CIs
fig, ax = plt.subplots(figsize=(8, 4.5))
hs = ["6h", "12h", "24h"]
all_auc = [0.809, 0.774, 0.756]
all_sd = [0.007, 0.008, 0.006]
fc_auc = [0.753, 0.702, 0.688]
fc_sd = [0.015, 0.028, 0.047]
gaps = ["0.053\n[0.04-0.06]", "0.061\n[0.05-0.08]", "0.044\n[0.03-0.07]"]
x = np.arange(3)
w = 0.35
ax.bar(x - w / 2, all_auc, width=w, yerr=all_sd, capsize=4,
       label="All decedents")
ax.bar(x + w / 2, fc_auc, width=w, yerr=fc_sd, capsize=4,
       label="Full-code only")
for i, g in enumerate(gaps):
    ax.text(i, 0.88, f"gap {g}", ha="center", fontsize=8)
ax.set_xticks(x)
ax.set_xticklabels(hs)
ax.set_ylim(0.5, 1.0)
ax.set_ylabel("5-fold CV AUC")
ax.legend(fontsize=9)
ax.set_title("Prediction holds out-of-sample; FC gap persists at 24h")
fig.tight_layout()
fig.savefig("adv_auc.png", dpi=130)
print("wrote adv_auc.png")
