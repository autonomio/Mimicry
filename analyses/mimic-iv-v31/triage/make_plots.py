import csv
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

SHORT = {"Cardiac Vascular Intensive Care Unit (CVICU)": "CVICU",
         "Coronary Care Unit (CCU)": "CCU",
         "Medical Intensive Care Unit (MICU)": "MICU",
         "Medical/Surgical Intensive Care Unit (MICU/SICU)": "MICU/SICU",
         "Neuro Intermediate": "NeuroIMC",
         "Neuro Stepdown": "NeuroSD",
         "Neuro Surgical Intensive Care Unit (Neuro SICU)": "NeuroSICU",
         "Surgical Intensive Care Unit (SICU)": "SICU",
         "Surgery/Vascular/Intermediate": "SurgVascIMC",
         "Trauma SICU (TSICU)": "TSICU",
         "OTHER_UNIT": "OTHER"}

# ---- 1. per-unit AUC + direct rate by hour ----
pc = list(csv.DictReader(open("triage_unit_perclass.csv")))
pc.sort(key=lambda r: float(r["ovr_auc"]))
bh = list(csv.DictReader(open("triage_direct_by_hour.csv")))
fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
ax = axes[0]
ax.barh([SHORT.get(r["unit"], r["unit"]) for r in pc],
        [float(r["ovr_auc"]) for r in pc], color="#2471a3")
ax.set_xlabel("one-vs-rest AUC (unit assignment from triage-moment data)")
ax.set_title("How predictable is each unit?")
for i, r in enumerate(pc):
    ax.text(float(r["ovr_auc"]) + 0.005, i, f"n={r['n_test']}", va="center", fontsize=7)
ax = axes[1]
ax.plot([int(r["hour"]) for r in bh], [float(r["direct_rate"]) for r in bh],
        "o-", ms=3, color="#c0392b")
ax.set_xlabel("admission hour of day")
ax.set_ylabel("P(ICU within 6h of hospital admit)")
ax.set_title("Direct-ICU rate by hour (time-of-day preserved)")
ax.grid(alpha=0.3)
fig.tight_layout()
fig.savefig("triage_units_hour.png", dpi=110)

# ---- 2. unit mix night/day + direct rate by year ----
mix = list(csv.DictReader(open("triage_unitmix_night.csv")))
units = [c for c in mix[0] if c != "night"]
fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
ax = axes[0]
x = np.arange(len(units))
day = [float(mix[0][u]) for u in units]
ngt = [float(mix[1][u]) for u in units]
ax.bar(x - 0.2, day, 0.4, label="day", color="#2471a3")
ax.bar(x + 0.2, ngt, 0.4, label="night", color="#c0392b")
ax.set_xticks(x)
ax.set_xticklabels([SHORT.get(u, u) for u in units], rotation=45, ha="right", fontsize=8)
ax.set_ylabel("share of ICU admissions")
ax.set_title("Unit mix: day vs night")
ax.legend()
by = list(csv.DictReader(open("triage_direct_by_year.csv")))
ax = axes[1]
ax.plot([r["anchor_year_group"] for r in by], [float(r["direct_rate"]) for r in by],
        "o-", color="#2471a3")
ax.set_ylabel("P(ICU within 6h)")
ax.set_title("Direct-ICU rate by true year group")
ax.grid(alpha=0.3)
plt.setp(ax.get_xticklabels(), rotation=20, ha="right", fontsize=8)
fig.tight_layout()
fig.savefig("triage_mix_year.png", dpi=110)
print("plots written")
