import time, asyncio
from typing import Callable, Awaitable, Any
from .sse import push_step

async def with_step(run_id: str, step_name: str, fn: Callable[..., Awaitable[Any]], *args, **kwargs):
    await push_step({"run_id": run_id, "step": step_name, "status": "start"})
    t0 = time.perf_counter()
    try:
        res = await fn(*args, **kwargs)
        dt = (time.perf_counter()-t0)*1000.0
        await push_step({"run_id": run_id, "step": step_name, "status": "end", "ms": dt})
        return res
    except Exception as e:
        await push_step({"run_id": run_id, "step": step_name, "status": "error", "meta": {"error": str(e)}})
        raise
