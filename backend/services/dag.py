"""Small dependency-driven asynchronous DAG executor.

The executor owns scheduling and validation only. Node functions own business
logic and may be synchronous or asynchronous; synchronous work should be
wrapped with ``asyncio.to_thread`` by the node factory.
"""

import asyncio
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Iterable

from pydantic import BaseModel, ValidationError

from observability.events import emit_event, stage_span


class DAGError(RuntimeError):
    pass


class NodeValidationError(DAGError):
    def __init__(self, node_id: str, output_model: type[BaseModel], error: Exception):
        self.node_id = node_id
        self.output_model = output_model
        self.error = error
        super().__init__(f"Node {node_id} produced invalid {output_model.__name__}: {error}")


class PipelineState:
    """Typed-by-convention state shared by nodes after dependency completion."""

    def __init__(self, initial: dict[str, Any] | None = None):
        self._values = dict(initial or {})

    def get(self, name: str, default: Any = None) -> Any:
        return self._values.get(name, default)

    def require(self, name: str) -> Any:
        if name not in self._values:
            raise DAGError(f"Pipeline state has no value for {name!r}")
        return self._values[name]

    def put(self, name: str, value: Any) -> None:
        self._values[name] = value

    def snapshot(self) -> dict[str, Any]:
        return dict(self._values)


NodeRunner = Callable[[PipelineState], Awaitable[Any]]


@dataclass(frozen=True)
class Node:
    id: str
    run: NodeRunner
    depends_on: tuple[str, ...] = ()
    output_model: type[BaseModel] | None = None
    stage: str | None = None
    kind: str = "service"
    agent: str | None = None
    worker: str | None = None


def _validate_graph(nodes: list[Node]) -> None:
    ids = [node.id for node in nodes]
    if len(ids) != len(set(ids)):
        raise DAGError("DAG contains duplicate node ids")
    known = set(ids)
    for node in nodes:
        missing = set(node.depends_on) - known
        if missing:
            raise DAGError(f"Node {node.id} depends on unknown nodes: {sorted(missing)}")

    remaining = {node.id: set(node.depends_on) for node in nodes}
    while remaining:
        ready = {name for name, deps in remaining.items() if not deps}
        if not ready:
            raise DAGError("DAG contains a dependency cycle")
        for name in ready:
            remaining.pop(name)
        for deps in remaining.values():
            deps.difference_update(ready)


async def execute_dag(
    nodes: Iterable[Node], initial: dict[str, Any] | None = None
) -> PipelineState:
    """Execute nodes as soon as their own dependencies complete.

    All node coroutines live in one ``TaskGroup``. A node waits only for the
    futures of its declared dependencies, so independent branches run at the
    same time without artificial stage barriers.
    """

    node_list = list(nodes)
    _validate_graph(node_list)
    state = PipelineState(initial)
    futures = {node.id: asyncio.get_running_loop().create_future() for node in node_list}

    async def run_node(node: Node) -> None:
        try:
            if node.depends_on:
                await asyncio.gather(*(futures[name] for name in node.depends_on))

            parent = node.depends_on[0] if node.depends_on else None
            with stage_span(
                node.stage or node.id,
                node_id=node.id,
                parent_node=parent,
                component=node.kind,
                agent=node.agent,
                worker=node.worker,
            ):
                result = await node.run(state)
                if node.output_model is not None:
                    try:
                        if isinstance(result, BaseModel):
                            result = node.output_model.model_validate(result.model_dump())
                        else:
                            result = node.output_model.model_validate(result)
                    except (ValidationError, TypeError, ValueError) as exc:
                        emit_event(
                            node.stage or node.id,
                            "validation_failed",
                            node_id=node.id,
                            validation_status="failed",
                            error=str(exc),
                        )
                        raise NodeValidationError(node.id, node.output_model, exc) from exc
                    emit_event(
                        node.stage or node.id,
                        "validated",
                        node_id=node.id,
                        validation_status="passed",
                    )
                state.put(node.id, result)
            if not futures[node.id].done():
                futures[node.id].set_result(result)
        except asyncio.CancelledError:
            if not futures[node.id].done():
                futures[node.id].cancel()
            raise
        except Exception as exc:
            if not futures[node.id].done():
                futures[node.id].set_exception(exc)
            raise

    try:
        async with asyncio.TaskGroup() as group:
            for node in node_list:
                group.create_task(run_node(node), name=f"pipeline:{node.id}")
    except* Exception as errors:
        first = errors.exceptions[0]
        if isinstance(first, DAGError):
            raise first from first.__cause__
        raise DAGError(f"DAG execution failed: {first}") from first
    return state
