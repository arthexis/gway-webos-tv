"""Game-bound voice lifecycle. No live backend configured by default."""
import asyncio
import re
import time
from dataclasses import dataclass

GAME = "lantern-gate"
RELEASE = "9e09b80699cd5d293d7d3c37d718fe09f463fa2fdd3e714fab2cad96d056c4cd"
ID = re.compile(r"[0-9a-f]{32}\Z")
LEASE_SECONDS = 15


class VoiceDenied(ValueError):
    pass


@dataclass(frozen=True)
class Session:
    owner: str
    connection: str
    launch: str
    release: str


def validate(owner, connection, request):
    if not owner or not connection:
        raise VoiceDenied("Unauthorized")
    if not isinstance(request, dict) or set(request) != {
        "type", "game", "release", "launch", "connection", "sequence", "enabled"
    }:
        raise VoiceDenied("Invalid request")
    if (request["type"] != "aeon.voice.set" or request["game"] != GAME
            or request["release"] != RELEASE
            or request["connection"] != connection
            or not isinstance(request["launch"], str)
            or not ID.fullmatch(request["launch"])
            or type(request["sequence"]) is not int
            or not 1 <= request["sequence"] <= 2**31-1
            or type(request["enabled"]) is not bool):
        raise VoiceDenied("Invalid game session")
    return Session(owner, connection, request["launch"], RELEASE)


class VoiceSession:
    def __init__(self, backend=None, clock=time.monotonic):
        self.backend = backend
        self.clock = clock
        self.lock = asyncio.Lock()
        self.active = None
        self.deadline = 0.0
        self.fault = False

    async def _stop(self):
        if self.active is None and not self.fault:
            return
        try:
            await asyncio.wait_for(self.backend.stop(), 10)
        except Exception as exc:
            self.fault = True
            raise VoiceDenied("Stop unconfirmed; voice locked") from exc
        self.active = None
        self.fault = False
        self.deadline = 0.0

    def status(self):
        return {"type": "aeon.voice.status",
                "state": "unknown" if self.fault else "listening" if self.active else "stopped"}

    async def set(self, session, enabled):
        async with self.lock:
            if self.backend is None:
                raise VoiceDenied("Scoped voice backend unavailable")
            if self.active and self.active != session:
                raise VoiceDenied("Another game session owns voice")
            if self.fault and enabled:
                raise VoiceDenied("Voice locked pending stop")
            if enabled and self.active is None:
                self.active = session
                try:
                    await asyncio.wait_for(self.backend.start(session), 45)
                except asyncio.CancelledError:
                    await self._stop()
                    raise
                except Exception as exc:
                    await self._stop()
                    raise VoiceDenied("Scoped voice start failed") from exc
            elif not enabled:
                await self._stop()
            if self.active:
                self.deadline = self.clock() + LEASE_SECONDS
            return self.status()

    async def heartbeat(self, session):
        async with self.lock:
            if self.fault or session != self.active or session is None:
                raise VoiceDenied("No active voice session")
            if self.clock() >= self.deadline:
                await self._stop()
                raise VoiceDenied("Expired voice session")
            if hasattr(self.backend, "listening") and not await self.backend.listening():
                await self._stop()
                raise VoiceDenied("Voice no longer listening")
            self.deadline = self.clock() + LEASE_SECONDS
            return self.status()

    async def expire(self):
        async with self.lock:
            if self.active and self.clock() >= self.deadline:
                await self._stop()

    async def disconnect(self, connection):
        async with self.lock:
            if self.active and self.active.connection == connection:
                await self._stop()


class VoiceConnection:
    """One authenticated connection; replay handling lasts for its lifetime."""
    def __init__(self, service, owner, connection):
        self.service = service
        self.owner = owner
        self.connection = connection
        self.session = None
        self.last = 0
        self.desired = False

    async def dispatch(self, request):
        if isinstance(request, dict) and request == {"type": "aeon.voice.heartbeat"}:
            return await self.service.heartbeat(self.session)
        session = validate(self.owner, self.connection, request)
        if self.session and self.session != session:
            raise VoiceDenied("Game launch changed")
        seq, enabled = request["sequence"], request["enabled"]
        if seq < self.last or (seq == self.last and enabled != self.desired):
            raise VoiceDenied("Stale or conflicting sequence")
        if seq == self.last:
            if not enabled:
                return {"type": "aeon.voice.status", "state": "stopped"}
            if enabled and self.service.active != session:
                raise VoiceDenied("Expired request")
            return self.service.status()
        # Never restart an expired session on a heartbeat or duplicate request.
        if enabled and self.service.active == session:
            await self.service.heartbeat(session)
            result = self.service.status()
        else:
            result = await self.service.set(session, enabled)
        self.session, self.last, self.desired = session, seq, enabled
        return result
