import asyncio
import os
from kagami.core.caching.redis import RedisClientFactory


async def check_redis():
    print("--- REDIS CHECK ---")
    try:
        # Use default redis URL from docker-compose usually maps to localhost:6379
        # But inside docker-compose network it's 'redis'.
        # From host (where I am running), it should be localhost:6379 if ports are mapped.
        # docker-compose.yml usually maps ports.

        redis = RedisClientFactory.get_client("default", async_mode=True, decode_responses=True)
        pong = await redis.ping()
        print(f"Redis Ping: {pong}")

        keys = await redis.keys("receipts:*")
        print(f"Receipt Keys ({len(keys)}): {keys[:5]}...")

        idem_keys = await redis.keys("kagami:idem:*")
        print(f"Idempotency Keys ({len(idem_keys)}): {idem_keys[:5]}...")

        # Test write/read
        await redis.set("kagami:test:verification", "passed")
        val = await redis.get("kagami:test:verification")
        print(f"Test Write/Read: {val}")

    except Exception as e:
        print(f"Redis Check Failed: {e}")


if __name__ == "__main__":
    # Force localhost for host-based check if not set
    if not os.getenv("REDIS_URL"):
        os.environ["REDIS_URL"] = "redis://localhost:6379/0"

    asyncio.run(check_redis())
