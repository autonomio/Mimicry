"""Plots for the self-fulfilling prophecy dissection.

Inputs: pr_slope_*.csv. AUC numbers are hardcoded from prophecy.out
(verified run output). Outputs: pr_pred.png, pr_slope.png.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# 1. prediction AUCs: FC vs ALL, phys vs chart vs both
auc = {
    ("FC", 6): (0.761, None, None),
    ("FC", 12): (0.725, None, None),
    ("FC", 24): (0.697, None, None),
    ("ALL", 6): (0.811, 0.791, 0.896),
    ("ALL", 12): (0.785, 0.763, 0.873),
    ("ALL", 24): (0.771, 0.737, 0.856),
}
fig, axes = plt.subplots(1, 2, figsize=(10, 4.5), sharey=True)
for ax, pop in zip(axes, ["FC", "ALL"]):
    hs = [6, 12, 24]
    x = np.arange(3)
    w = 0.25
    phys = [auc[(pop, h)][0] for h in hs]
    ax.bar(x - w, phys, width=w, label="Physiology")
    if pop == "ALL":
        ch = [auc[(pop, h)][1] for h in hs]
        bo = [auc[(pop, h)][2] for h in hs]
        ax.bar(x, ch, width=w, label="Chart (DNR written)")
        ax.bar(x + w, bo, width=w, label="Both")
    ax.set_xticks(x)
    ax.set_xticklabels([f"{h}h" for h in hs])
    ax.set_ylim(0.4, 1.0)
    ax.set_title("Full-code decedents" if pop == "FC" else "All decedents")
    ax.set_xlabel("Horizon")
    ax.legend(fontsize=8)
axes[0].set_ylabel("AUC (death within horizon)")
fig.suptitle("Imminent-death prediction: physiology vs the chart")
fig.tight_layout()
fig.savefig("pr_pred.png", dpi=130)
print("wrote pr_pred.png")

# 2. slope discontinuity around DNR time (paired post-pre deltas)
fig, axes = plt.subplots(1, 2, figsize=(10, 4.5), sharey=False)
for ax, sig, unit in zip(axes, ["hr", "map"],
                         ["bpm/hour", "mmHg/hour"]):
    d = pd.read_csv(f"pr_slope_dnr_{sig}.csv")
    c = pd.read_csv(f"pr_slope_ctl_{sig}.csv")
    dd = (d["post"] - d["pre"]).dropna()
    cc = (c["post"] - c["pre"]).dropna()
    for v, lab in [(dd, f"DNR (med {dd.median():+.3f}, n={len(dd)})"),
                   (cc, f"Control (med {cc.median():+.3f}, n={len(cc)})")]:
        x = np.sort(v.values)
        ax.plot(x, np.arange(1, len(x) + 1) / len(x), label=lab)
    ax.axvline(0, color="k", lw=0.8)
    lo = min(dd.quantile(0.01), cc.quantile(0.01))
    hi = max(dd.quantile(0.99), cc.quantile(0.99))
    ax.set_xlim(lo, hi)
    ax.set_title(f"{sig.upper()} slope change at DNR time ({unit})")
    ax.set_xlabel("Post minus pre slope")
    ax.set_ylabel("ECDF")
    ax.legend(fontsize=8)
fig.suptitle("Decline steepens after DNR; matched controls flat")
fig.tight_layout()
fig.savefig("pr_slope.png", dpi=130)
print("wrote pr_slope.png")
