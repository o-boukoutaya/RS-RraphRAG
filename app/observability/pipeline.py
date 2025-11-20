import time, asyncio, functools, logging
from app.observability.sse import push_step

def pipeline_step(name: str, series: str|None=None):
    def deco(fn):
        is_async = asyncio.iscoroutinefunction(fn)
        @functools.wraps(fn)
        async def _a(*a, **k):
            t0 = time.perf_counter()
            await push_step({"series": series, "step": name, "phase": "start"})
            try:
                res = await fn(*a, **k)
                dt = (time.perf_counter()-t0)*1000.0
                await push_step({"series": series, "step": name, "phase": "end", "ms": dt})
                return res
            except Exception as e:
                await push_step({"series": series, "step": name, "phase": "error", "msg": str(e)})
                raise
        @functools.wraps(fn)
        def _s(*a, **k):
            t0 = time.perf_counter()
            asyncio.create_task(push_step({"series": series, "step": name, "phase": "start"}))
            try:
                res = fn(*a, **k)
                dt = (time.perf_counter()-t0)*1000.0
                asyncio.create_task(push_step({"series": series, "step": name, "phase": "end", "ms": dt}))
                return res
            except Exception as e:
                asyncio.create_task(push_step({"series": series, "step": name, "phase": "error", "msg": str(e)}))
                raise
        return _a if is_async else _s
    return deco
