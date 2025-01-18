import json
from typing import Any, Dict, List, Union

import weave
from openai import OpenAI
from weave.trace.refs import ObjectRef, OpRef
from weave.trace.vals import WeaveObject


def remove_class_key(d: Union[Dict, List]):
    if isinstance(d, dict):
        d.pop("__class__", None)
        for key, value in d.items():
            remove_class_key(value)
    elif isinstance(d, list):
        for item in d:
            remove_class_key(item)
    return d


def serialize_weave_object(obj: WeaveObject):
    serialized_data = obj._val.__dict__
    serialized_data.pop("name", None)
    serialized_data.pop("description", None)
    serialized_data.pop("_class_name", None)
    serialized_data.pop("_bases", None)
    return serialized_data


def serialize_weave_references(data: Any):
    if isinstance(data, ObjectRef):
        return {"type": "ObjectRef", "name": data.name}
    elif isinstance(data, OpRef):
        return {"type": "OpRef", "name": data.name}
    elif isinstance(data, list):
        return [serialize_weave_references(item) for item in data]
    elif isinstance(data, dict):
        return {key: serialize_weave_references(value) for key, value in data.items()}
    else:
        return data


def serialize_input_output_objects(inputs: Any) -> dict[str, Any]:
    inputs = dict(inputs)
    for key, val in inputs.items():
        if isinstance(val, WeaveObject):
            inputs[key] = serialize_weave_object(inputs[key])
        inputs[key] = serialize_weave_references(inputs[key])
    return inputs


@weave.op()
def summarize_single_node(node: dict) -> str:
    response = OpenAI().chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": """
You are a helpful assistant meant to summarize the call trace (given in JSON format)
of a function in a simple and insightful manner.

The call trace would be a dictionary with the following keys:
- id: The ID of the call
- call_name: The name of the call
- inputs: The inputs to the call
- outputs: The outputs of the call
- child_calls: The child calls of the call

Here are some instructions that you must follow:
1. The summary should be simple and insightful.
2. You must start the summary with the following sentence:
`Here's a summary of the call trace {call_name} with ID {id}:`
3. You should take into account the summaries of the child calls when summarizing the parent call.
4. You must summarize each call in the call trace, including all the child calls.
""",
            },
            {
                "role": "user",
                "content": json.dumps(node, sort_keys=True, indent=4),
            },
        ],
    )
    return response.choices[0].message.content


@weave.op()
def summarize_single_predict_and_score_call(node: dict) -> str:
    if not node.get("child_calls"):
        return summarize_single_node(node)

    summarized_children = []
    for child in node["child_calls"]:
        summarized_child = summarize_single_predict_and_score_call(child)
        summarized_children.append(summarized_child)

    node["child_calls"] = summarized_children
    return summarize_single_node(node)
