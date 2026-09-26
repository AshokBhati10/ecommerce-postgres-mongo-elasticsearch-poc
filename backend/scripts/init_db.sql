-- PostgreSQL schema: source of truth for users, orders, order items.
-- Order item rows keep a title/price snapshot taken from MongoDB at checkout.

CREATE TABLE IF NOT EXISTS users (
    id         SERIAL PRIMARY KEY,
    name       TEXT NOT NULL,
    email      TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS orders (
    id           SERIAL PRIMARY KEY,
    user_id      INTEGER NOT NULL REFERENCES users (id),
    order_date   TIMESTAMPTZ NOT NULL DEFAULT now(),
    status       TEXT NOT NULL DEFAULT 'PENDING'
                 CHECK (status IN ('PENDING', 'PROCESSING', 'SHIPPED')),
    total_amount NUMERIC(10, 2) NOT NULL,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS order_items (
    id         SERIAL PRIMARY KEY,
    order_id   INTEGER NOT NULL REFERENCES orders (id) ON DELETE CASCADE,
    product_id TEXT NOT NULL,          -- MongoDB ObjectId as text
    title      TEXT NOT NULL,          -- snapshot at checkout
    quantity   INTEGER NOT NULL CHECK (quantity > 0),
    unit_price NUMERIC(10, 2) NOT NULL -- snapshot at checkout
);

CREATE INDEX IF NOT EXISTS idx_orders_user_id    ON orders (user_id);
CREATE INDEX IF NOT EXISTS idx_orders_updated_at ON orders (updated_at);
CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items (order_id);
