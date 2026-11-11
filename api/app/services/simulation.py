"""Is anyone in Simulation mode? Decides whether the simulator runs.

A lease in Redis: browsers in Simulation mode refresh a key that expires on its own. While
the key exists the simulator sends readings; once nobody refreshes it (everyone switched to
Live, closed the tab, or lost connection) it expires and the simulator goes idle.
Nothing tracks *who* is watching: several viewers just keep refreshing the same key.
"""

from arq.connections import ArqRedis

ACTIVE_KEY = "simulation:active"
# Browsers refresh every 30s; 90s leaves room for two missed refreshes (a slow network)
# before the simulation stops.
LEASE_S = 90


async def keep_alive(redis: ArqRedis) -> None:
    """Start the simulation, or keep it running for another LEASE_S seconds."""
    await redis.set(ACTIVE_KEY, "1", ex=LEASE_S)


async def stop(redis: ArqRedis) -> None:
    """Stop at once. Other viewers still in Simulation mode restart it on their next refresh."""
    await redis.delete(ACTIVE_KEY)


async def is_active(redis: ArqRedis) -> bool:
    return bool(await redis.exists(ACTIVE_KEY))
