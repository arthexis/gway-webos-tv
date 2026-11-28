import asyncio

import pytest

from gway_webos_tv.aeon_voice import GAME, RELEASE, VoiceConnection, VoiceDenied, VoiceSession


class FakeVoice:
    def __init__(self):
        self.starts = []
        self.stops = 0
        self.fail_stop = False

    async def start(self, session):
        self.starts.append(session)

    async def stop(self):
        self.stops += 1
        if self.fail_stop:
            raise RuntimeError("stop failed")


def request(seq=1, enabled=True, **kwargs):
    return {"type": "aeon.voice.set", "game": GAME, "release": RELEASE,
            "launch": "a"*32, "connection": "connection-a", "sequence": seq,
            "enabled": enabled, **kwargs}


def test_shared_toggle_and_lease():
    async def check():
        now = [100.]
        backend = FakeVoice()
        svc = VoiceSession(backend, clock=lambda: now[0])
        client = VoiceConnection(svc, "owner", "connection-a")
        assert (await client.dispatch(request()))["state"] == "listening"
        assert (await client.dispatch(request()))["state"] == "listening"
        assert len(backend.starts) == 1
        now[0] += 10
        await client.dispatch({"type": "aeon.voice.heartbeat"})
        now[0] += 10
        await svc.expire()
        assert svc.active
        assert (await client.dispatch(request(2, False)))["state"] == "stopped"
        assert (await client.dispatch(request(2, False)))["state"] == "stopped"
        assert backend.stops == 1
        with pytest.raises(VoiceDenied):
            await client.dispatch(request())
        await client.dispatch(request(3))
        now[0] += 16
        await svc.expire()
        assert svc.active is None
        with pytest.raises(VoiceDenied):
            await client.dispatch(request(3))
        await client.dispatch(request(4))
        await svc.disconnect("connection-a")
        assert svc.active is None and backend.stops == 3
    asyncio.run(check())


def test_denial_and_disconnect():
    async def check():
        svc = VoiceSession(FakeVoice())
        a = VoiceConnection(svc, "owner", "connection-a")
        b = VoiceConnection(svc, "other", "connection-b")
        for bad in (request(game="other"), request(release="0"*64),
                    request(launch="../home"), request(command="anything"),
                    request(connection="connection-b"), request(enabled=1)):
            with pytest.raises(VoiceDenied):
                await a.dispatch(bad)
        await a.dispatch(request())
        with pytest.raises(VoiceDenied):
            await b.dispatch(request(connection="connection-b"))
        with pytest.raises(VoiceDenied):
            await a.dispatch(request(2, launch="b"*32))
        await svc.disconnect("connection-b")
        assert svc.active
        await svc.disconnect("connection-a")
        assert not svc.active
        with pytest.raises(VoiceDenied):
            await VoiceConnection(VoiceSession(), "owner", "connection-a").dispatch(request())
    asyncio.run(check())


def test_stop_failure_does_not_report_stopped():
    async def check():
        backend = FakeVoice()
        svc = VoiceSession(backend)
        a = VoiceConnection(svc, "owner", "connection-a")
        await a.dispatch(request())
        backend.fail_stop = True
        with pytest.raises(VoiceDenied):
            await a.dispatch(request(2, False))
        assert svc.status()["state"] == "unknown"
        with pytest.raises(VoiceDenied):
            await a.dispatch(request(3))
        backend.fail_stop = False
        await a.dispatch(request(4, False))
        assert svc.status()["state"] == "stopped"
    asyncio.run(check())
