import os
import argparse
import system_run_v1 as main_module

parser = argparse.ArgumentParser()
import seaborn as sns
from matplotlib import pyplot as plt
import time




def plot_figure(df1, df2):
    global DIR
    global feedback_batch_size
    global top_K_count

    ts = str(time.time()).split('.')[0]
    plt.figure(figsize=[6, 4])
    plt.title('Accuracy in next {} samples| Iteration(batch) : {} samples'.format(top_K_count, feedback_batch_size))
    plt.xlabel('Batch index', fontsize=14)
    plt.ylabel('Accuracy in next {} samples'.format(top_K_count), fontsize=14)
    sns.lineplot(data=df1, x="idx", y="acc", markers=True, label='Input provided')
    sns.lineplot(data=df2, x="idx", y="acc", markers=True, label='No Input')
    plt.legend(fontsize=14)
    plt.grid()
    plt.savefig('{}_results_v1_{}.png'.format(DIR, ts))
    try:
        plt.show()
    except:
        pass
    plt.close()


def checkPerformance():
    num_runs = 10
    df1 = None
    df2 = None
    for n in range(num_runs):
        results_with_input, results_no_input = main_module.main_executor()
        if df1 is None:
            df1 = results_with_input
        else:
            df1 = df1.append(results_with_input, ignore_index=True)
        if df2 is None:
            df2 = results_no_input
        else:
            df2 = df2.append(results_no_input, ignore_index=True)

    plot_figure(df1, df2)
    return

parser.add_argument(
    '--DIR',
    choices=['us_import1', 'us_import2', 'us_import3', 'us_import4', 'us_import5', 'us_import6'],
    default=None
)
parser.add_argument(
    '--feedback_size',
    type=int,
    default=10
)
parser.add_argument(
    '--top_K',
    type=int,
    default=10,
)

args = parser.parse_args()
main_module.DIR = args.DIR
main_module.feedback_batch_size = args.feedback_size
main_module.top_K_count = args.top_K
main_module.setup_config(main_module.DIR)
checkPerformance()
