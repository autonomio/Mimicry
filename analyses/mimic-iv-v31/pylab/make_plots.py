import csv
from collections import defaultdict
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

LABELS = {"50963": "NTproBNP", "50924": "Ferritin", "52073": "Abs eosino",
          "51003": "Troponin T", "52135": "Immature gran", "51200": "Eosinophils%",
          "51006": "BUN", "52075": "Abs neutro", "51516": "Urine WBC",
          "51244": "Lymphocytes%", "51146": "Basophils%", "50885": "Bilirubin tot",
          "50878": "AST", "50813": "Lactate", "51133": "Abs lympho",
          "50911": "CK-MB", "50912": "Creatinine", "51301": "WBC",
          "51476": "Urine epi cells", "50889": "CRP", "51099": "Prot/creat u",
          "50883": "Bilirubin dir", "50915": "D-dimer", "51070": "Alb/creat u",
          "52006": "UTX3", "51069": "Albumin u", "51288": "ESR",
          "51102": "Protein u", "51257": "Nucl RBC", "51482": "Hyaline casts",
          "50934": "H (blood)", "50863": "Alk phos", "52069": "Abs baso",
          "51484": "Ketone u"}

# ---- coverage top 20 (v1 Q3) ----
cov = []
with open("pylab_sweep.out") as f:
    for line in f:
        if line.startswith("Q3_top"):
            p = next(csv.reader([line]))
            cov.append((p[2], int(p[5])))
cov = cov[:20]
fig, ax = plt.subplots(figsize=(9, 5))
ax.barh([c[0] for c in cov][::-1], [c[1] for c in cov][::-1], color="#2471a3")
ax.set_xlabel("admissions with >=1 prior-year result (of 546,028)")
ax.set_title("Prior-year lab coverage: top 20 tests")
for i, (name, n) in enumerate(reversed(cov)):
    ax.text(n + 3000, i, f"{n//1000}k", va="center", fontsize=7)
fig.tight_layout()
fig.savefig("pylab_coverage.png", dpi=110)


def load_v2(tag):
    d = defaultdict(dict)
    with open("pylab_sweep_v2.out") as f:
        for line in f:
            if line.startswith(tag):
                p = line.strip().split(",")
                d[p[1]][p[2]] = (int(p[3]), float(p[4]))
    return d


def gaps(d):
    rows = []
    for item, g in d.items():
        if "0" not in g or "1" not in g:
            continue
        (n0, m0), (n1, m1) = g["0"], g["1"]
        if min(n0, n1) < 2000 or m0 == 0:
            continue
        rows.append(((m1 - m0) / m0, item, m0, m1, min(n0, n1)))
    rows.sort(key=lambda r: -abs(r[0]))
    return rows[:15]


fig, axes = plt.subplots(1, 2, figsize=(12, 5.5))
for ax, (tag, title) in zip(axes, [("Q5_death", "Died vs survived"),
                                   ("Q6_icu", "ICU vs floor (no ICU)")]):
    rows = gaps(load_v2(tag))
    names = [LABELS.get(it, it) for _, it, _, _, _ in rows]
    vals = [r for r, _, _, _, _ in rows]
    cols = ["#c0392b" if v > 0 else "#2471a3" for v in vals]
    ax.barh(names[::-1], [v * 100 for v in vals][::-1], color=cols[::-1])
    ax.set_xlabel("last pure-history value, median gap % (red = higher in event group)")
    ax.set_title(f"{title}\n(prior-year labs older than 24h pre-admission)")
fig.tight_layout()
fig.savefig("pylab_signal.png", dpi=110)
print("plots written")
