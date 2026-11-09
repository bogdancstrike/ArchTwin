CREATE TABLE customers (id serial PRIMARY KEY, name text NOT NULL, email text NOT NULL, created_at timestamptz DEFAULT now());
CREATE TABLE orders (id serial PRIMARY KEY, customer_id int NOT NULL REFERENCES customers(id), sku text NOT NULL, qty int NOT NULL,
                     total_cents int NOT NULL, created_at timestamptz DEFAULT now());
CREATE TABLE payments (id serial PRIMARY KEY, order_id int NOT NULL REFERENCES orders(id), card_last4 text, status text NOT NULL);
INSERT INTO customers (name, email) VALUES ('Ada', 'ada@example.test'), ('Linus', 'linus@example.test');
CREATE ROLE archtwin_catalog_ro LOGIN PASSWORD 'catalog-ro';
GRANT CONNECT ON DATABASE orders TO archtwin_catalog_ro;
GRANT USAGE ON SCHEMA public TO archtwin_catalog_ro;
