import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Pre-admission rx exposure lift (died vs survived), from rx_pre.out analysis
pre_risk = [("Lorazepam", 2.57), ("Norepinephrine", 2.44), ("Vancomycin", 2.37),
            ("Albumin 25%", 2.30), ("Phytonadione", 2.24), ("Cefepime", 2.19),
            ("Glycopyrrolate", 2.19), ("Dexamethasone", 2.17), ("Amiodarone", 1.92),
            ("Allopurinol", 1.89), ("Alteplase cath", 1.87), ("Ipratrop-Albut", 1.84)]
pre_prot = [("Oxycodone-APAP", 0.79), ("Milk of Magnesia", 0.75),
            ("Ibuprofen", 0.63), ("Ketorolac", 0.59)]
# In-ICU eMAR lift (died-in-ICU vs survived)
icu_emar = [("Micafungin", 14.54), ("CRRT priming", 13.41), ("Glycopyrrolate", 13.05),
            ("Hydrocortisone", 9.62), ("Bicarbonate", 9.62), ("Citrate 4%", 9.09),
            ("Artificial tears", 8.55), ("Chlorothiazide", 5.66),
            ("Insulin/hyperK", 5.44), ("Meropenem", 5.18), ("Midazolam", 4.74),
            ("Dextrose 50%", 4.27)]
icu_ing = [("TPN bundle", 4.07), ("Enteral feed", 2.86), ("Protein", 2.83),
           ("Calcium", 1.99), ("Blood", 1.47), ("Calories", 1.25),
           ("IVF", 1.03), ("Water", 0.99), ("Oral/gastric", 0.77),
           ("OR intake", 0.61)]

fig, axes = plt.subplots(1, 2, figsize=(12, 5.5))
ax = axes[0]
items = pre_risk + pre_prot
ax.barh([n for n, _ in items][::-1], [v for _, v in items][::-1],
        color=(["#c0392b"] * len(pre_risk) + ["#2471a3"] * len(pre_prot))[::-1])
ax.axvline(1.0, color="black", lw=0.8)
ax.set_xlabel("exposure lift: P(prior rx | died) / P(prior rx | survived)")
ax.set_title("Pre-admission prescriptions (prior stays)")
ax = axes[1]
ax.barh([n for n, _ in icu_emar][::-1], [v for _, v in icu_emar][::-1], color="#c0392b")
ax.set_xlabel("exposure lift: P(drug in ICU | died) / P(drug | survived)")
ax.set_title("In-ICU eMAR administrations (post-2014, 50% cover)")
fig.suptitle("Compound profiles: markers of dying, not causes (confounding by indication)")
fig.tight_layout()
fig.savefig("/tmp/rx_compounds.png", dpi=110)

fig, ax = plt.subplots(figsize=(8, 4.5))
ax.barh([n for n, _ in icu_ing][::-1], [v for _, v in icu_ing][::-1],
        color=["#c0392b" if v >= 1 else "#2471a3" for _, v in icu_ing][::-1])
ax.axvline(1.0, color="black", lw=0.8)
ax.set_xlabel("exposure lift (died vs survived)")
ax.set_title("In-ICU IV ingredients (89% cover; IVF/water ~1.0 = sanity check)")
fig.tight_layout()
fig.savefig("/tmp/rx_ingredients.png", dpi=110)
print("plots written")
