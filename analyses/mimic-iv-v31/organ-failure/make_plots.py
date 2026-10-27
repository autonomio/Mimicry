"""Plots for the organ-failure order study.

Inputs: of_traj_*.csv, of_first_thr3.csv, of_precedence_thr3.csv
Outputs: of_trajectories.png, of_total_sofa.png, of_first.png,
  of_precedence.png, of_subgroups.png
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ORGANS = ["respiration", "coagulation", "liver", "cardiovascular", "cns",
          "renal"]
PRETTY = {"respiration": "Respiratory", "coagulation": "Coagulation",
          "liver": "Liver", "cardiovascular": "Cardiovascular", "cns": "CNS",
          "renal": "Renal"}


def load(name, min_n=500):
    t = pd.read_csv(f"of_traj_{name}.csv").sort_values("bin")
    t = t[t["n"] >= min_n]
    t["hbd"] = -t["bin"]
    return t


dec = load("dec")
surv = load("surv")

# 1. per-organ trajectories, decedents
fig, ax = plt.subplots(figsize=(8, 5))
for o in ORGANS:
    ax.plot(dec["hbd"], dec[o], label=PRETTY[o])
ax.axvline(0, color="k", lw=1)
ax.set_xlabel("Hours before death")
ax.set_ylabel("Mean SOFA subscore")
ax.set_title("Organ dysfunction trajectories before death (n=8,534 ICU "
             "decedents)")
ax.legend(fontsize=8, ncol=2)
fig.tight_layout()
fig.savefig("of_trajectories.png", dpi=130)
print("wrote of_trajectories.png")

# 2. total SOFA: decedents vs survivors (aligned to discharge)
fig, ax = plt.subplots(figsize=(8, 4.5))
ax.plot(dec["hbd"], dec["sofa"], label="Decedents (to death)")
ax.plot(surv["hbd"], surv["sofa"], label="Survivors (to ICU discharge)")
ax.axvline(0, color="k", lw=1)
ax.set_xlabel("Hours before death / ICU discharge")
ax.set_ylabel("Mean total SOFA")
ax.set_title("Total SOFA: death vs recovery")
ax.legend(fontsize=9)
fig.tight_layout()
fig.savefig("of_total_sofa.png", dpi=130)
print("wrote of_total_sofa.png")

# 3. first-failing organ, both thresholds
f3 = pd.read_csv("of_first_thr3.csv", index_col=0)
f2 = pd.read_csv("of_first_thr2.csv", index_col=0)
fig, axes = plt.subplots(1, 2, figsize=(9, 4.5), sharey=True)
for ax, f, t in [(axes[0], f3, "Failure (SOFA>=3)"),
                 (axes[1], f2, "Dysfunction (SOFA>=2)")]:
    f = f.reindex([o for o in ORGANS])
    ax.barh([PRETTY[o] for o in f.index], f.iloc[:, 0])
    ax.set_title(t)
    ax.set_xlabel("Share first-failing (tie-split)")
axes[0].invert_yaxis()
fig.suptitle("Which organ fails first")
fig.tight_layout()
fig.savefig("of_first.png", dpi=130)
print("wrote of_first.png")

# 4. precedence heatmap P(row before col), thr3
p = pd.read_csv("of_precedence_thr3.csv")
m = pd.DataFrame(0.5, index=ORGANS, columns=ORGANS, dtype=float)
for _, r in p.iterrows():
    m.loc[r["a"], r["b"]] = r["p_a_first_notie"]
    m.loc[r["b"], r["a"]] = r["p_b_first_notie"]
fig, ax = plt.subplots(figsize=(6.5, 5.5))
im = ax.imshow(m.values, cmap="RdBu_r", vmin=0, vmax=1)
ax.set_xticks(range(6))
ax.set_yticks(range(6))
ax.set_xticklabels([PRETTY[o] for o in ORGANS], rotation=25, ha="right",
                   fontsize=9)
ax.set_yticklabels([PRETTY[o] for o in ORGANS], fontsize=9)
for i in range(6):
    for j in range(6):
        if i != j:
            ax.text(j, i, f"{m.values[i, j]:.2f}", ha="center",
                    va="center", fontsize=8,
                    color="white" if abs(m.values[i, j] - 0.5) > 0.25
                    else "black")
fig.colorbar(im, ax=ax, label="P(row organ fails before column organ)")
ax.set_title("Pairwise failure precedence (SOFA>=3, ties excluded)")
fig.tight_layout()
fig.savefig("of_precedence.png", dpi=130)
print("wrote of_precedence.png")

# 5. subgroup total-SOFA trajectories
fig, axes = plt.subplots(1, 3, figsize=(11, 4), sharey=True)
for ax, files, title in [
        (axes[0], ["sepsis", "nonsepsis"], "Sepsis vs not"),
        (axes[1], ["age65p", "ageu65"], "Age 65+ vs <65"),
        (axes[2], ["fullcode", "dec"], "Full-code vs all decedents")]:
    for f in files:
        t = load(f, min_n=100 if f == "fullcode" else 500)
        ax.plot(t["hbd"], t["sofa"], label=f)
    ax.set_title(title)
    ax.set_xlabel("Hours before death")
    ax.legend(fontsize=8)
axes[0].set_ylabel("Mean total SOFA")
fig.suptitle("Death-aligned total SOFA by subgroup")
fig.tight_layout()
fig.savefig("of_subgroups.png", dpi=130)
print("wrote of_subgroups.png")
