from enum import Enum, auto
from typing import Any, Callable, List, Literal, Optional, TypeVar, Union, overload

import streamlit as st
from weave.trace.weave_client import WeaveClient

from mods.api import query
from mods.streamlit.api import current_client


class BoxSelector(Enum):
    OP = auto()
    DATASET = auto()
    MODEL = auto()
    OBJECT = auto()


T = TypeVar("T")


@overload
def selectbox(
    label: str,
    selector: Literal[BoxSelector.OP],
    sort_key: Optional[Callable[[query.Op], Any]] = None,
    object_types: None = None,
    client: Optional[WeaveClient] = None,
) -> Optional[query.Op]: ...


@overload
def selectbox(
    label: str,
    selector: Literal[BoxSelector.DATASET],
    sort_key: Optional[Callable[[query.Obj], Any]] = None,
    object_types: None = None,
    client: Optional[WeaveClient] = None,
) -> Optional[query.Obj]: ...


@overload
def selectbox(
    label: str,
    selector: Literal[BoxSelector.MODEL],
    sort_key: Optional[Callable[[query.Obj], Any]] = None,
    object_types: None = None,
    client: Optional[WeaveClient] = None,
) -> Optional[query.Obj]: ...


@overload
def selectbox(
    label: str,
    selector: Literal[BoxSelector.OBJECT],
    sort_key: Optional[Callable[[query.Obj], Any]] = None,
    object_types: Union[List[str], str, None] = None,
    client: Optional[WeaveClient] = None,
) -> Optional[query.Obj]: ...


def selectbox(
    label: str,
    selector: BoxSelector,
    sort_key: Optional[Callable[[Any], Any]] = None,
    object_types: Union[List[str], str, None] = None,
    client: Optional[WeaveClient] = None,
) -> Optional[Union[query.Op, query.Obj]]:
    """Create a Streamlit selectbox for various Weave object types.

    Args:
        label (str): The label to display above the selectbox.
        selector (Selector): The type of selector to use. Options are:
            - Selector.OP: Select from available ops
            - Selector.DATASET: Select from available datasets
            - Selector.MODEL: Select from available models
            - Selector.OBJECT: Select from available objects of specified types
        sort_key (Optional[Callable[[Any], Any]], optional): Function to determine the sort order
            of the options. Defaults to None.
        object_types (Union[List[str], str, None], optional): When using Selector.OBJECT,
            specify the type(s) of objects to include. Defaults to None.
        client (Optional[WeaveClient], optional): WeaveClient instance to use.
            If None, uses the current client. Defaults to None.

    Returns:
        Any: The selected object, or None if nothing is selected.
    """
    if client is None:
        client = current_client()
    kwargs = {}
    if sort_key is not None:
        kwargs["sort_key"] = sort_key
    if object_types is not None:
        kwargs["object_types"] = object_types
    return selectors[selector](client, label, **kwargs)


def op_selectbox(
    client: WeaveClient,
    label: str,
    sort_key: Optional[Callable[[query.Op], Any]] = None,
) -> Optional[query.Op]:
    ops = query.get_ops(client)
    if sort_key is None:

        def sort_key(x: query.Op):
            return x.name

    ops = sorted(ops, key=sort_key)
    selection = st.selectbox(
        label,
        options=ops,
        index=None,
        placeholder="Select an Op...",
        format_func=lambda x: f"{x.name} ({x.version_index + 1} versions)",
    )
    return selection


def obj_selectbox(
    client: WeaveClient,
    label: str,
    object_types: List[str] | str = [],
    sort_key: Optional[Callable[[query.Obj], Any]] = None,
) -> Optional[query.Obj]:
    objs = query.get_objs(client, types=object_types)
    if sort_key:
        objs = sorted(objs, key=sort_key)
    thing = "Object"
    if len(object_types) > 0:
        thing = object_types[0]
    return st.selectbox(
        label,
        options=objs,
        index=None,
        placeholder=f"Select an {thing}...",
        format_func=lambda o: f"{o.ref().name}:{o.ref().digest[:3]}",
    )


def dataset_selectbox(
    client: WeaveClient,
    label: str,
    sort_key: Optional[Callable[[query.Obj], Any]] = None,
) -> Optional[query.Obj]:
    return obj_selectbox(client, label, object_types=["Dataset"], sort_key=sort_key)


def model_selectbox(
    client: WeaveClient,
    label: str,
    sort_key: Optional[Callable[[query.Obj], Any]] = None,
) -> Optional[query.Obj]:
    return obj_selectbox(client, label, object_types=["Model"], sort_key=sort_key)


selectors = {
    BoxSelector.OP: op_selectbox,
    BoxSelector.DATASET: dataset_selectbox,
    BoxSelector.MODEL: model_selectbox,
    BoxSelector.OBJECT: obj_selectbox,
}
