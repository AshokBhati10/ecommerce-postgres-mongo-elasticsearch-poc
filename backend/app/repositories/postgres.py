"""PostgreSQL access. All order writes happen inside explicit transactions."""
from datetime import datetime, timezone

from psycopg_pool import ConnectionPool


def list_users(pool: ConnectionPool) -> list[dict]:
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT id, name, email FROM users ORDER BY id")
        return cur.fetchall()


def get_user(pool: ConnectionPool, user_id: int) -> dict | None:
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT id, name, email FROM users WHERE id = %s", (user_id,))
        return cur.fetchone()


def create_order(
    pool: ConnectionPool,
    user_id: int,
    items: list[dict],
    order_date: datetime | None = None,
    status: str = "PENDING",
) -> dict:
    """Insert one order + its items atomically. items carry the Mongo snapshot:
    {product_id, title, quantity, unit_price}. Returns the created order row."""
    total = round(sum(i["quantity"] * float(i["unit_price"]) for i in items), 2)
    with pool.connection() as conn, conn.cursor() as cur:
        # Explicit transaction boundary: everything below commits or rolls back together.
        with conn.transaction():
            cur.execute(
                """
                INSERT INTO orders (user_id, order_date, status, total_amount)
                VALUES (%s, %s, %s, %s)
                RETURNING id, user_id, order_date, status, total_amount, updated_at
                """,
                (user_id, order_date or datetime.now(timezone.utc), status, total),
            )
            order = cur.fetchone()
            cur.executemany(
                """
                INSERT INTO order_items (order_id, product_id, title, quantity, unit_price)
                VALUES (%s, %s, %s, %s, %s)
                """,
                [
                    (order["id"], i["product_id"], i["title"], i["quantity"], i["unit_price"])
                    for i in items
                ],
            )
    return order


def get_order(pool: ConnectionPool, order_id: int) -> dict | None:
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT o.id, o.user_id, o.order_date, o.status, o.total_amount, o.updated_at,
                   u.name AS customer_name, u.email AS customer_email
            FROM orders o JOIN users u ON u.id = o.user_id
            WHERE o.id = %s
            """,
            (order_id,),
        )
        order = cur.fetchone()
        if not order:
            return None
        cur.execute(
            """
            SELECT product_id, title, quantity, unit_price
            FROM order_items WHERE order_id = %s ORDER BY id
            """,
            (order_id,),
        )
        order["items"] = cur.fetchall()
    return order


def update_order_status(pool: ConnectionPool, order_id: int, status: str) -> dict | None:
    with pool.connection() as conn, conn.cursor() as cur:
        with conn.transaction():
            cur.execute(
                """
                UPDATE orders SET status = %s, updated_at = now()
                WHERE id = %s
                RETURNING id, user_id, order_date, status, total_amount, updated_at
                """,
                (status, order_id),
            )
            order = cur.fetchone()
    return order


def get_changed_orders(pool: ConnectionPool, since: datetime) -> list[dict]:
    """Orders (with items + customer) changed after `since`. Used by polling sync."""
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT o.id, o.user_id, o.order_date, o.status, o.total_amount, o.updated_at,
                   u.name AS customer_name, u.email AS customer_email
            FROM orders o JOIN users u ON u.id = o.user_id
            WHERE o.updated_at > %s
            ORDER BY o.updated_at
            """,
            (since,),
        )
        orders = cur.fetchall()
        for order in orders:
            cur.execute(
                """
                SELECT product_id, title, quantity, unit_price
                FROM order_items WHERE order_id = %s ORDER BY id
                """,
                (order["id"],),
            )
            order["items"] = cur.fetchall()
    return orders


def count_orders(pool: ConnectionPool) -> int:
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM orders")
        return cur.fetchone()["n"]
