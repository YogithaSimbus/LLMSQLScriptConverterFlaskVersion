CREATE VOLATILE TABLE vt_recent_orders (
    order_id INTEGER,
    customer_id INTEGER,
    order_date DATE,
    order_amount DECIMAL(10,2)
)
ON COMMIT PRESERVE ROWS;
