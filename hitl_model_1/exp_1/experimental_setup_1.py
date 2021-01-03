#!/usr/bin/env python
# coding: utf-8

# In[75]:


try:
    get_ipython().run_line_magic('load_ext', 'autoreload')
    get_ipython().run_line_magic('autoreload', '2')
except:
    pass


import pandas as pd
import numpy as np
import os
import sys
import glob
from sklearn.preprocessing import normalize
sys.path.append('./..')
sys.path.append('./../..')
from pathlib import Path
from tqdm import tqdm
import pickle
import copy
try:
    from IPython.display import display
except:
    pass
import json
from onlineGD import onlineGD
import linear_model
import seaborn as sns
from matplotlib import pyplot as plt
import argparse



parser = argparse.ArgumentParser()
parser.add_argument(
    '--DIR', choices=['us_import1', 'us_import2', 'us_import3','us_import4'],
    default=None
)


args = parser.parse_args()
DIR = args.DIR

# ============================================


embedding_path  = './../../createGraph_trade/saved_model_data/{}'.format(DIR)
serialID_mapping_loc = './../../generated_data_v1/{}/idMapping.csv'.format(DIR)
idMapper_file = os.path.join(serialID_mapping_loc)
mapping_df = pd.read_csv(idMapper_file, index_col=None)
serialID_to_entityID = {}

for i, row in mapping_df.iterrows():
    serialID_to_entityID[row['serial_id']] = row['entity_id']

anomalies_pos_fpath = './../../generated_data_v1/generated_anomalies/{}/pos_anomalies.csv'.format(DIR)
anomalies_neg_fpath = './../../generated_data_v1/generated_anomalies/{}/neg_anomalies.csv'.format(DIR)
anom_pos_df = pd.read_csv(anomalies_pos_fpath, index_col=None)
anom_neg_df = pd.read_csv(anomalies_neg_fpath, index_col=None)



class record_obj:
    embedding = None
    serialID_to_entityID = None
    @staticmethod
    def __setup_embedding__(embedding_path, serialID_to_entityID, _normalize = True):
        record_obj.embedding = {}
        record_obj.serialID_to_entityID = serialID_to_entityID
        files =  glob.glob(os.path.join(embedding_path,'**.npy'))
        for f in sorted(files):
            emb = np.load(f)
            domain = f.split('/')[-1].split('_')[-1].split('.')[0]
            if _normalize:
                emb = normalize(emb,axis=1)
            record_obj.embedding[domain] = emb
        return
    
    def __init__(self, _record, _label):
        id_col = 'PanjivaRecordID'
        self.id = _record[id_col]
        domains = list(record_obj.embedding.keys())
        self.x = []
        self.label = _label
        for d,e in _record.items():
            if d == id_col: continue
            non_serial_id = serialID_to_entityID[e]
            self.x.append(record_obj.embedding[d][non_serial_id])
        self.x = np.array(self.x)

record_obj.__setup_embedding__(embedding_path, serialID_to_entityID, _normalize=True)

emb_dim = record_obj.embedding['HSCode'].shape[1]


def obtain_normal_samples(DIR):
    normal_data = pd.read_csv(
        './../../generated_data_v1/{}/stage_2/test_serialized.csv'.format(DIR), index_col= None
    )
    
    _df =  normal_data.sample(5000)
    obj_list = []
    for i in tqdm(range(_df.shape[0])):
        obj = record_obj(_df.iloc[i].to_dict(),-1)
        obj_list.append(obj)
    data_x = []
    for _obj in obj_list:
        data_x.append(_obj.x)
    data_x = np.stack(data_x)
    return data_x

obj_list = []
for i in tqdm(range(anom_neg_df.shape[0])):
    obj = record_obj(anom_neg_df.iloc[i].to_dict(),-1)
    obj_list.append(obj)
    
for i in tqdm(range(anom_pos_df.shape[0])):
    obj = record_obj(anom_pos_df.iloc[i].to_dict(),1)
    obj_list.append(obj)

# Read in the explantions

explantions_f_path =  './../../generated_data_v1/generated_anomalies/{}/pos_anomalies_explanations.json'.format(DIR)
with open(explantions_f_path,'rt') as fh:
    explanations = json.load(fh)
explanations = { int(k): [sorted (_) for _ in v] for k,v in explanations.items()}

domain_dims = None
with open('./../../generated_data_v1/{}/domain_dims.pkl'.format(DIR), 'rb') as fh :
    domain_dims = pickle.load(fh)

num_domains = len(domain_dims)
domain_idx = { e[0]:e[1] for e in enumerate(domain_dims.keys())}
domain_list = list(domain_dims.keys())

domainInteraction_index = {}
k = 0 
for i in range(num_domains):
    for j in range(i+1,num_domains):
        domainInteraction_index['_'.join((domain_idx[i] , domain_idx[j]))] = k
        k+=1


data_x = []
data_id = []
data_label = []
data_ID_to_matrix = {}
for _obj in obj_list:
    data_x.append(_obj.x)
    data_id.append(_obj.id)
    data_label.append(_obj.label)
    data_ID_to_matrix[_obj.id] = _obj.x
data_x = np.stack(data_x)
data_label = np.array(data_label)
data_id = np.array(data_id)


idx = np.arange(len(data_id),dtype=int)
np.random.shuffle(idx)

data_x = data_x[idx]
data_label = data_label[idx]
data_id = data_id[idx]


X_0 = data_x 
X_1 = obtain_normal_samples(DIR)

y_0 = np.ones(X_0.shape[0])
y_1 = -1 * np.ones(X_1.shape[0])
y = np.hstack([y_0,y_1])
X = np.vstack([X_0,X_1])


def get_trained_classifier( X,y , num_domains, emb_dim, num_epochs=10000):
    classifier_obj = linear_model.linearClassifier(
        num_domains = num_domains , emb_dim = emb_dim, num_epochs=num_epochs
    )

    # classifier_obj.fit_on_pos(X, np.ones(X.shape[0]),n_epochs=10000)
    classifier_obj.fit(X, y)
    classifier_obj.fit_on_pos( X, y, n_epochs=5000)
    return classifier_obj

classifier_obj = get_trained_classifier(X,y , num_domains, emb_dim)
      

num_coeff = len(domainInteraction_index)
W = classifier_obj.W.cpu().data.numpy()
emb_dim = W.shape[-1]

# classifier_obj.predict_score_op(X_0)

# Create a referece dataframe  :: data_reference_df

working_df = pd.DataFrame(
    data = np.vstack([data_id, data_label]).transpose(), 
    columns=['PanjivaRecordID', 'label'] 
)

working_df['baseID'] = working_df['PanjivaRecordID'].apply(lambda x : str(x)[:-3])
working_df['expl_1'] = -1
working_df['expl_2'] = -1
working_df['original_score'] = 1

for i,row in working_df.iterrows():
    _id = int(row['PanjivaRecordID'])
    if _id in explanations.keys():
        entry = explanations[_id]
        domain_1 = entry[0][0]
        domain_2 = entry[0][1]
        working_df.loc[i,'expl_1']= domainInteraction_index['_'.join(sorted( [domain_1, domain_2]))]
        domain_1 = entry[1][0]
        domain_2 = entry[1][1]
        working_df.loc[i,'expl_2'] = domainInteraction_index['_'.join(sorted( [domain_1, domain_2]))]
    _x = data_ID_to_matrix[_id]
    working_df.loc[i,'original_score'] = classifier_obj.predict_score_op(np.array([_x]))[0]

working_df['cur_score']  = working_df['original_score'].values
data_reference_df = working_df.copy()

def execute(
    clf_obj,
    working_df,
    domainInteraction_index,
    check_next = 20,
    batch_size = 10
):

    BATCH_SIZE = batch_size
    working_df['delta'] = 0
    obj = onlineGD(num_coeff,emb_dim)
    W = clf_obj.W.cpu().data.numpy()
    obj.set_original_W(W)

    num_batches = len(working_df.loc[working_df['label']==1])//BATCH_SIZE + 5
    acc = []
    for b in range(num_batches):
        cur = working_df.head(BATCH_SIZE)
        flags = [] # Whether a pos anaomaly or not
        terms = [] # Explanation terms

        x = [] 
        for i,row in cur.iterrows():
            _mask = np.zeros(len(domainInteraction_index))
            if row['label'] == 1:
                _mask[row['expl_1']] = 1
                _mask[row['expl_2']] = 1
                flags.append(1)
                terms.append((row['expl_1'],row['expl_2'],))
            else:
                flags.append(0)
                terms.append(())
            x.append(data_ID_to_matrix[row['PanjivaRecordID']])
        if len(x) < 2:
            break
        x = np.array(x)
    
        final_gradient, _W = obj.update_weight(
            flags,
            terms,
            x
        )

        # Update weights
        clf_obj.update_W(_W)
        working_df = working_df.iloc[BATCH_SIZE:]
        # Obtain scores
        x_test = []
        for _id in  working_df['PanjivaRecordID'].values:
            x_test.append( data_ID_to_matrix[_id] )
        x_test = np.array(x_test)
        new_scores =  clf_obj.predict_score_op(x_test)
        old_scores = working_df['cur_score'].values
        _delta = new_scores - old_scores
        working_df['delta'] = _delta
        working_df = working_df.sort_values(by='delta', ascending =False)
        working_df = working_df.reset_index(drop=True)
        tmp = working_df.head(check_next)
        _labels = tmp['label'].values

        res = len(np.where(_labels==1)[0])
        _acc = res/check_next
        acc.append(_acc)
    return acc

def execute_no_input(
    working_df,
    check_next = 20,
    batch_size = 10
):
    
    BATCH_SIZE = batch_size
    working_df['delta'] = 0

    num_batches = len(working_df.loc[working_df['label']==1])//BATCH_SIZE + 5
    acc = []
    for b in range(num_batches):
        working_df = working_df.iloc[BATCH_SIZE:]
        working_df = working_df.reset_index(drop=True)
        tmp = working_df.head(check_next)
        _labels = tmp['label'].values

        res = len(np.where(_labels==1)[0])
        _acc = res/check_next
        acc.append(_acc)
    return acc
    

num_runs = 20
cumulative_results = pd.DataFrame(columns=['idx','acc'])
results_no_input = pd.DataFrame(columns=['idx','acc'])


for i in range(num_runs):
    cur_df = data_reference_df.copy()
    cur_df = cur_df.sample(frac=1).reset_index(drop=True)
    acc = execute(
            clf_obj = copy.deepcopy(classifier_obj),
            working_df = cur_df,
            domainInteraction_index = domainInteraction_index,
            check_next = 50,
            batch_size = 10
    )
    _tmpdf = pd.DataFrame( [(e[0],e[1]) for e in enumerate(acc)], columns=['idx','acc'] )
    cumulative_results = cumulative_results.append(
       _tmpdf, ignore_index=True
    )
    
    acc = execute_no_input(
            working_df = cur_df,
            check_next = 50,
            batch_size = 10
    )
    _tmpdf = pd.DataFrame( [(e[0],e[1]) for e in enumerate(acc)], columns=['idx','acc'] )
    results_no_input = results_no_input.append(
       _tmpdf, ignore_index=True
    )
    

plt.figure(figsize=[6,4])
plt.title('Accuracy in next 50 samples| Iteration(batch) : 10 samples')
plt.xlabel('Batch index',fontsize=14)
plt.ylabel('Accuracy in next 50 samples', fontsize=14)
sns.lineplot(data=cumulative_results, x="idx", y="acc",markers=True, label = 'Input provided')
sns.lineplot(data=results_no_input, x="idx", y="acc",markers=True, label='No Input')
plt.legend(fontsize=14)
plt.grid()
plt.savefig('{}_results_v1.png'.format(DIR))
try:
    plt.show()
except:
    pass
plt.close()


# In[ ]:



