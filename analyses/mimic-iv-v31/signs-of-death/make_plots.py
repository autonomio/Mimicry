"""Plots for the signs-of-death gap study.

Inputs (from s0): sd_*.csv. Outputs: sd_vitals/hrv/clock/cos/cause/wd/
oliguria pngs.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

SIGS = ["hr", "map", "rr", "spo2", "temp"]
PRETTY = {"hr": "Heart rate (bpm)", "map": "MAP (mmHg)",
          "rr": "Resp rate (/min)", "spo2": "SpO2 (%)",
          "temp": "Temp (C)"}

# 1. vital trajectories dec vs surv
traj = pd.read_csv("sd_traj.csv")
fig, axes = plt.subplots(2, 3, figsize=(12, 7), sharex=True)
axes = axes.ravel()
for ax, sig in zip(axes[:5], SIGS):
    t = traj[traj["sig"] == sig].sort_values("hbd")
    x = -t["hbd"]
    ax.plot(x, t["mean_d"], "r-", label="Decedents")
    ax.fill_between(x, t["mean_d"] - 1.96 * t["sem_d"],
                    t["mean_d"] + 1.96 * t["sem_d"], color="r", alpha=0.2)
    ax.plot(x, t["mean_s"], "b-", label="Survivors")
    ax.fill_between(x, t["mean_s"] - 1.96 * t["sem_s"],
                    t["mean_s"] + 1.96 * t["sem_s"], color="b", alpha=0.2)
    ax.set_title(PRETTY[sig])
    ax.set_xlabel("Hours before death/discharge")
axes[5].axis("off")
axes[0].legend(fontsize=8)
fig.suptitle("Vital signs in the last 72h: dying vs discharge")
fig.tight_layout()
fig.savefig("sd_vitals.png", dpi=130)
print("wrote sd_vitals.png")

# 2. HRV proxies
hrv = pd.read_csv("sd_hrv.csv")
fig, axes = plt.subplots(1, 2, figsize=(10, 4), sharex=True)
for ax, col, title in [(axes[0], "wsd", "Within-hour HR sd (bpm)"),
                       (axes[1], "succ_d",
                        "Successive-hour HR change (bpm)")]:
    for grp, c in [("dec", "r"), ("surv", "b")]:
        g = hrv[hrv["grp"] == grp].sort_values("hbd")
        ax.plot(-g["hbd"], g[col], color=c, label=grp)
    ax.set_title(title)
    ax.set_xlabel("Hours before death/discharge")
axes[0].legend(fontsize=8)
fig.suptitle("Heart-rate variability proxies before death")
fig.tight_layout()
fig.savefig("sd_hrv.png", dpi=130)
print("wrote sd_hrv.png")

# 3. clock hours
fig, axes = plt.subplots(2, 2, figsize=(11, 7), sharey=False)
axes = axes.ravel()
for ax, fn, title in [(axes[0], "sd_death_hour.csv", "Death"),
                      (axes[1], "sd_admit_hour.csv", "Admission"),
                      (axes[2], "sd_dnr_hour.csv", "First DNR/CMO")]:
    t = pd.read_csv(fn)
    t = t[pd.notna(t[t.columns[0]])].sort_values(t.columns[0])
    hcol = t.columns[0]
    ax.bar(t[hcol].astype(int), t["n"], width=0.9)
    ax.set_title(f"Hour of {title} (local clock)")
    ax.set_xlabel("Hour")
    ax.set_xlim(-1, 24)
wd = pd.read_csv("sd_death_hour_wd.csv", index_col=0)
wd = wd.reindex(range(24)).fillna(0)
axes[3].bar(wd.index - 0.2, wd["True"], width=0.4, label="DNR/CMO before death")
axes[3].bar(wd.index + 0.2, wd["False"], width=0.4, label="Full code")
axes[3].set_title("Hour of death by withdrawal status")
axes[3].set_xlabel("Hour")
axes[3].legend(fontsize=8)
fig.suptitle("When do deaths happen (validity: admissions must peak "
             "afternoon/evening)")
fig.tight_layout()
fig.savefig("sd_clock.png", dpi=130)
print("wrote sd_clock.png")

# 4. cosinor amplitudes
fig, axes = plt.subplots(1, 2, figsize=(9, 4), sharey=False)
for ax, sig in zip(axes, ["temp", "hr"]):
    t = pd.read_csv(f"sd_cos_{sig}.csv")
    piv = t.pivot(index="day", columns="grp", values="amp")
    piv.plot(kind="bar", ax=ax, rot=0)
    ax.set_title(f"Circadian amplitude: {sig}")
    ax.set_xlabel("Days before death/discharge")
fig.suptitle("Loss of 24h rhythmicity approaching death")
fig.tight_layout()
fig.savefig("sd_cos.png", dpi=130)
print("wrote sd_cos.png")

# 5. cause trajectories
fig, axes = plt.subplots(1, 3, figsize=(13, 4), sharex=True)
for ax, sig in zip(axes, ["hr", "map", "rr"]):
    t = pd.read_csv(f"sd_cause_{sig}.csv", index_col=0)
    for c in t.columns:
        ax.plot(-t.index.values, t[c].values, label=c)
    ax.set_title(PRETTY[sig])
    ax.set_xlabel("Hours before death")
axes[0].legend(fontsize=8)
fig.suptitle("Dying trajectories by cause group (decedents)")
fig.tight_layout()
fig.savefig("sd_cause.png", dpi=130)
print("wrote sd_cause.png")

# 6. withdrawal split
fig, axes = plt.subplots(1, 2, figsize=(10, 4), sharex=True)
for ax, sig in zip(axes, ["map", "hr"]):
    t = pd.read_csv(f"sd_wd_{sig}.csv", index_col=0)
    for c in t.columns:
        ax.plot(-t.index.values, t[c].values, label=c)
    ax.set_title(PRETTY[sig])
    ax.set_xlabel("Hours before death")
axes[0].legend(fontsize=8)
fig.suptitle("Full-code deaths vs post-DNR/CMO deaths")
fig.tight_layout()
fig.savefig("sd_wd.png", dpi=130)
print("wrote sd_wd.png")

# 7. oliguria (Hui validation)
og = pd.read_csv("sd_oliguria.csv")
fig, ax = plt.subplots(figsize=(8, 4.5))
for grp, c in [("dec", "r"), ("surv", "b")]:
    g = og[og["grp"] == grp].sort_values("hbd")
    ax.plot(-g["hbd"], g["olig05"], color=c,
            label=f"{grp} <0.5 mL/kg/h")
    ax.plot(-g["hbd"], g["olig03"], color=c, linestyle="--",
            label=f"{grp} <0.3 mL/kg/h")
ax.set_xlabel("Hours before death/discharge")
ax.set_ylabel("Share oliguric/anuric")
ax.set_title("Oliguria before death (Hui late sign, instrumented)")
ax.legend(fontsize=8)
fig.tight_layout()
fig.savefig("sd_oliguria.png", dpi=130)
print("wrote sd_oliguria.png")
