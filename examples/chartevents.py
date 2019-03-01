import pandas as pd
import numpy as np

import wrangle as wr

f = '/Users/mikko/Downloads/CHARTEVENTS.csv.gz'
n = 330712483
c = ['HADM_ID', 'SUBJECT_ID', 'ITEMID', 'VALUENUM']

chartev = wr.utils.read_large_csv(f, n, c)

d_items = pd.read_csv('/Users/mikko/Downloads/D_ITEMS.csv.gz')

top_itemid = pd.Series(chartev[:,2]).astype(int).value_counts()
top_itemid = pd.Series(chartev[:,2]).astype(int).value_counts()
d_items = pd.read_csv('/Users/mikko/Downloads/D_ITEMS.csv.gz')
top_itemid = pd.DataFrame(top_itemid).reset_index()
top_itemid.columns = ['ITEMID', 'COUNT']
d_items = pd.merge(d_items, top_itemid)[['ITEMID', 'LABEL', 'COUNT']]


import time
from IPython.display import clear_output

for i in range(20, 1000, 20):

    print(d_items.sort_values('COUNT', ascending=False).head(i).tail(20))
    
    time.sleep(5)
    clear_output()
