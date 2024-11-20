import datetime
import math
from dataclasses import dataclass
from typing import Any, Callable, List, Optional

import pandas as pd
import streamlit as st
from weave.trace.refs import ObjectRef, OpRef, parse_uri
from weave.trace.weave_client import WeaveClient

from mods.api.pandas_util import pd_apply_and_insert
from mods.api.weave_api_next import (
    weave_client_calls,
    weave_client_get_batch,
    weave_client_objs,
    weave_client_ops,
)

ST_HASH_FUNCS = {WeaveClient: lambda x: x._project_id()}


def simple_val(v):
    if isinstance(v, dict):
        return {k: simple_val(v) for k, v in v.items()}
    elif isinstance(v, list):
        return [simple_val(v) for v in v]
    elif hasattr(v, "uri"):
        return v.uri()
    # elif hasattr(v, "__dict__"):
    #     return {k: simple_val(v) for k, v in v.__dict__.items()}
    else:
        return v


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


@st.cache_data(hash_funcs=ST_HASH_FUNCS)
def resolve_refs(client, refs):
    # Resolve the refs and fetch the message.text field
    # Note we do do this after grouping, so we don't over-fetch refs
    ref_vals = weave_client_get_batch(client, refs)
    ref_vals = simple_val(ref_vals)
    ref_val_df = pd.json_normalize(ref_vals)
    ref_val_df.index = refs
    return ref_val_df


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


def get_ops(_client: WeaveClient):
    # client = weave.init(project_name)
    client_ops = weave_client_ops(_client, latest_only=True)
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


# @st.cache_data(hash_funcs=ST_HASH_FUNCS)
def get_objs(client, types=None, latest_only=True):
    # client = weave.init(project_name)
    client_objs = weave_client_objs(client, types=types, latest_only=latest_only)
    refs = []
    objs = []
    for v in client_objs:
        entity, project = v.project_id.split("/", 1)
        refs.append(ObjectRef(entity, project, v.object_id, v.digest).uri())
        objs.append(v.val)
        # TODO there is other metadata like created at
    df = pd.json_normalize([simple_val(v) for v in objs])
    df.index = refs
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
    # return [Op(op.object_id, op.version_index) for op in client_ops]


def friendly_dtypes(df):
    # Pandas doesn't allow NaN in bool columns for example. But we want to suggest
    # bool-like columns as target columns for example.
    def detect_dtype(series):
        non_null_series = series.dropna()

        if non_null_series.empty:
            return "unknown"

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


def get_calls(
    _client: WeaveClient,
    op_name: str | List[str] | List[Op] | None,
    input_refs=None,
    limit: int | None = None,
    cache_key=None,
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
        for c in weave_client_calls(_client, op_names, input_refs, limit)
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


@st.cache_data(hash_funcs=ST_HASH_FUNCS)
def cached_get_calls(
    client: WeaveClient,
    op_name: str | List[str] | List[Op] | None,
    input_refs=None,
    cache_key=None,
):
    return get_calls(client, op_name, input_refs, cache_key)
