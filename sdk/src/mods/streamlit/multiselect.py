from typing import Any, Callable, List, Optional, Sequence, Union, overload

import streamlit as st

from mods.api import query
from mods.streamlit.api import current_client


@overload
def multiselect(
    label: str,
    op: query.Op,
    default: Optional[Callable[[Sequence[str]], Any]] = None,
    client: Optional[query.WeaveClient] = None,
) -> List[query.Op]: ...


@overload
def multiselect(
    label: str,
    calls: query.Calls,
    default: Optional[Callable[[Sequence[str]], Any]] = None,
    sort_key: Optional[Callable[[query.Column], Any]] = None,
    op_types: Optional[Sequence[str]] = None,
) -> List[query.Column]: ...


def multiselect(
    label: str,
    op: Optional[query.Op] = None,
    calls: Optional[query.Calls] = None,
    default: Optional[Callable[[Sequence[str]], Any]] = None,
    sort_key: Optional[Callable[[query.Column], Any]] = None,
    op_types: Optional[Sequence[str]] = None,
    client: Optional[query.WeaveClient] = None,
) -> List[Union[query.Op, query.Column]]:
    if client is None:
        client = current_client()
    if op is not None:
        return version_multiselect(client, label, op, default)
    elif calls is not None:
        return calls_column_multiselect(label, calls, op_types, sort_key, default)


def version_multiselect(
    client: query.WeaveClient,
    label: str,
    op: query.Op,
    default: Optional[Callable[[Sequence[str]], Any]] = None,
) -> List[query.Op]:
    versions = query.get_op_versions(client, op)
    if default is None:
        default_op = [versions[0]]
    else:
        default_op = default([str(v) for v in versions])
    return st.multiselect(
        label, versions, default=default_op, format_func=lambda x: repr(x)
    )


def calls_column_multiselect(
    label: str,
    calls: query.Calls,
    op_types: Optional[Sequence[str]] = None,
    sort_key: Optional[Callable[[query.Column], Any]] = None,
    default: Optional[Callable[[Sequence[str]], Any]] = None,
) -> List[str]:
    ordered_compare_cols = calls.columns(op_types=op_types, sort_key=sort_key)
    ordered_compare_column_names = [col.name for col in ordered_compare_cols]
    default_val = None
    if default is not None:
        default_val = default(ordered_compare_column_names)
    return st.multiselect(label, ordered_compare_column_names, default=default_val)
