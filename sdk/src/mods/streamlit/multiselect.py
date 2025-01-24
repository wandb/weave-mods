from typing import Any, Callable, List, Optional, Sequence, Union

import streamlit as st

from mods.api import query
from mods.streamlit import api
from mods.streamlit.selectbox import BoxSelector

SelectOptions = Union[query.Op, query.Calls, List[query.Obj], BoxSelector]


def multiselect(
    label: str,
    options: SelectOptions,
    *args,
    default: Optional[Callable[[Sequence[str]], Any]] = None,
    sort_key: Optional[Callable[[Any], Any]] = None,
    op_types: Optional[Sequence[str]] = None,
    client: Optional[query.WeaveClient] = None,
    **kwargs,
) -> Union[List[query.Op], List[query.Column], List[query.Obj]]:
    """Create a multi-select widget that handles different types of selectable inputs.

    This function provides a unified interface for creating multi-select widgets for
    different types of inputs (Operations, Calls, Objects, or regular lists).

    Args:
        label: Display label for the multi-select widget.
        options: The options to select from. Can be:
            - query.Op: Shows versions of the operation
            - query.Calls: Shows columns from the calls
            - List[query.Obj]: Shows a list of objects (Datasets, Models, etc.)
            - List: Shows a regular list of items
            - None: Queries objects based on the selector
        selector:
            - Selector.DATASET: Select from available datasets
            - Selector.MODEL: Select from available models
            - Selector.EVALUATION: Select from available evaluations
            - Selector.PROMPT: Select from available prompts
        default: Optional callback that takes a sequence of strings and returns
            default selected values.
        sort_key: Optional function to sort the input items (used for Calls and Objects).
        op_types: Optional sequence of operation types to filter columns
            (only used with query.Calls input).
        client: Optional WeaveClient instance. If None, uses the current client.

    Returns:
        A list of selected items. The type depends on the input:
        - List[query.Op] for Operation inputs
        - List[query.Column] for Calls inputs
        - List[query.Obj] for Object list inputs
        - List for regular list inputs

    Raises:
        ValueError: If the input type is not supported.
    """
    if client is None:
        client = api.current_client()

    # TODO: rethink this...
    if options == BoxSelector.DATASET:
        options = api.get_objects("Dataset", cached=False, client=client)
        kwargs["placeholder"] = "Select Datasets..."
    elif options == BoxSelector.MODEL:
        options = api.get_objects("Model", cached=False, client=client)
        kwargs["placeholder"] = "Select Models..."
    elif options == BoxSelector.EVALUATION:
        options = api.get_objects("Evaluation", cached=False, client=client)
        kwargs["placeholder"] = "Select Evaluations..."
    elif options == BoxSelector.PROMPT:
        options = api.get_objects("Prompt", cached=False, client=client)
        kwargs["placeholder"] = "Select Prompts..."

    if type(options).__name__ == "Op":
        return version_multiselect(client, label, options, default)
    elif type(options).__name__ == "Calls":
        return calls_column_multiselect(label, options, op_types, sort_key, default)
    elif isinstance(options, list):
        if options and all(type(x) is query.Obj for x in options):
            return objs_multiselect(label, options, *args, sort_key, default, **kwargs)
        return st.multiselect(label, options, *args, default=default, **kwargs)

    raise ValueError(f"Invalid input type: {type(options)}")


def version_multiselect(
    client: query.WeaveClient,
    label: str,
    op: query.Op,
    default: Optional[Callable[[Sequence[str]], Any]] = None,
) -> List[query.Op]:
    versions = api.get_op_versions(op, client=client)
    if default is None:
        default_val = [versions[0]]
    else:
        default_val = default([repr(v) for v in versions])

    return st.multiselect(
        label, versions, default=default_val, format_func=lambda x: repr(x)
    )


def calls_column_multiselect(
    label: str,
    calls: query.Calls,
    op_types: Optional[Sequence[str]] = None,
    sort_key: Optional[Callable[[query.Column], Any]] = None,
    default: Optional[Callable[[Sequence[str]], Any]] = None,
) -> List[query.Column]:
    ordered_compare_cols = calls.columns(op_types=op_types, sort_key=sort_key)
    default_val = None
    if default is not None:
        default_val = default([col.name for col in ordered_compare_cols])
    return st.multiselect(
        label,
        ordered_compare_cols,
        default=default_val,
        format_func=lambda col: col.name,
    )


def objs_multiselect(
    label: str,
    objs: List[query.Obj],
    sort_key: Optional[Callable[[query.Obj], Any]] = None,
    default: Optional[Callable[[Sequence[str]], Any]] = None,
    **kwargs,
) -> List[query.Obj]:
    if sort_key:
        objs = sorted(objs, key=sort_key)
    default_val = None
    if default is not None:
        default_val = default([repr(o) for o in objs])

    return st.multiselect(
        label,
        objs,
        default=default_val,
        format_func=lambda o: repr(o),
        **kwargs,
    )
