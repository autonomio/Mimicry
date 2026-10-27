import csv
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# ---- 1. landmark AUC/AP vs hours ----
lm = list(csv.DictReader(open("landmark_metrics.csv")))
L = [int(r["L"]) for r in lm]
auc = [float(r["auc"]) for r in lm]
ap = [float(r["ap"]) for r in lm]
n = [int(r["n"]) for r in lm]
fig, ax1 = plt.subplots(figsize=(9, 4.5))
ax1.plot(L, auc, "o-", color="#2471a3", ms=3, label="AUC")
ax1.plot(L, ap, "s-", color="#c0392b", ms=3, label="AP")
ax1.set_xlabel("landmark: hours of data after ICU admission")
ax1.set_ylabel("AUC / AP")
ax1.set_xticks(range(1, 25))
ax1.grid(alpha=0.3)
ax2 = ax1.twinx()
ax2.plot(L, n, color="gray", lw=1, ls="--", label="n stays")
ax2.set_ylabel("cohort n (LOS >= landmark)")
h1, l1 = ax1.get_legend_handles_labels()
h2, l2 = ax2.get_legend_handles_labels()
ax1.legend(h1 + h2, l1 + l2, loc="lower right", fontsize=9)
ax1.set_title("Early-mortality signal vs hours of data (logreg, cumulative [0, L))")
fig.tight_layout()
fig.savefig("sweep_landmark.png", dpi=110)

# ---- 2. univariate heatmap ----
uni = list(csv.DictReader(open("univariate.csv")))
vitals = ["hr_med", "rr_med", "spo2_med", "map_med", "temp_med",
          "gcs_med", "lactate_med", "creat_med"]
grid = np.full((len(vitals), 24), np.nan)
for r in uni:
    if r["vital"] in vitals and int(r["h"]) < 24:
        grid[vitals.index(r["vital"]), int(r["h"])] = float(r["auc"])
grid = np.maximum(grid, 1 - grid)  # direction-free strength; see caption
fig, ax = plt.subplots(figsize=(11, 4.5))
im = ax.imshow(grid, aspect="auto", vmin=0.5, vmax=0.78, cmap="YlOrRd")
ax.set_yticks(range(len(vitals)))
ax.set_yticklabels([v.replace("_med", "") for v in vitals])
ax.set_xticks(range(24))
ax.set_xticklabels([f"{h}-{h+1}h" for h in range(24)], rotation=45, ha="right", fontsize=8)
ax.set_xlabel("hour after admission (single-hour median as lone predictor)")
ax.set_title("Univariate AUC per vital per hour (red = stronger)")
for i in range(len(vitals)):
    for j in range(24):
        if not np.isnan(grid[i, j]):
            ax.text(j, i, f"{grid[i, j]:.2f}", ha="center", va="center", fontsize=6)
fig.colorbar(im, ax=ax, label="AUC")
fig.tight_layout()
fig.savefig("sweep_univariate.png", dpi=110)
print("plots written")
