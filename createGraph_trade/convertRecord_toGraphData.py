# try:
#     %load_ext autoreload
#     %autoreload 2
# except:
#     pass

import argparse
import pandas as pd
import numpy as np
import sys
from itertools import combinations
sys.path.append('./..')
sys.path.append('./../..')
from pathlib import Path
import os
try:
    from common_utils import utils
except:
    from .commmon_utils import utils
from joblib import Parallel, delayed
import multiprocessing as mp
import pickle


def main(DIR):

    # Use training data for graph creation
    DATA_LOC = './../generated_data_v1/{}'.format(DIR)

    with open(os.path.join(DATA_LOC, 'domain_dims.pkl'), 'rb') as fh:
        domain_dims = pickle.load(fh)

    # ---------------------------------------
    # This data is already serialized
    # ---------------------------------------
    data_df = pd.read_csv(os.path.join(DATA_LOC, 'train_data.csv'), index_col=None, low_memory=False)
    data_df = data_df.drop_duplicates(subset=list(domain_dims.keys()))

    # ------------------------------
    # Create graph ingestible data
    # ------------------------------

    ID_COL = 'PanjivRecordID'
    node_types = sorted(domain_dims.keys())
    
    utils.convert_to_serializedID_format(
        data_df,
        DIR
    )
    
    candidate_edge_types = ['_'.join(sorted([a, b])) for a, b in combinations(node_types, 2)]

    with open('./valid_edges.txt', 'r') as fh:
        valid_edge_types = fh.readlines()
    valid_edge_types = [_.strip('\n') for _ in valid_edge_types]

    def get_edge_list(df, e_type):
        s, t = e_type.split('_')
        df_grouped = df.groupby([s, t]).size().reset_index(name='weight')
        df_grouped = df_grouped.rename(columns={s: 'source', t: 'target'})
        df_grouped['e_type'] = e_type
        return df_grouped

    list_edge_df = Parallel(mp.cpu_count())(delayed(get_edge_list)(data_df, e) for e in valid_edge_types)

    sum([len(_) for _ in list_edge_df])

    edges_df = None
    for _df in list_edge_df:
        if edges_df is not None:
            edges_df = edges_df.append(_df, ignore_index=True)
        else:
            edges_df = pd.DataFrame(_df)

    nodes_df = pd.DataFrame(columns=['ID', 'n_type'])
    
    idMapping_df = utils.fetch_idMappingFile(DIR)

    for domain in domain_dims.keys():
        tmp = pd.DataFrame(idMapping_df.loc[idMapping_df['domain'] == domain]['serial_id'])
        tmp = tmp.rename(columns={'serial_id': 'ID'})
        tmp['n_type'] = domain
        nodes_df = nodes_df.append(tmp, ignore_index=True)
    print('Number of nodes :: ',len(nodes_df), 'Number of edges ::', len(edges_df))

    # --------------------------
    # Save files
    # --------------------------
    SAVE_DIR = os.path.join(DATA_LOC, 'stage_graph')
    pathobj = Path(SAVE_DIR)
    pathobj.mkdir(exist_ok=True, parents=True)

    edges_df.to_csv(os.path.join(SAVE_DIR, 'edges.csv'), index=False)
    nodes_df.to_csv(os.path.join(SAVE_DIR, 'nodes.csv'), index=False)


parser = argparse.ArgumentParser()
parser.add_argument(
    '--DIR', choices=['us_import1', 'us_import2', 'us_import3', 'us_import4', 'us_import5', 'us_import6'],
    default='us_import1'
)

args = parser.parse_args()
DIR = args.DIR
main(DIR)
