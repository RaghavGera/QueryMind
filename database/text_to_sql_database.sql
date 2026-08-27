-- ============================================================
-- TEXT-TO-SQL E-COMMERCE DATABASE
-- PostgreSQL
--
-- EXACT DATASET:
-- 500 customers
-- 100 products
-- 2,000 orders
-- 5,000 order items
-- 5 countries
-- 14+ months of dates
-- Structured customer behavior
-- ============================================================


-- ============================================================
-- 1. CLEAN DATABASE
-- ============================================================

DROP TABLE IF EXISTS order_items CASCADE;
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS products CASCADE;
DROP TABLE IF EXISTS customers CASCADE;


-- ============================================================
-- 2. CUSTOMERS
-- ============================================================

CREATE TABLE customers (
    customer_id SERIAL PRIMARY KEY,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    country VARCHAR(50) NOT NULL,
    signup_date DATE NOT NULL
);


-- EXACTLY 500 CUSTOMERS

INSERT INTO customers (
    first_name,
    last_name,
    email,
    country,
    signup_date
)
SELECT
    'Customer' || gs,
    'User' || gs,
    'customer' || gs || '@example.com',

    CASE
        WHEN gs % 5 = 0 THEN 'India'
        WHEN gs % 5 = 1 THEN 'USA'
        WHEN gs % 5 = 2 THEN 'UK'
        WHEN gs % 5 = 3 THEN 'Canada'
        ELSE 'Australia'
    END,

    CASE
        -- 20 recently joined customers
        WHEN gs >= 481 THEN
            CURRENT_DATE - ((gs - 480) * 2)::INTEGER

        -- Older customers spread across ~14 months
        ELSE
            CURRENT_DATE -
            (30 + ((gs * 17) % 400))::INTEGER
    END

FROM generate_series(1, 500) AS gs;


-- ============================================================
-- 3. PRODUCTS
-- ============================================================

CREATE TABLE products (
    product_id SERIAL PRIMARY KEY,
    product_name VARCHAR(150) NOT NULL,
    category VARCHAR(50) NOT NULL,
    price NUMERIC(10,2) NOT NULL
);


-- EXACTLY 100 PRODUCTS

INSERT INTO products (
    product_name,
    category,
    price
)
SELECT

    CASE
        WHEN gs <= 20 THEN 'Laptop ' || gs
        WHEN gs <= 40 THEN 'Phone ' || (gs - 20)
        WHEN gs <= 55 THEN 'Headphones ' || (gs - 40)
        WHEN gs <= 70 THEN 'Keyboard ' || (gs - 55)
        WHEN gs <= 85 THEN 'Monitor ' || (gs - 70)
        ELSE 'Accessory ' || (gs - 85)
    END,

    CASE
        WHEN gs <= 20 THEN 'Laptops'
        WHEN gs <= 40 THEN 'Phones'
        WHEN gs <= 55 THEN 'Audio'
        WHEN gs <= 70 THEN 'Accessories'
        WHEN gs <= 85 THEN 'Monitors'
        ELSE 'Accessories'
    END,

    CASE
        -- Laptops: 600 - 1999
        WHEN gs <= 20 THEN
            (600 + ((gs * 137) % 1400))::NUMERIC(10,2)

        -- Phones: 250 - 1249
        WHEN gs <= 40 THEN
            (250 + ((gs * 83) % 1000))::NUMERIC(10,2)

        -- Audio: 40 - 299
        WHEN gs <= 55 THEN
            (40 + ((gs * 29) % 260))::NUMERIC(10,2)

        -- Keyboards: 20 - 199
        WHEN gs <= 70 THEN
            (20 + ((gs * 17) % 180))::NUMERIC(10,2)

        -- Monitors: 180 - 879
        WHEN gs <= 85 THEN
            (180 + ((gs * 47) % 700))::NUMERIC(10,2)

        -- Accessories: 10 - 159
        ELSE
            (10 + ((gs * 13) % 150))::NUMERIC(10,2)
    END

FROM generate_series(1, 100) AS gs;


-- ============================================================
-- 4. ORDERS
-- ============================================================

CREATE TABLE orders (
    order_id SERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
    order_date DATE NOT NULL,
    status VARCHAR(30) NOT NULL
);


-- ============================================================
-- EXACTLY 2,000 ORDERS
--
-- Customers 1-10:
--     30 orders each = 300
--
-- Customers 11-50:
--     15 orders each = 600
--
-- Customers 51-250:
--     3 orders each = 600
--
-- Customers 251-450:
--     2 orders each = 400
--
-- Customers 451-500:
--     0 orders
--
-- TOTAL:
--     300 + 600 + 600 + 400 = 1,900
--
-- Remaining 100 orders are distributed among
-- customers 51-250.
--
-- TOTAL = EXACTLY 2,000
-- ============================================================


-- HIGH-VALUE CUSTOMERS
-- 1-10 get exactly 30 orders each = 300

INSERT INTO orders (
    customer_id,
    order_date,
    status
)
SELECT
    c.customer_id,

    CURRENT_DATE -
    (((o.order_number * 11 + c.customer_id * 3) % 430)::INTEGER),

    CASE
        WHEN o.order_number % 20 = 0 THEN 'Cancelled'
        WHEN o.order_number % 13 = 0 THEN 'Pending'
        ELSE 'Completed'
    END

FROM customers c
CROSS JOIN generate_series(1, 30) AS o(order_number)

WHERE c.customer_id BETWEEN 1 AND 10;


-- MEDIUM-HIGH CUSTOMERS
-- 11-50 get exactly 15 orders each = 600

INSERT INTO orders (
    customer_id,
    order_date,
    status
)
SELECT
    c.customer_id,

    CURRENT_DATE -
    (((o.order_number * 19 + c.customer_id * 5) % 430)::INTEGER),

    CASE
        WHEN o.order_number % 17 = 0 THEN 'Cancelled'
        WHEN o.order_number % 11 = 0 THEN 'Pending'
        ELSE 'Completed'
    END

FROM customers c
CROSS JOIN generate_series(1, 15) AS o(order_number)

WHERE c.customer_id BETWEEN 11 AND 50;


-- NORMAL CUSTOMERS
-- 51-250 get exactly 3 orders each = 600

INSERT INTO orders (
    customer_id,
    order_date,
    status
)
SELECT
    c.customer_id,

    CURRENT_DATE -
    (((o.order_number * 23 + c.customer_id * 7) % 430)::INTEGER),

    CASE
        WHEN o.order_number % 19 = 0 THEN 'Cancelled'
        WHEN o.order_number % 13 = 0 THEN 'Pending'
        ELSE 'Completed'
    END

FROM customers c
CROSS JOIN generate_series(1, 3) AS o(order_number)

WHERE c.customer_id BETWEEN 51 AND 250;


-- LOW-ACTIVITY CUSTOMERS
-- 251-450 get exactly 2 orders each = 400

INSERT INTO orders (
    customer_id,
    order_date,
    status
)
SELECT
    c.customer_id,

    CURRENT_DATE -
    (((o.order_number * 31 + c.customer_id * 9) % 430)::INTEGER),

    CASE
        WHEN o.order_number % 23 = 0 THEN 'Cancelled'
        WHEN o.order_number % 17 = 0 THEN 'Pending'
        ELSE 'Completed'
    END

FROM customers c
CROSS JOIN generate_series(1, 2) AS o(order_number)

WHERE c.customer_id BETWEEN 251 AND 450;


-- ADD EXACTLY 100 MORE ORDERS
-- Distributed among customers 51-250

INSERT INTO orders (
    customer_id,
    order_date,
    status
)
SELECT
    51 + ((gs - 1) % 200),

    CURRENT_DATE -
    (((gs * 37) % 430)::INTEGER),

    CASE
        WHEN gs % 23 = 0 THEN 'Cancelled'
        WHEN gs % 17 = 0 THEN 'Pending'
        ELSE 'Completed'
    END

FROM generate_series(1, 100) AS gs;


-- ============================================================
-- 5. ORDER ITEMS
-- ============================================================

CREATE TABLE order_items (
    order_item_id SERIAL PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders(order_id),
    product_id INTEGER NOT NULL REFERENCES products(product_id),
    quantity INTEGER NOT NULL,
    unit_price NUMERIC(10,2) NOT NULL
);


-- ============================================================
-- EXACTLY 5,000 ORDER ITEMS
--
-- 2 items for every order = 4,000
-- 1 extra item for every even order = 1,000
--
-- TOTAL = 5,000
-- ============================================================


-- FIRST ITEM FOR EVERY ORDER
-- 2,000 items

INSERT INTO order_items (
    order_id,
    product_id,
    quantity,
    unit_price
)
SELECT
    o.order_id,

    ((o.order_id * 17) % 100) + 1,

    CASE
        WHEN o.order_id % 20 = 0 THEN 3
        WHEN o.order_id % 7 = 0 THEN 2
        ELSE 1
    END,

    p.price

FROM orders o

JOIN products p
    ON p.product_id = ((o.order_id * 17) % 100) + 1;


-- SECOND ITEM FOR EVERY ORDER
-- 2,000 items

INSERT INTO order_items (
    order_id,
    product_id,
    quantity,
    unit_price
)
SELECT
    o.order_id,

    ((o.order_id * 31 + 7) % 100) + 1,

    CASE
        WHEN o.order_id % 9 = 0 THEN 3
        ELSE 1
    END,

    p.price

FROM orders o

JOIN products p
    ON p.product_id = ((o.order_id * 31 + 7) % 100) + 1;


-- THIRD ITEM FOR EVERY EVEN ORDER
-- Exactly 1,000 items

INSERT INTO order_items (
    order_id,
    product_id,
    quantity,
    unit_price
)
SELECT
    o.order_id,

    ((o.order_id * 47 + 13) % 100) + 1,

    CASE
        WHEN o.order_id % 15 = 0 THEN 3
        ELSE 1
    END,

    p.price

FROM orders o

JOIN products p
    ON p.product_id = ((o.order_id * 47 + 13) % 100) + 1

WHERE o.order_id % 2 = 0;


-- ============================================================
-- 6. INDEXES
-- ============================================================

CREATE INDEX idx_orders_customer
ON orders(customer_id);

CREATE INDEX idx_orders_date
ON orders(order_date);

CREATE INDEX idx_order_items_order
ON order_items(order_id);

CREATE INDEX idx_order_items_product
ON order_items(product_id);

CREATE INDEX idx_customers_country
ON customers(country);

CREATE INDEX idx_products_category
ON products(category);


-- ============================================================
-- 7. ANALYTICAL VIEW
-- ============================================================

CREATE VIEW order_details AS
SELECT
    o.order_id,
    o.customer_id,

    c.first_name,
    c.last_name,
    c.country,

    c.signup_date,

    o.order_date,
    o.status,

    oi.order_item_id,
    oi.product_id,

    p.product_name,
    p.category,

    oi.quantity,
    oi.unit_price,

    (oi.quantity * oi.unit_price) AS item_total

FROM orders o

JOIN customers c
    ON c.customer_id = o.customer_id

JOIN order_items oi
    ON oi.order_id = o.order_id

JOIN products p
    ON p.product_id = oi.product_id;


-- ============================================================
-- 8. FINAL VERIFICATION
-- ============================================================

SELECT
    'customers' AS table_name,
    COUNT(*) AS row_count
FROM customers

UNION ALL

SELECT
    'products',
    COUNT(*)
FROM products

UNION ALL

SELECT
    'orders',
    COUNT(*)
FROM orders

UNION ALL

SELECT
    'order_items',
    COUNT(*)
FROM order_items;


-- ============================================================
-- 9. CUSTOMER ORDER DISTRIBUTION
-- ============================================================


SELECT
    p.product_name,
    p.category,
    SUM(oi.quantity) AS units_sold,
    ROUND(SUM(oi.quantity * oi.unit_price), 2) AS revenue
FROM products p
JOIN order_items oi
    ON oi.product_id = p.product_id
JOIN orders o
    ON o.order_id = oi.order_id
WHERE o.status = 'Completed'
GROUP BY p.product_id, p.product_name, p.category
ORDER BY revenue DESC
LIMIT 10;