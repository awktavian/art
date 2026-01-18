import asyncio
from kagami.core.database.cockroach import CockroachDB, CockroachConfig


async def check_db():
    print("--- COCKROACHDB CHECK ---")
    try:
        # Default config uses localhost:26257
        config = CockroachConfig(
            host="localhost",
            port=26257,
            user="root",
            database="defaultdb",  # Usually defaultdb or kagami
        )

        # Try 'kagami' first, if fails, 'defaultdb'
        db = CockroachDB(config)
        try:
            await db.connect()
            print("Connected to 'defaultdb' (or configured default)")
        except Exception:
            print("Could not connect with default settings, trying 'kagami' db...")
            config.database = "kagami"
            db = CockroachDB(config)
            await db.connect()
            print("Connected to 'kagami' db")

        res = await db.execute("SELECT version()")
        print(f"DB Version: {res.scalar()}")

        # Check receipts table
        try:
            res = await db.execute("SELECT count(*) FROM receipts")
            count = res.scalar()
            print(f"Receipts Count: {count}")

            if count > 0:
                rows = await db.execute(
                    "SELECT correlation_id, phase, status FROM receipts ORDER BY ts DESC LIMIT 5"
                )
                print("Recent Receipts:")
                for row in rows:
                    print(f"  - {row}")
        except Exception as e:
            print(f"Could not query receipts table (might not exist): {e}")

    except Exception as e:
        print(f"DB Check Failed: {e}")
    finally:
        if "db" in locals() and db._connected:
            await db.disconnect()


if __name__ == "__main__":
    asyncio.run(check_db())
