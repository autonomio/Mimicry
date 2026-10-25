#!/usr/bin/env python3
import json, warnings
from pathlib import Path
import numpy as np, pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder,StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss, brier_score_loss
from scipy.special import softmax
from scipy.optimize import minimize_scalar
warnings.filterwarnings('ignore',category=FutureWarning)
ROOT=Path('/srv/mimic-iv/studies/decision_feedback_20261025')
df=pd.read_parquet(ROOT/'multistate_6h_panel.parquet')
classes=np.array(['CODE_CHANGE','DEATH','ICU_EXIT','STABLE'])
assert df.groupby(['stay_id','step']).size().max()==1
assert df.subject_id.nunique()==df.stay_id.nunique()
assert (df.step>=4).all()
assert (df.next_icu_hours>0).all()
a=df.era.isin(['2008 - 2010','2011 - 2013','2014 - 2016'])
b=df.era.eq('2017 - 2019')
c=df.era.eq('2020 - 2022')
assert a.sum()+b.sum()+c.sum()==len(df)
assert not set(df.loc[a,'subject_id'])&set(df.loc[c,'subject_id'])
feature_sets={
 'demographics':['age','step','unit_group'],
 'physiology':['age','step','unit_group','sofa','hr','map','rr','spo2'],
 'observation':['age','step','unit_group','sofa','hr','map','rr','spo2','n_hr','n_map','n_spo2'],
 'code_status':['age','step','unit_group','sofa','hr','map','rr','spo2','code_state','code_age_h'],
 'treatment_history':['age','step','unit_group','sofa','hr','map','rr','spo2','prior_invasive_h','prior_pressor_h'],
 'care_history':['age','step','unit_group','sofa','hr','map','rr','spo2','n_hr','n_map','n_spo2','prior_invasive_h','prior_pressor_h','code_state','code_age_h']
}
df['code_state']=df.code_state.fillna('UNKNOWN')
target=df.next_event.to_numpy()
yva=target[b.to_numpy()]
yte=target[c.to_numpy()]
results={'n_rows':int(len(df)),'n_subjects':int(df.subject_id.nunique()),
 'splits':{'train':int(a.sum()),'val':int(b.sum()),'test':int(c.sum())},
 'test_events':df.loc[c,'next_event'].value_counts().to_dict(),'models':{}}
preds={}
for name,features in feature_sets.items():
 cats=[x for x in features if x in ('unit_group','code_state')]
 nums=[x for x in features if x not in cats]
 prep=ColumnTransformer([
  ('num',Pipeline([('fill',SimpleImputer(strategy='median',add_indicator=True)),('scale',StandardScaler())]),nums),
  ('cat',OneHotEncoder(handle_unknown='ignore'),cats)
 ])
 model=Pipeline([('prep',prep),('model',LogisticRegression(max_iter=110,solver='lbfgs',class_weight=None))])
 model.fit(df.loc[a,features],target[a.to_numpy()])
 cls=model.named_steps['model'].classes_
 order=np.array([np.where(cls==k)[0][0] for k in classes])
 pv=model.predict_proba(df.loc[b,features])[:,order]
 pt=model.predict_proba(df.loc[c,features])[:,order]
 # Temperature scaling on validation set; no test-set calibration.
 def lnt(t):
  logits=np.log(np.maximum(pv,1e-9))
  pp=softmax(logits/np.exp(t),axis=1)
  return log_loss(yva,pp,labels=classes)
 opt=minimize_scalar(lnt,bounds=(-1,1.5),method='bounded')
 T=float(np.exp(opt.x))
 p=softmax(np.log(np.maximum(pt,1e-9))/T,axis=1)
 preds[name]=p
 ll=float(log_loss(yte,p,labels=classes))
 onehot=(yte[:,None]==classes).astype(float)
 br=float(np.mean(np.sum((p-onehot)**2,axis=1)))
 results['models'][name]={'test_log_loss':ll,'test_multiclass_brier':br,'validation_temperature':T,
 'perclass_test_observed':{k:float(np.mean(yte==k)) for k in classes},
 'perclass_test_predicted':{k:float(p[:,i].mean()) for i,k in enumerate(classes)}}
 print(name,round(ll,5),round(br,5),flush=True)
# Paired patient cluster uncertainty, proper sample-level difference in log score.
yind=np.array([np.where(classes==label)[0][0] for label in yte])
lo=-np.log(np.maximum(preds['physiology'][np.arange(len(yte)),yind],1e-9))
hi=-np.log(np.maximum(preds['care_history'][np.arange(len(yte)),yind],1e-9))
delta=lo-hi
patient=df.loc[c,'subject_id'].to_numpy()
tmp=pd.DataFrame({'id':patient,'delta':delta}).groupby('id').agg(n=('delta','size'),score=('delta','sum'))
sum_score=tmp.score.to_numpy();sum_n=tmp.n.to_numpy()
rng=np.random.default_rng(20261025)
ii=rng.integers(0,len(tmp),size=(500,len(tmp)))
boot=(sum_score[ii].sum(axis=1)/sum_n[ii].sum(axis=1))
results['eventwise_loss']={}
for state in classes:
 idx=(yte==state)
 results['eventwise_loss'][str(state)]={'n':int(idx.sum()),
 'physiology':float(lo[idx].mean()),'care_history':float(hi[idx].mean()),
 'paired_gain':float(delta[idx].mean())}
results['paired_phys_vs_care']={'logloss_gain':float(delta.mean()),
'patient_bootstrap_95ci':np.quantile(boot,[.025,.975]).tolist(),
'bootstrap_reps':500}
# Stratified hold-out calibration, no retraining.
for group,frame in df.loc[c].groupby('code_state'):
 if len(frame)<100:continue
 indices=np.flatnonzero(c.to_numpy())
 pos=np.flatnonzero(df.loc[c,'code_state'].to_numpy()==group)
 results.setdefault('test_code_strata',{})[str(group)]={'n':int(len(pos)),
  'care_history_logloss':float(log_loss(yte[pos],preds['care_history'][pos],labels=classes))}
(ROOT/'multistate_realfit_report.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps({'paired_phys_vs_care':results['paired_phys_vs_care']},indent=2))
