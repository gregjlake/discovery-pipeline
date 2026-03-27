import pandas as pd

def keep_all(df):
    return df.copy()

def winsorize(df, p=0.025):
    result = df.copy()
    for col in ['x', 'y']:
        lo, hi = result[col].quantile(p), result[col].quantile(1 - p)
        result[col] = result[col].clip(lo, hi)
    return result

def remove_3sigma(df):
    mask_x = (df['x'] - df['x'].mean()).abs() <= 3 * df['x'].std()
    mask_y = (df['y'] - df['y'].mean()).abs() <= 3 * df['y'].std()
    return df[mask_x & mask_y].copy()

OUTLIER_FUNCTIONS = {
    'keep':    keep_all,
    'winsor5': lambda df: winsorize(df, 0.025),
    'winsor1': lambda df: winsorize(df, 0.005),
    'remove3': remove_3sigma,
}
