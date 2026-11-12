import csv
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def load(path):
    rows = {}
    with open(path) as f:
        for r in csv.DictReader(f):
            rows.setdefault(r["cohort"], []).append(r)
    return rows


def series(rows, cohort, vital, xkey, keys):
    pts = []
    for r in rows[cohort]:
        if r["vital"] != vital:
            continue
        pts.append(tuple([int(r[xkey])] + [float(r[k]) for k in keys]))
    return sorted(pts)


# ---- 1. sensitivity ----
VITALS = [("hr", "Heart rate (bpm)"), ("rr", "Resp. rate (/min)"),
          ("spo2", "SpO2 (%)"), ("map", "MAP (mmHg)"), ("tempc", "Temp (C)")]
sens = load("../outputs/mimic_sensitivity.csv")
fig, axes = plt.subplots(5, 1, figsize=(9, 13), sharex=True)
cols = {"died_all": ("#c0392b", "died, all (n=7329)"),
        "died_gap2h": ("#e67e22", "died, monitored<=2h"),
        "survived": ("#2471a3", "survived")}
for ax, (v, label) in zip(axes, VITALS):
    for cohort, (color, name) in cols.items():
        pts = series(sens, cohort, v, "hours_before", ["median", "p25", "p75"])
        x = [-p[0] for p in pts]
        ax.plot(x, [p[1] for p in pts], color=color, lw=1.5,
                label=name if v == "hr" else None)
        ax.fill_between(x, [p[2] for p in pts], [p[3] for p in pts],
                        color=color, alpha=0.12)
    ax.set_ylabel(label)
    ax.grid(alpha=0.3)
axes[0].legend(fontsize=8)
axes[0].set_title("Sensitivity: all decedents vs continuously-monitored decedents vs survivors")
axes[-1].set_xlabel("hours before death / discharge")
fig.tight_layout()
fig.savefig("mimic_sensitivity.png", dpi=110)

# ---- 2. finegrain ----
fine = load("../outputs/mimic_finegrain.csv")
fig, axes = plt.subplots(3, 1, figsize=(9, 9), sharex=True)
for ax, (v, label) in zip(axes, [("hr", "Heart rate (bpm)"),
                                 ("spo2", "SpO2 (%)"), ("map", "MAP (mmHg)")]):
    for cohort, color in (("died", "#c0392b"), ("survived", "#2471a3")):
        pts = series(fine, cohort, v, "bin5", ["median", "p25", "p75", "n_stays"])
        x = [-p[0] * 5 / 60 for p in pts]
        ax.plot(x, [p[1] for p in pts], color=color, lw=1.2)
        ax.fill_between(x, [p[2] for p in pts], [p[3] for p in pts],
                        color=color, alpha=0.15)
    ax.set_ylabel(label)
    ax.grid(alpha=0.3)
axes[0].set_title("Last 6h at 5-min resolution, still-monitored subset (gap<=1h)")
axes[-1].set_xlabel("hours before death / discharge")
fig.tight_layout()
fig.savefig("mimic_finegrain.png", dpi=110)

# ---- 3. labs ----
labs = load("../outputs/mimic_labs.csv")
fig, axes = plt.subplots(1, 2, figsize=(9, 4), sharex=True)
for ax, (v, label) in zip(axes, [("lactate", "Lactate (mmol/L)"),
                                 ("creat", "Creatinine (mg/dL)")]):
    for cohort, color in (("died", "#c0392b"), ("survived", "#2471a3")):
        pts = [p for p in series(labs, cohort, v, "bin6", ["median", "p25", "p75"]) if p[0] <= 3]
        x = [-(p[0] * 6 + 3) for p in pts]
        med = [p[1] for p in pts]
        ax.errorbar(x, med,
                    yerr=[[m - lo for _, m, lo, _ in pts],
                          [hi - m for _, m, _, hi in pts]],
                    color=color, marker="o", capsize=4, label=cohort)
    ax.set_ylabel(label)
    ax.set_xlabel("hours before (6h bins)")
    ax.grid(alpha=0.3)
axes[0].legend()
axes[0].set_title("Lactate and creatinine before ICU death vs discharge")
fig.tight_layout()
fig.savefig("mimic_labs.png", dpi=110)

# ---- 4. pressors + GCS ----
fig, axes = plt.subplots(1, 2, figsize=(10, 4))
pr = load("../outputs/mimic_pressors.csv")
ax = axes[0]
for cohort, color in (("died", "#c0392b"), ("survived", "#2471a3")):
    pts = sorted((int(r["hour_before"]), float(r["pct_on_pressor"])) for r in pr[cohort])
    pts = list(pts)
    ax.plot([-h for h, _ in pts], [p for _, p in pts], color=color, lw=1.8, label=cohort)
ax.set_ylabel("% stays on pressors")
ax.set_xlabel("hours before death / discharge")
ax.set_title("Pressor exposure (withdrawn approaching death)")
ax.legend()
ax.grid(alpha=0.3)
gcs = load("../outputs/mimic_gcs.csv")
ax = axes[1]
for cohort, color in (("died", "#c0392b"), ("survived", "#2471a3")):
    pts = []
    for r in gcs[cohort]:
        pts.append((int(r["hours_before"]), float(r["median_gcs"]),
                    float(r["p25"]), float(r["p75"])))
    pts.sort()
    ax.plot([-h for h, _, _, _ in pts], [m for _, m, _, _ in pts],
            color=color, lw=1.8, label=cohort)
    ax.fill_between([-h for h, _, _, _ in pts],
                    [l for _, _, l, _ in pts], [u for _, _, _, u in pts],
                    color=color, alpha=0.15)
ax.set_ylabel("GCS total (median +/- IQR)")
ax.set_xlabel("hours before death / discharge")
ax.set_title("Glasgow Coma Scale")
ax.legend()
ax.grid(alpha=0.3)
fig.tight_layout()
fig.savefig("mimic_pressors_gcs.png", dpi=110)
print("plots written")
