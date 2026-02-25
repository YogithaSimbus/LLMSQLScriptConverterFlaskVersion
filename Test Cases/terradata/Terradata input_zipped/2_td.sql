CREATE SET TABLE sales_db.orders (
    order_id INTEGER,
    customer_id INTEGER,
    order_date DATE,
    order_amount DECIMAL(10,2),
    order_status VARCHAR(20) COMPRESS ('NEW','SHIPPED','CANCELLED')
)
PRIMARY INDEX (order_id);
