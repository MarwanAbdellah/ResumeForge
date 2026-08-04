import asyncio

import pytest

from models.pipeline import ATSKeywordModel
from services.dag import DAGError, Node, execute_dag


def test_independent_nodes_run_concurrently():
    async def scenario():
        started = asyncio.Event()
        active = 0
        maximum = 0

        async def worker(state):
            nonlocal active, maximum
            active += 1
            maximum = max(maximum, active)
            started.set()
            await asyncio.sleep(0.02)
            active -= 1
            return ATSKeywordModel(required_keywords=["Python"])

        nodes = [
            Node("a", worker, output_model=ATSKeywordModel),
            Node("b", worker, output_model=ATSKeywordModel),
        ]
        await execute_dag(nodes)
        assert started.is_set()
        assert maximum == 2

    asyncio.run(scenario())


def test_graph_rejects_cycles():
    async def scenario():
        async def noop(state):
            return None

        with pytest.raises(DAGError, match="cycle"):
            await execute_dag([
                Node("a", noop, ("b",)),
                Node("b", noop, ("a",)),
            ])

    asyncio.run(scenario())
