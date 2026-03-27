import numpy as np
import pandas as pd

def zscore(s):
    return (s - s.mean()) / s.std()

def minmax(s):
    return (s - s.min()) / (s.max() - s.min())

def rank_percentile(s):
    return s.rank(method='average') / len(s)

def log_zscore(s):
    logged = np.log(s.clip(lower=0.001))
    return zscore(pd.Series(logged, index=s.index))

def robust_zscore(s):
    med = s.median()
    iqr = s.quantile(0.75) - s.quantile(0.25)
    return (s - med) / (iqr * 0.7413)

NORM_FUNCTIONS = {
    'zscore':  zscore,
    'minmax':  minmax,
    'rank':    rank_percentile,
    'log':     log_zscore,
    'robust':  robust_zscore,
}
