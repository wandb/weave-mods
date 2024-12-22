# This contains code that needs to be added to the weave Python package.
# But its here for now so we can iterate on finding the right patterns.

import dataclasses
import datetime
from typing import Any, Callable, Iterator, List, Optional, Sequence, Union, cast

from weave.trace import urls, weave_client
from weave.trace.weave_client import WeaveClient, from_json
from weave.trace_server.trace_server_interface import (
    CallSchema,
    CallsFilter,
    CallsQueryReq,
    ObjectVersionFilter,
    ObjQueryReq,
    ObjQueryRes,
    ObjSchema,
    RefsReadBatchReq,
    TraceServerInterface,
)
from weave.trace_server.trace_server_interface_util import extract_refs_from_values


@dataclasses.dataclass
class Call:
    op_name: str
    started_at: datetime.datetime
    ended_at: Optional[datetime.datetime]
    trace_id: str
    project_id: str
    parent_id: Optional[str]
    inputs: dict
    input_refs: list[str]
    id: Optional[str] = None
    output: Any = None
    exception: Optional[str] = None
    summary: Optional[dict] = None
    attributes: Optional[dict] = None
    # These are the live children during logging
    _children: list["Call"] = dataclasses.field(default_factory=list)

    @property
    def ui_url(self) -> str:
        project_parts = self.project_id.split("/")
        if len(project_parts) != 2:
            raise ValueError(f"Invalid project_id: {self.project_id}")
        entity, project = project_parts
        if not self.id:
            raise ValueError("Can't get URL for call without ID")
        return urls.redirect_call(entity, project, self.id)

    # These are the children if we're using Call at read-time
    def children(self) -> "CallsIter":
        client = weave_client.require_graph_client()
        if not self.id:
            raise ValueError("Can't get children of call without ID")
        return CallsIter(
            client.server,
            self.project_id,
            CallsFilter(parent_ids=[self.id]),
        )

    def delete(self) -> bool:
        client = weave_client.require_graph_client()
        return client.delete_call(call=self)


def make_client_call(
    entity: str, project: str, server_call: CallSchema, server: TraceServerInterface
) -> Call:
    output = server_call.output
    # extract_refs_from_values operates on strings. We could return ref objects
    # here instead, since those are what are in inputs after from_json.
    input_refs = extract_refs_from_values(server_call.inputs)
    inputs = from_json(server_call.inputs, server_call.project_id, server)
    call = Call(
        op_name=server_call.op_name,
        started_at=server_call.started_at,
        ended_at=server_call.ended_at,
        project_id=server_call.project_id,
        trace_id=server_call.trace_id,
        parent_id=server_call.parent_id,
        id=server_call.id,
        inputs=inputs,
        input_refs=input_refs,
        output=output,
        summary=server_call.summary,
        attributes=server_call.attributes,
    )
    if call.id is None:
        raise ValueError("Call ID is None")
    return call


class CallsIter:
    server: TraceServerInterface
    filter: CallsFilter
    _column: str
    _limit: int
    _callback: Optional[Callable[[int], None]] = None

    def __init__(
        self,
        server: TraceServerInterface,
        project_id: str,
        filter: CallsFilter,
        columns: List[str] | None = None,
        limit: int | None = None,
        callback: Optional[Callable[[int], None]] = None,
    ) -> None:
        self.server = server
        self.project_id = project_id
        self.filter = filter
        self._columns = columns
        # TODO: Probably make this bigger
        self._limit = limit or 10_000
        self._callback = callback

    def __getitem__(self, key: Union[slice, int]) -> Call:
        if isinstance(key, slice):
            raise NotImplementedError("Slicing not supported")
        for i, call in enumerate(self):
            if i == key:
                return call
        raise IndexError(f"Index {key} out of range")

    def __iter__(self) -> Iterator[Call]:
        page_index = 0
        page_size = 200
        entity, project = self.project_id.split("/")
        total_calls = 0
        while True:
            response = self.server.calls_query(
                CallsQueryReq(
                    project_id=self.project_id,
                    filter=self.filter,
                    offset=page_index * page_size,
                    columns=self._columns,
                    limit=page_size,
                )
            )
            page_data = response.calls
            total_calls += len(page_data)
            if self._callback:
                self._callback(total_calls)
            for call in page_data:
                # TODO: if we want to be able to refer to call outputs
                # we need to yield a ref-tracking call here.
                yield make_client_call(entity, project, call, self.server)
                # yield make_trace_obj(call, ValRef(call.id), self.server, None)
            if len(page_data) < page_size:
                break
            page_index += 1
            if page_index * page_size + len(page_data) >= self._limit:
                break

    def column(self, col_name: str) -> "CallsIter":
        return CallsIter(self.server, self.project_id, CallsFilter(), [col_name])


def weave_client_calls(
    self: WeaveClient,
    op_names,
    input_refs=None,
    limit: int | None = None,
    callback: Optional[Callable[[int], None]] = None,
) -> CallsIter:
    trace_server_filt = CallsFilter()
    if op_names:
        if isinstance(op_names, str):
            op_names = [op_names]
        op_ref_uris = []
        for op_name in op_names:
            if op_name.startswith("weave:///"):
                op_ref_uris.append(op_name)
            else:
                if ":" not in op_name:
                    op_name = op_name + ":*"
                op_ref_uris.append(f"weave:///{self._project_id()}/op/{op_name}")
        trace_server_filt.op_names = op_ref_uris
    if input_refs:
        trace_server_filt.input_refs = input_refs
    return CallsIter(
        self.server,
        self._project_id(),
        trace_server_filt,
        limit=limit,
        callback=callback,
    )


def weave_client_ops(
    self: WeaveClient,
    filter: Optional[ObjectVersionFilter] = None,
    latest_only=False,
    id=None,
) -> list[ObjSchema]:
    if not filter:
        filter = ObjectVersionFilter()
    else:
        filter = filter.model_copy()
    filter = cast(ObjectVersionFilter, filter)
    filter.latest_only = latest_only
    filter.is_op = True
    if id:
        filter.object_ids = [id]

    response = self.server.objs_query(
        ObjQueryReq(
            project_id=self._project_id(),
            filter=filter,
        )
    )
    # latest_only is broken in sqlite implementation, so do it here.
    if latest_only:
        latest_objs = {}
        for obj in response.objs:
            prev_obj = latest_objs.get(obj.object_id)
            if prev_obj and prev_obj.version_index > obj.version_index:
                continue
            latest_objs[obj.object_id] = obj
        response = ObjQueryRes(objs=list(latest_objs.values()))

    return response.objs


def weave_client_objs(
    self: WeaveClient,
    filter: Optional[ObjectVersionFilter] = None,
    types=None,
    latest_only=True,
) -> list[ObjSchema]:
    if not filter:
        filter = ObjectVersionFilter()
    else:
        filter = filter.model_copy()
    if types is not None:
        if isinstance(types, str):
            types = [types]
        filter.base_object_classes = types
    filter = cast(ObjectVersionFilter, filter)
    filter.latest_only = latest_only
    filter.is_op = False

    response = self.server.objs_query(
        ObjQueryReq(
            project_id=self._project_id(),
            filter=filter,
        )
    )

    # latest_only is broken in sqlite implementation, so do it here.
    if latest_only:
        latest_objs = {}
        for obj in response.objs:
            prev_obj = latest_objs.get(obj.object_id)
            if prev_obj and prev_obj.version_index > obj.version_index:
                continue
            latest_objs[obj.object_id] = obj
        response = ObjQueryRes(objs=list(latest_objs.values()))
    return response.objs


def weave_client_get_batch(self, refs: Sequence[str]) -> Sequence[Any]:
    # Create a dictionary to store unique refs and their results
    unique_refs = list(set(refs))
    read_res = self.server.refs_read_batch(
        RefsReadBatchReq(refs=[uri for uri in unique_refs])
    )

    # Create a mapping from ref to result
    ref_to_result = {
        unique_refs[i]: from_json(val, self._project_id(), self.server)
        for i, val in enumerate(read_res.vals)
    }

    # Return results in the original order of refs
    return [ref_to_result[ref] for ref in refs]
