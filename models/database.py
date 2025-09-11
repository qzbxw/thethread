import asyncpg
from config import Config

class Database:
    def __init__(self):
        self.pool = None

    async def connect(self):
        self.pool = await asyncpg.create_pool(Config.DATABASE_URL)

    async def disconnect(self):
        if self.pool:
            await self.pool.close()

    async def create_tables(self):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    username VARCHAR(255),
                    balance_crystals INTEGER DEFAULT 0,
                    last_free_card_ts TIMESTAMP,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(user_id),
                    payment_provider VARCHAR(50) DEFAULT 'stripe',
                    payment_id VARCHAR(255) UNIQUE,
                    amount_usd DECIMAL(10, 2),
                    amount_crystals INTEGER,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS checkout_sessions (
                    token VARCHAR(64) PRIMARY KEY,
                    user_id BIGINT REFERENCES users(user_id),
                    session_id VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS active_messages (
                    user_id BIGINT PRIMARY KEY REFERENCES users(user_id),
                    message_id BIGINT,
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)

    async def get_user(self, user_id):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)

    async def create_user(self, user_id, username):
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO users (user_id, username) VALUES ($1, $2) ON CONFLICT (user_id) DO NOTHING",
                user_id, username
            )

    async def update_balance(self, user_id, amount):
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET balance_crystals = balance_crystals + $1 WHERE user_id = $2",
                amount, user_id
            )

    async def set_last_free_card(self, user_id):
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET last_free_card_ts = NOW() WHERE user_id = $1",
                user_id
            )

    async def record_transaction(self, user_id, payment_id, amount_usd, amount_crystals):
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO transactions (user_id, payment_id, amount_usd, amount_crystals) VALUES ($1, $2, $3, $4)",
                user_id, payment_id, amount_usd, amount_crystals
            )

    async def transaction_exists(self, payment_id: str) -> bool:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT 1 FROM transactions WHERE payment_id = $1",
                payment_id,
            )
            return row is not None

    async def save_checkout_session(self, user_id: int, token: str, session_id: str):
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO checkout_sessions (token, user_id, session_id) VALUES ($1, $2, $3) ON CONFLICT (token) DO UPDATE SET session_id = EXCLUDED.session_id, user_id = EXCLUDED.user_id",
                token, user_id, session_id
            )

    async def get_session_id_by_token(self, token: str):
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT session_id FROM checkout_sessions WHERE token = $1",
                token
            )
            return row['session_id'] if row else None

    async def delete_checkout_session(self, token: str):
        async with self.pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM checkout_sessions WHERE token = $1",
                token
            )

    async def get_active_message_id(self, user_id: int) -> int | None:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT message_id FROM active_messages WHERE user_id = $1",
                user_id,
            )
            return row['message_id'] if row else None

    async def set_active_message_id(self, user_id: int, message_id: int):
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO active_messages (user_id, message_id, updated_at) VALUES ($1, $2, NOW()) ON CONFLICT (user_id) DO UPDATE SET message_id = EXCLUDED.message_id, updated_at = NOW()",
                user_id, message_id,
            )

db = Database()
