---
name: weave_mods
type: repo
agent: CodeActAgent
---

You're a master at making mods for the Weave AI platform.  A mod is a streamlit app that runs on demand within the Weave AI platform.  Weave is an observability platform for developers building LLM applications, and mods are a way to extend the platform with custom functionality.  Weave has the following concepts:

- **Op**: A function definition.  Users define ops by decorating functions they want to trace.
- **Trace**: A record of a function call.  Traces are created by ops.
- **Dataset**: A collection of data.  Datasets can be created by querying traces from weave or by uploading data from a file.
- **Model**: A python class that has a `predict` function and contains configuration such as the model name, temperature, top_k, etc.
- **Object**: A python object that is stored in weave.  These aren't often used directly, but they power the abstraction behind Datasets and Models.

To make things easy, I've already created the scaffolding and an `app.py` entrypoint.  Please change the name and description of the mod in the `pyproject.toml` file.

We use `uv` to manage the app and dependencies.  If you need to add pip dependencies, you can run `uv add <dependency>`.  DO NOT run `uv pip install <dependency>` when working with streamlit apps.  When you want to run the app, you should run `uv run streamlit run app.py --server.runOnSave=true > server.log 2>&1 &`.

IMPORTANT: don't worry about CORS or iframe's we're behind a proxy that takes care of all of that.  Also no need to restart this process, any changes will be reflected in the running app.  When you print the host url to the console, do not include the port number. You should check the file you log to and look for any errors after starting the server.  When checking for errors, never use the `-f` flag, just tail the file.

After you've made changes to the app, use your browser tool to open the app and test it out by clicking around.  If you encounter an error, you can tail server.log and try to fix it.

The environment is configured with the `WANDB_API_KEY` environment variable so you can use the Weave SDK.  The sdk contains the following interfaces:

### Streamlit Components

The SDK provides several pre-built Streamlit components:

- `mods.streamlit.selectbox`: Enhanced selection interface with support for querying different types from weave.
    ```python
    BoxSelector = mods.st.OP | mods.st.DATASET | mods.st.MODEL | mods.st.OBJECT
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
        ...
    ```
- `mods.streamlit.multiselect`: Multi-selection component for handling multiple items
    ```python
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
        ...
    ```
- `mods.streamlit.chat_thread`: Chat interface component
    ```python
    def chat_thread(call: pd.Series):
        ...
    # Example usage
    chat_data = pd.Series({
        'id': '123',
        'inputs.messages': [{'role': 'user', 'content': 'Hello'}],
        'output.choices': [{'message': {'role': 'assistant', 'content': 'Hi!'}}]
    })
    chat_thread(chat_data)
    ```
- `mods.streamlit.tracetable`: Data visualization component for traces/tables
    ```python
    def tracetable(
        op_names: List[str] | str | None = None,
        input_refs: List[str] | str | None = None,
        dataframe: pd.DataFrame | None = None,
        cached: bool = True,
        client: WeaveClient | None = None,
    ) -> Tuple[query.Calls, Optional[int]]:
        ...
    ```

### Low level API's

Built-in API utilities for data querying and manipulation `from mods.streamlit import api`:

- `api.get_calls`: Retrieve call data
- ```python
  def get_calls(
    op_name: str | List[str] | List[Op] | None = None,
    input_refs: Dict[str, Any] | None = None,
    calls_filter: CallsFilter | None = None,
    cached: bool = True,
    client: WeaveClient | None = None,
  ) -> Calls:
    ...
  ```
- `api.get_ops`: Get operations information
- ```python
  def get_ops(
    latest_only: bool = True,
    cached: bool = True,
    client: WeaveClient | None = None,
  ) -> Calls:
        ...
    ```
- `api.get_op_versions`: Get operation versions
- ```python
  def get_op_versions(
    op: Op,
    include_call_counts: bool = False,
    cached: bool = True,
    client: WeaveClient | None = None,
  ):
    ...
  ```
- `api.get_objects`: Fetch object data
- ```python
  def get_objects(
    object_type: str,
    latest_only: bool = True,
    cached: bool = True,
    client: WeaveClient | None = None,
  ) -> List[Obj]:
    ...
  ```
- `api.resolve_refs`: Resolve weave reference uri's in batch
- ```python
  def resolve_refs(refs: List[str], client: WeaveClient | None = None) -> pd.DataFrame:
    ...
  ```

### Weave SDK

You can also use the official Weave SDK.  If you want access to the raw weave client simply use `api.current_client()`.  For example to add feedback to a trace you can do the following:

```python
client = api.current_client()
trace = client.get_call(trace_id)
trace.feedback.add("annotation", {"valid": True, "reason": "It's great!"})
```

### Example Mod

```python
import streamlit as st
import mods

st.set_page_config(layout="wide")
st.title("Welcome to Weave Mods!")

with st.sidebar:
    st.title("Example mod helpers")
    op = mods.st.selectbox("Ops", mods.st.OP)
    if op:
        v = mods.st.multiselect("Versions", op)
    ds = mods.st.multiselect("Datasets", mods.st.DATASET)
    if ds:
        st.write(f"Datasets: {[d.name for d in ds]}")

if op:
    st.write("Select a row to see the chat thread")
    calls = mods.st.api.get_calls([v.ref().uri() for v in v])
    _, selected = mods.st.tracetable(dataframe=calls.df)
    if selected:
        call = calls.df.iloc[selected]
        mods.st.chat_thread(call)
else:
    st.write("*Select an op to see traces*")
```
# Pro Tips™

1. Use `now = pd.Timestamp.now(tz='UTC')` instead of `datetime.now()` to avoid timezone issues.
2. The calls dataframe can have any columns, you can print the repr of the calls object to see the schema for the specific op you're querying.

```python
from mods.streamlit import api
calls = api.get_calls("litellm.completion")
print(repr(calls))
```

Calls(rows=349, columns=[
  id: str,
  trace_id: str,
  parent_id: str,
  started_at: datetime64[ns, UTC],
  op_name: str,
  op_name.entity: str,
  op_name.project: str,
  op_name.kind: str,
  op_name.name: str,
  op_name.version: str,
  input_refs: list[0 items],
  ended_at: datetime64[ns, UTC],
  inputs.kwargs.messages: list[3 items, first item: dict(content, role)],
  inputs.kwargs.tools: list[6 items, first item: dict(function, type)],
  ...

If the mod you're creating needs access to additional secrets, you can specify them in the `pyproject.toml` file under [tool.weave.mods].  You can set these new secrets to dummy values in the environment during development.
