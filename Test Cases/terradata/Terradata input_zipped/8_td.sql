-- Bronze
CREATE MULTISET TABLE bronze.orders_raw (
    order_id INTEGER,
    customer_id INTEGER,
    order_date DATE,
    order_amount DECIMAL(10,2)
)
PRIMARY INDEX (order_id);

-- Silver
CREATE SET TABLE silver.orders_clean AS
(
    SELECT *
    FROM bronze.orders_raw
    WHERE order_amount > 0
) WITH DATA
PRIMARY INDEX (order_id);

-- Gold
CREATE TABLE gold.customer_revenue AS
(
    SELECT
        customer_id,
        SUM(order_amount) AS total_revenue
    FROM silver.orders_clean
    GROUP BY customer_id
) WITH DATA;
