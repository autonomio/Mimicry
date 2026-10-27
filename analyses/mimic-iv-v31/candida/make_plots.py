import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

groups = ["neither\n(n=83,254)", "micafungin\nno candida\n(n=1,717)",
          "candida\nno micafungin\n(n=64)", "candida +\nmicafungin\n(n=207)"]
icu = [6.2, 26.9, 73.4, 35.3]
hosp = [10.2, 47.3, 84.4, 43.5]
x = np.arange(4)
fig, ax = plt.subplots(figsize=(9, 5))
ax.bar(x - 0.2, icu, 0.4, label="died in ICU", color="#c0392b")
ax.bar(x + 0.2, hosp, 0.4, label="died in hospital", color="#7d3c98")
ax.set_xticks(x)
ax.set_xticklabels(groups)
ax.set_ylabel("mortality %")
ax.set_title("Candidemia x micafungin: fungus vs host (first ICU stays)")
ax.legend()
for i, (a, b) in enumerate(zip(icu, hosp)):
    ax.text(i - 0.2, a + 1, f"{a}%", ha="center", fontsize=8)
    ax.text(i + 0.2, b + 1, f"{b}%", ha="center", fontsize=8)
fig.tight_layout()
fig.savefig("/tmp/candida_2x2.png", dpi=110)
print("plot written")
