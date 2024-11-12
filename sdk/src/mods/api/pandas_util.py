import pandas as pd


def pd_apply_and_insert(df, column_name, func):
    # Apply the function to the specified column
    new_df = func(df[column_name])

    # Rename the new columns
    new_df.columns = [f"{column_name}.{col}" for col in new_df.columns]

    # Find the location of the source column
    col_idx = df.columns.get_loc(column_name)

    # Split the DataFrame into two parts
    left = df.iloc[:, : col_idx + 1]
    right = df.iloc[:, col_idx + 1 :]

    # Concatenate the parts with the new DataFrame in between
    result_df = pd.concat([left, new_df, right], axis=1)

    return result_df


def find_rows_with_vals(df, vals_df):
    df_str = df.astype(str)
    vals_df_str = vals_df.astype(str)

    if len(df) == 0:
        return df

    merged_df = df_str.merge(vals_df_str, how="left", indicator=True)
    return df.loc[merged_df["_merge"] == "both"]


def get_unflat_value(series: pd.Series, key_prefix: str):
    # TODO: this drops None which is no good
    series = series.dropna()

    # Exact match
    if key_prefix in series.index:
        return series[key_prefix]

    # Prefixed match
    prefix_with_dot = key_prefix + "."
    matched_columns = {
        col: series[col] for col in series.index if col.startswith(prefix_with_dot)
    }

    # Remove prefix from keys
    result = {
        col[len(prefix_with_dot) :]: value for col, value in matched_columns.items()
    }

    return result
