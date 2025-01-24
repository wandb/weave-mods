import datetime
import math
from dataclasses import dataclass
from typing import Any, Callable, List, Optional

import pandas as pd
from weave.trace.refs import ObjectRef, OpRef, parse_uri
from weave.trace.weave_client import WeaveClient
from weave.trace_server.trace_server_interface import CallsFilter

from mods.api.pandas_util import pd_apply_and_insert
from mods.api.weave_api_next import (
    weave_client_calls,
    weave_client_objs,
    weave_client_ops,
)

ST_HASH_FUNCS = {
    WeaveClient: lambda x: x._project_id(),
    CallsFilter: lambda x: x.model_dump_json(),
}


def nice_ref(x):
    try:
        parsed = parse_uri(x)
        nice_name = f"{parsed.name}:{parsed.digest[:3]}"
        if parsed.extra:
            for i in range(0, len(parsed.extra), 2):
                k = parsed.extra[i]
                v = parsed.extra[i + 1]
                if k == "id":
                    nice_name += f"/{v[:4]}"
        return nice_name
    except ValueError:
        return x


def pd_col_join(df, sep):
    columns = df.columns
    res = df[columns[0]]
    for i in range(1, len(columns)):
        res = res + sep + df[columns[i]]
    return res


def is_ref_series(series: pd.Series):
    return series.str.startswith("weave://").any()


def split_obj_ref(series: pd.Series):
    expanded = series.str.split("/", expand=True)
    name_version = expanded[6].str.split(":", expand=True)
    result = pd.DataFrame(
        {
            "entity": expanded[3],
            "project": expanded[4],
            "kind": expanded[5],
            "name": name_version[0],
            "version": name_version[1],
        }
    )
    if len(expanded.columns) > 7:
        result["path"] = pd_col_join(expanded.loc[:, expanded.columns > 6], "/")
    return result


@dataclass
class Op:
    project_id: str
    name: str
    digest: str
    version_index: int
    call_count: Optional[int] = None

    def ref(self):
        entity_id, project_id = self.project_id.split("/", 1)
        return OpRef(entity_id, project_id, self.name, self.digest)

    def __str__(self):
        return self.ref().uri()

    def __repr__(self):
        name = self.name
        name = name.split(".")[-1][-10:]
        return f"{name}:v{self.version_index}"


def get_ops(_client: WeaveClient, latest_only=True):
    # client = weave.init(project_name)
    client_ops = weave_client_ops(_client, latest_only=latest_only)
    return [
        Op(op.project_id, op.object_id, op.digest, op.version_index)
        for op in client_ops
    ]


def get_op_versions(_client: WeaveClient, op: Op, include_call_counts=False):
    client_ops = weave_client_ops(_client, id=op.name)
    ops = [
        Op(op.project_id, op.object_id, op.digest, op.version_index)
        for op in client_ops
    ]
    if include_call_counts:
        calls = get_calls(_client, [o.ref().uri() for o in ops])
        if len(calls.df):
            counts = calls.df.groupby("op_name").size()
            for op in ops:
                op.call_count = counts.get(op.ref().uri())
        else:
            for op in ops:
                op.call_count = 0

    return list(reversed(ops))


@dataclass
class Objs:
    df: pd.DataFrame


@dataclass
class Obj:
    project_id: str
    name: str
    digest: str
    version_index: int
    created_at: datetime.datetime

    def ref(self):
        entity_id, project_id = self.project_id.split("/", 1)
        return ObjectRef(entity_id, project_id, self.name, self.digest)

    def get(self):
        return self.ref().get()

    def __repr__(self):
        return f"{self.name}:v{self.version_index}"


def get_objs(client, types=None, latest_only=True):
    client_objs = weave_client_objs(client, types=types, latest_only=latest_only)
    return list(
        reversed(
            sorted(
                [
                    Obj(
                        v.project_id,
                        v.object_id,
                        v.digest,
                        v.version_index,
                        v.created_at,
                    )
                    for v in client_objs
                ],
                key=lambda v: v.created_at,
            )
        )
    )


def friendly_dtypes(df):
    # Pandas doesn't allow NaN in bool columns for example. But we want to suggest
    # bool-like columns as target columns for example.
    def detect_dtype(series):
        non_null_series = series.dropna()

        if non_null_series.empty:
            return "empty"

        # Check for boolean-like columns
        if all(
            isinstance(x, bool) or x is None or (isinstance(x, float) and math.isnan(x))
            for x in series
        ):
            return "bool"

        # Check for string-like columns
        if all(
            isinstance(x, str) or x is None or (isinstance(x, float) and math.isnan(x))
            for x in series
        ):
            return "str"

        # Fallback to the series' original dtype
        return series.dtype.name

    dtypes_dict = {col: detect_dtype(df[col]) for col in df.columns}
    friendly_dtypes_series = pd.Series(dtypes_dict, name="Friendly Dtype")
    return friendly_dtypes_series


@dataclass
class Column:
    name: str
    type: str


@dataclass
class Calls:
    df: pd.DataFrame

    def columns(
        # TODO what is the python type for sorted key return value?
        self,
        op_types=None,
        sort_key: Optional[Callable[[Column], Any]] = None,
    ):
        dtypes = friendly_dtypes(self.df)
        cols = (Column(c, dtypes[c]) for c in dtypes.index)
        if op_types:
            cols = (c for c in cols if dtypes[c.name] in op_types)
        if sort_key:
            cols = sorted(cols, key=sort_key)
        return cols

    def __repr__(self):
        def format_column_type(col: str, dtype: str) -> str:
            if dtype == "object":
                # Get first non-null value without scanning entire column
                mask = self.df[col].notna()
                sample = self.df[col].iloc[mask.idxmax()] if mask.any() else None
                if sample is not None:
                    if isinstance(sample, dict):
                        keys = list(sample.keys())
                        key_preview = ", ".join(sorted(keys)[:3])
                        if len(keys) > 3:
                            key_preview += ", ..."
                        return f"{col}: dict[{len(keys)} keys: {key_preview}]"
                    elif isinstance(sample, (list, tuple)):
                        # Peek into first item if it's a dict
                        if len(sample) > 0 and isinstance(sample[0], dict):
                            keys = sample[0].keys()
                            key_preview = ", ".join(sorted(keys)[:3])
                            if len(keys) > 3:
                                key_preview += ", ..."
                            return f"{col}: {type(sample).__name__}[{len(sample)} items, first item: dict({key_preview})]"
                        return f"{col}: {type(sample).__name__}[{len(sample)} items]"
                    return f"{col}: {type(sample).__name__}"
            return f"{col}: {dtype}"

        dtypes = {
            col: dtype
            for col, dtype in friendly_dtypes(self.df).items()
            if dtype != "empty"
        }
        col_info = [format_column_type(col, dtype) for col, dtype in dtypes.items()]
        return f"Calls(rows={len(self.df)}, columns=[\n  {',\n  '.join(col_info)}\n])"


def get_calls(
    _client: WeaveClient,
    op_name: str | List[str] | List[Op] | None,
    input_refs: list[str] | str | None = None,
    calls_filter: CallsFilter | None = None,
    trace_roots_only: bool | None = None,
    limit: int | None = None,
    callback: Optional[Callable[[int], None]] = None,
):
    if isinstance(op_name, list):
        if all(type(op_name).__name__ == "Op" for o in op_name):
            op_names = [o.ref().uri() for o in op_name]
        else:
            op_names = op_name
    else:
        if type(op_name).__name__ == "Op":
            op_names = [op_name.ref().uri()]
        else:
            op_names = [op_name] if op_name else None
    call_list = [
        {
            "id": c.id,
            "trace_id": c.trace_id,
            "parent_id": c.parent_id,
            "started_at": c.started_at,
            "op_name": c.op_name,
            "inputs": {
                k: v.uri() if hasattr(v, "uri") else v for k, v in c.inputs.items()
            },
            "input_refs": c.input_refs,
            "output": c.output,
            "exception": c.exception,
            "attributes": c.attributes,
            "summary": c.summary,
            "ended_at": c.ended_at,
        }
        for c in weave_client_calls(
            _client,
            op_names,
            input_refs,
            calls_filter,
            trace_roots_only,
            limit,
            callback,
        )
    ]
    df = pd.json_normalize(call_list)

    if df.empty:
        return Calls(df)
    df = pd_apply_and_insert(df, "op_name", split_obj_ref)

    # Merge the usage columns, removing the model component
    usage_columns = [col for col in df.columns if col.startswith("summary.usage")]
    renamed_columns = [
        f"summary.usage.{col.split('.')[-1]}"  # Keep only the metric name (last component)
        for col in usage_columns
    ]
    df_renamed = df[usage_columns].copy()
    df_renamed.columns = renamed_columns
    df_summed = df_renamed.T.groupby(level=0).sum().T
    df_final = df.drop(columns=usage_columns).join(df_summed)
    # Sum up duplicate columns
    """
    duplicate_cols = df_final.columns[df_final.columns.duplicated(keep=False)]
    for col_name in duplicate_cols.unique():
        # Sum all columns with this name and assign back to first occurrence
        df_final[col_name] = df_final.filter(like=col_name).sum(axis=1)
        # Drop all but the first occurrence
        dup_indices = df_final.columns.get_indexer_for([col_name])[1:]
        df_final = df_final.drop(columns=df_final.columns[dup_indices])
    """

    return Calls(df_final)
