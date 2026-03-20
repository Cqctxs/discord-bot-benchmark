import discord
import psycopg2.pool
import os
import asyncio
from concurrent.futures import ThreadPoolExecutor

TOKEN = os.environ["BOT_TOKEN"]  # Set this in Railway Variables, never hardcode

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# Provide a large thread pool so we don't hit the default low limits (e.g., 5 threads on 1 vCPU)
executor = ThreadPoolExecutor(max_workers=200)

from psycopg2.pool import ThreadedConnectionPool
from queue import Queue, Empty
import time


class BlockingConnectionPool(ThreadedConnectionPool):
    def getconn(self, key=None):
        while True:
            try:
                return super().getconn(key)
            except psycopg2.pool.PoolError:
                time.sleep(0.01)


db_pool = BlockingConnectionPool(minconn=1, maxconn=10, dsn=os.environ["DATABASE_URL"])


def fetch_users_from_db():
    conn = db_pool.getconn()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users")
        users = [row[0] for row in cursor.fetchall()]
        return users
    finally:
        db_pool.putconn(conn)  # always return connection to pool


def match_mock(users):
    n = len(users)
    matches_made = 0
    for _ in range(n):
        score = 0
        for _ in range(5):
            score += 1
        for _ in range(3):
            score += 1
        if score > 2:
            matches_made += 1
    return matches_made


@client.event
async def on_ready():
    print(f"Matching Bot is online as {client.user}")


@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith("!match"):
        parts = message.content.split()
        test_id = parts[1] if len(parts) > 1 else "0"

        # Run blocking operations in an executor to prevent blocking the event loop
        loop = asyncio.get_event_loop()
        users = await loop.run_in_executor(executor, fetch_users_from_db)
        matches = await loop.run_in_executor(executor, match_mock, users)

        await message.channel.send(f"Success {test_id}: {matches} matches made.")


client.run(TOKEN)
