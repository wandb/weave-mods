from enum import Enum, auto
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    ParamSpec,
    TypeVar,
    Union,
)

import streamlit as st
from weave.trace.weave_client import WeaveClient

from mods.api import query
from mods.streamlit import api


class BoxSelector(Enum):
    OP = auto()
    DATASET = auto()
    MODEL = auto()
    EVALUATION = auto()
    PROMPT = auto()
    OBJECT = auto()


T = TypeVar("T")

SelectOptions = Union[BoxSelector, List[T]]


def selectbox(
    label: str,
    options: SelectOptions,
    *args,
    sort_key: Optional[Callable[[Any], Any]] = None,
    object_types: Union[List[str], str, None] = None,
    client: Optional[WeaveClient] = None,
    **kwargs,
) -> Optional[Union[query.Op, query.Obj]]:
    """Create a Streamlit selectbox for various Weave object types.

    Args:
        label (str): The label to display above the selectbox.
        selector (Selector): The type of selector to use. Options are:
            - Selector.OP: Select from available ops
            - Selector.DATASET: Select from available datasets
            - Selector.MODEL: Select from available models
            - Selector.EVALUATION: Select from available evaluations
            - Selector.PROMPT: Select from available prompts
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
        client = api.current_client()

    if isinstance(options, BoxSelector):
        kwargs: dict[str, Any] = {}
        if sort_key is not None:
            kwargs["sort_key"] = sort_key
        if object_types is not None:
            kwargs["object_types"] = object_types
        selector_func = selectors.get(options)
        return selector_func(client, label, **kwargs)
    elif isinstance(options, list):
        return st.selectbox(label, options=options, *args, **kwargs)
    else:
        raise ValueError(f"Invalid options type: {type(options)}")


def op_selectbox(
    client: WeaveClient,
    label: str,
    sort_key: Optional[Callable[[query.Op], Any]] = None,
) -> Optional[query.Op]:
    ops = api.get_ops(client=client)
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
    objs = api.get_objects(object_types, client=client)
    if sort_key:
        objs = sorted(objs, key=sort_key)
    # TODO: this article nonsense is a bit of a mess
    thing = "Object"
    article = "an"
    if len(object_types) > 0:
        thing = object_types[0]
        article = "a"
    return st.selectbox(
        label,
        options=objs,
        index=None,
        placeholder=f"Select {article} {thing}...",
        format_func=lambda o: repr(o),
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


def evaluation_selectbox(
    client: WeaveClient,
    label: str,
    sort_key: Optional[Callable[[query.Obj], Any]] = None,
) -> Optional[query.Obj]:
    return obj_selectbox(client, label, object_types=["Evaluation"], sort_key=sort_key)


def prompt_selectbox(
    client: WeaveClient,
    label: str,
    sort_key: Optional[Callable[[query.Obj], Any]] = None,
) -> Optional[query.Obj]:
    return obj_selectbox(client, label, object_types=["Prompt"], sort_key=sort_key)


P = ParamSpec("P")
R = TypeVar("R", bound=Optional[Union[query.Op, query.Obj]])

SelectorFunc = Callable[P, R]

selectors: Dict[BoxSelector, SelectorFunc] = {
    BoxSelector.OP: op_selectbox,
    BoxSelector.DATASET: dataset_selectbox,
    BoxSelector.MODEL: model_selectbox,
    BoxSelector.EVALUATION: evaluation_selectbox,
    BoxSelector.PROMPT: prompt_selectbox,
    BoxSelector.OBJECT: obj_selectbox,
}
