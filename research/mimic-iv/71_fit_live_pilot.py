#!/usr/bin/env python3
"""Historical MIMIC-IV 3.1 6h pilot, aggregate-only outputs.
This is observational validation, not causal policy evaluation.
All patient-level analysis and model predictions stay on the s0 server.
"""
import argparse
import json
import warnings
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar
from scipy.special import softmax,logsumexp
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder,StandardScaler
from sklearn.metrics import roc_auc_score,average_precision_score
from sklearn.exceptions import ConvergenceWarning

ERAS_TRAIN=['2008 - 2010','2011 - 2013','2014 - 2016']
ERAS_VAL=['2017 - 2019']
ERAS_TEST=['2020 - 2022']
FIRST=['NO_EVENT','FIRST_DOCUMENTATION','CODE_CHANGE','ICU_EXIT','DEATH']
TERMINAL=['IN_ICU','ICU_EXIT','ICU_DEATH']
FEATURES={
 'baseline':['step','age','sofa','unit_group'],
 'physiology':['step','age','sofa','unit_group','hr','map','rr','spo2'],
 'physiology_monitoring':['step','age','sofa','unit_group','hr','map','rr','spo2','n_hr','n_map','n_spo2'],
 'documented_care':['step','age','sofa','unit_group','hr','map','rr','spo2','n_hr','n_map','n_spo2','code_state','code_age_h'],
 'full_retrospective':['step','age','sofa','unit_group','hr','map','rr','spo2','n_hr','n_map','n_spo2','code_state','code_age_h','prior_invasive_h','prior_pressor_h']
}
def check(df):
    required=set(sum(FEATURES.values(),[])+['subject_id','stay_id','era','next_event','death_within6h','icu_exit_within6h','within_bin_collision','next_icu_hours'])
    absent=required-set(df.columns)
    if absent:raise ValueError('missing fields: '+str(sorted(absent)))
    for c in ['death_within6h','icu_exit_within6h','code_change_within6h','first_documentation_within6h','within_bin_collision']:
        df[c]=df[c].fillna(False).astype(bool)
    if df.step.min()<4:raise ValueError('SOFA may leak at landmarks before 24h')
    if df.duplicated(['stay_id','step']).any() or df.duplicated(['subject_id','step']).any():raise ValueError('Duplicate stay or patient landmarks')
    if (df.groupby('subject_id').era.nunique()>1).any():raise ValueError('Patient overlaps historical eras')
    if ((df.next_icu_hours<0)|(df.next_icu_hours>6.00001)).any():raise ValueError('Invalid at-risk durations')
    if ((df.next_event=='FIRST_DOCUMENTATION')&(df.code_state!='UNKNOWN')).any():raise ValueError('First documentation has prior known status')
    if ((df.next_event=='CODE_CHANGE')&(df.code_state=='UNKNOWN')).any():raise ValueError('Unknown initial status mislabeled code change')
    if ((df.next_event=='DEATH')&(~df.death_within6h)).any():raise ValueError('Death label without death event')
    if ((df.next_event=='ICU_EXIT')&(~df.icu_exit_within6h)).any():raise ValueError('Exit label without ICU exit')
    if not set(df.next_event).issubset(FIRST):raise ValueError('Unexpected first-event label')
    df['terminal_target']=np.select([df.death_within6h,df.icu_exit_within6h],['ICU_DEATH','ICU_EXIT'],default='IN_ICU')
    # Counts are computed before any fitting and are descriptive.
    return {
      'rows':int(len(df)),'patients':int(df.subject_id.nunique()),
      'era_landmarks':{str(k):int(v) for k,v in df.era.value_counts().items()},
      'first_event_counts':{str(k):int(v) for k,v in df.next_event.value_counts().items()},
      'terminal_counts':{str(k):int(v) for k,v in df.terminal_target.value_counts().items()},
      'unknown_code_pct':float(100*df.code_state.eq('UNKNOWN').mean()),
      'within_bin_collisions':int(df.within_bin_collision.sum()),
      'all_icu_deaths':int(df.death_within6h.sum()),
      'first_labeled_icu_deaths':int((df.next_event=='DEATH').sum()),
      'deaths_with_earlier_first_event':int(df.death_within6h.sum()-(df.next_event=='DEATH').sum())
    }
def make_model(cols):
    num=[c for c in cols if c not in ('unit_group','code_state')]
    cat=[c for c in cols if c in ('unit_group','code_state')]
    pre=ColumnTransformer([
        ('num',Pipeline([('impute',SimpleImputer(strategy='median',add_indicator=True)),
                         ('scale',StandardScaler())]),num),
        ('cat',Pipeline([('impute',SimpleImputer(strategy='most_frequent')),
                         ('onehot',OneHotEncoder(handle_unknown='ignore'))]),cat)
    ])
    return Pipeline([('prep',pre),('lr',LogisticRegression(C=.2,max_iter=650))])
def sorted_logits(model,x,classes):
    z=model.decision_function(x)
    names=list(model.named_steps['lr'].classes_)
    if set(names)!=set(classes):raise ValueError('Training missing classes')
    if z.ndim==1:
        if len(names)!=2:raise ValueError('Unexpected binary output')
        z=np.column_stack([-z/2.,z/2.])
    return z[:,[names.index(s) for s in classes]]
def fit_temp(z,y,classes):
    lab=np.array([classes.index(x) for x in y])
    def loss(logtemp):
        scores=z/np.exp(logtemp)
        return np.mean(logsumexp(scores,axis=1)-scores[np.arange(len(y)),lab])
    opt=minimize_scalar(loss,bounds=(-2,2),method='bounded')
    if not opt.success:raise RuntimeError('Temperature optimization failed')
    return float(np.exp(opt.x))
def per_row(y,probs,classes):
    labs=np.array([classes.index(q) for q in y],dtype=int)
    one=np.eye(len(classes))[labs]
    return -np.log(np.clip(probs[np.arange(len(y)),labs],1e-12,1.)),np.sum((probs-one)**2,axis=1)
def scoring(y,probs,classes,patients):
    ll,br=per_row(y,probs,classes)
    agg=pd.DataFrame({'id':patients,'ll':ll,'br':br}).groupby('id').mean()
    report={'n_landmarks':int(len(y)),'n_patients':int(len(agg)),
      'landmark_log_loss':float(ll.mean()),'landmark_multiclass_brier':float(br.mean()),
      'patient_equal_log_loss':float(agg.ll.mean()),'patient_equal_multiclass_brier':float(agg.br.mean())}
    for ix,name in enumerate(classes):
        truth=(y==name).astype(int)
        risk=probs[:,ix]
        m={'observed':float(truth.mean()),'predicted':float(risk.mean()),
           'brier':float(np.mean((risk-truth)**2))}
        if 0<truth.sum()<len(truth):
            m['auroc']=float(roc_auc_score(truth,risk))
            m['auprc']=float(average_precision_score(truth,risk))
        else:m['auroc']=None;m['auprc']=None
        groups=pd.qcut(pd.Series(risk).rank(method='first'),10,labels=False)
        m['calibration_deciles']=[{'n':int((groups==j).sum()),
            'predicted':float(risk[groups==j].mean()),'observed':float(truth[groups==j].mean())} for j in range(10)]
        report[name]=m
    return report
def paired(y,pa,pb,patients,classes,reps=300,seed=20261025):
    la,ba=per_row(y,pa,classes);lb,bb=per_row(y,pb,classes)
    g=pd.DataFrame({'id':patients,'n':1,'dll':lb-la,'dbr':bb-ba}).groupby('id').sum()
    mat=g[['n','dll','dbr']].to_numpy(dtype=float)
    rng=np.random.default_rng(seed);vals=np.empty((reps,2));ns=len(g)
    for k in range(reps):
        s=rng.integers(ns,size=ns);sample=mat[s]
        vals[k]=sample[:,1:].sum(axis=0)/sample[:,0].sum()
    return {'delta_logloss_B_minus_A':float((lb-la).mean()),
      'delta_brier_B_minus_A':float((bb-ba).mean()),
      'ci_logloss':[float(x) for x in np.quantile(vals[:,0],[.025,.975])],
      'ci_brier':[float(x) for x in np.quantile(vals[:,1],[.025,.975])],
      'n_test_patients':int(ns),'replicates':int(reps)}
def run(df,reps):
    cohort=check(df)
    train=df.era.isin(ERAS_TRAIN);val=df.era.isin(ERAS_VAL);test=df.era.isin(ERAS_TEST)
    if (train|val|test).sum()!=len(df):raise ValueError('Unassigned evaluation era')
    if train.sum()<1000 or val.sum()<1000 or test.sum()<1000:raise ValueError('Historical split too small')
    report={'analysis':'MIMIC-IV 3.1 observational 6h pilot, not policy effect',
      'cohort':cohort,'n_train':int(train.sum()),'n_val':int(val.sum()),'n_test':int(test.sum()),
      'caveat':'Prior support from derived interval edges may incorporate future charting; only documented-care no-support baseline is candidate for as-of audit',
      'fits':{}}
    for endpoint,classes,target in [('first_event',FIRST,'next_event'),('terminal',TERMINAL,'terminal_target')]:
        truth=df.loc[test,target].to_numpy()
        ytrain=df.loc[train,target];yval=df.loc[val,target].to_numpy()
        if set(ytrain)!=set(classes):raise ValueError('Missing class in train split: '+str(set(classes)-set(ytrain)))
        pred={};scores={};temps={}
        for name,fields in FEATURES.items():
            model=make_model(fields)
            with warnings.catch_warnings(record=True) as rec:
                warnings.simplefilter('always',ConvergenceWarning)
                model.fit(df.loc[train,fields],ytrain)
            if any(issubclass(x.category,ConvergenceWarning) for x in rec):raise RuntimeError('Fit convergence failed: '+endpoint+' '+name)
            temp=fit_temp(sorted_logits(model,df.loc[val,fields],classes),yval,classes)
            pred[name]=softmax(sorted_logits(model,df.loc[test,fields],classes)/temp,axis=1)
            temps[name]=temp
            scores[name]=scoring(truth,pred[name],classes,df.loc[test,'subject_id'].to_numpy())
        comparison={}
        for before,after in [('physiology','physiology_monitoring'),('physiology_monitoring','documented_care'),('documented_care','full_retrospective')]:
            comparison[before+'_TO_'+after]=paired(truth,pred[before],pred[after],df.loc[test,'subject_id'].to_numpy(),classes,reps)
        report['fits'][endpoint]={'class_order':classes,'temperature':temps,'models':scores,'paired':comparison}
    return report
def main():
    p=argparse.ArgumentParser()
    p.add_argument('--panel',required=True);p.add_argument('--out',required=True);p.add_argument('--reps',type=int,default=300)
    args=p.parse_args()
    df=pd.read_parquet(args.panel)
    report=run(df,args.reps)
    dest=Path(args.out);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'cohort':report['cohort'],'test_n':report['n_test'],
      'endpoint_log_loss':{k:{m:z['landmark_log_loss'] for m,z in v['models'].items()} for k,v in report['fits'].items()},
      'paired':{k:v['paired'] for k,v in report['fits'].items()}},indent=2))
if __name__=='__main__':main()
