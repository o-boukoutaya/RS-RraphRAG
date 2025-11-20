# app/observability/state.py
from __future__ import annotations
from dataclasses import dataclass, asdict
from enum import Enum
from time import monotonic
from datetime import datetime, timezone
import asyncio, uuid

try:
    from neo4j import GraphDatabase
except Exception:
    GraphDatabase = None

class Phase(str, Enum):
    STARTING="STARTING"; RUNNING="RUNNING"; STOPPING="STOPPING"
    STOPPED="STOPPED"; ERROR="ERROR"; DEGRADED="DEGRADED"

@dataclass
class Neo4jStatus:
    connected: bool = False
    latency_ms: float | None = None
    error: str | None = None

@dataclass
class BackendStatus:
    boot_id: str
    phase: Phase
    started_at: str
    uptime_s: float
    neo4j: Neo4jStatus
    sse_clients: int = 0
    note: str | None = None

BOOT_ID = str(uuid.uuid4())
T0 = monotonic()
STATUS = BackendStatus(
    boot_id=BOOT_ID,
    phase=Phase.STARTING,
    started_at=datetime.now(timezone.utc).isoformat(),
    uptime_s=0.0,
    neo4j=Neo4jStatus(),
)

_sse_clients = 0
def inc_clients():  # appelé par la route SSE à la connexion
    global _sse_clients; _sse_clients += 1; STATUS.sse_clients = _sse_clients
def dec_clients():
    global _sse_clients; _sse_clients = max(0, _sse_clients-1); STATUS.sse_clients = _sse_clients

async def probe_neo4j(uri: str|None, user: str|None, pwd: str|None) -> Neo4jStatus:
    if not GraphDatabase or not uri: return Neo4jStatus(False, None, "driver/uri manquant")
    t0 = monotonic()
    try:
        driver = GraphDatabase.driver(uri, auth=(user, pwd)) if user else GraphDatabase.driver(uri)
        with driver.session() as s:
            s.run("RETURN 1")
        return Neo4jStatus(True, (monotonic()-t0)*1000.0, None)
    except Exception as e:
        return Neo4jStatus(False, None, str(e))

async def health_loop():
    """Boucle de santé périodique : met à jour STATUS et diffuse (via SSE) à chaque tick."""
    from .sse import push_status  # import local pour éviter cycle
    while True:
        try:
            from app.core.config import get_settings
            neo4j_cfg = get_settings().neo4j
            STATUS.uptime_s = monotonic() - T0
            # neo4j conf
            neo = await probe_neo4j(getattr(neo4j_cfg, "uri", None), 
                                    getattr(neo4j_cfg, "username", None),
                                    getattr(neo4j_cfg, "password", None))
            STATUS.neo4j = neo
            # Dégradation simple: RUNNING mais Neo4j down -> DEGRADED
            if STATUS.phase == Phase.RUNNING and not neo.connected:
                STATUS.phase = Phase.DEGRADED
            elif STATUS.phase == Phase.DEGRADED and neo.connected:
                STATUS.phase = Phase.RUNNING
            await push_status(asdict(STATUS)) # ✅ envoi dans la file SSE
        except Exception as e:
            STATUS.phase = Phase.ERROR
            STATUS.note = str(e)
        await asyncio.sleep(5)  # période de 5s

# app/observability/state.py
async def health_loop_2():
    """Boucle de santé : met à jour STATUS et diffuse (via SSE)."""
    from .sse import push_status  # import local pour éviter cycle
    from app.core.config import get_settings
    import asyncio, time

    while True:
        prev = STATUS.phase
        try:
            cfg = get_settings().neo4j
            STATUS.neo4j = await probe_neo4j(cfg.uri, cfg.username, cfg.password)
            STATUS.uptime_s = time.monotonic() - T0

            # FSM : transitions de phase
            if STATUS.neo4j.connected:
                if prev in (Phase.STARTING, Phase.DEGRADED):
                    STATUS.phase = Phase.RUNNING
            else:
                if prev == Phase.RUNNING:
                    STATUS.phase = Phase.DEGRADED

            # Push seulement si changement
            if prev != STATUS.phase:
                await push_status(asdict(STATUS))

        except Exception as e:
            STATUS.phase = Phase.ERROR
            STATUS.note = str(e)
            await push_status(asdict(STATUS))

        await asyncio.sleep(5)