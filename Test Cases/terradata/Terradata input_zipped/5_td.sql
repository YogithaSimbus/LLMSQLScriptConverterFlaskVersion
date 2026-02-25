REPLACE PROCEDURE sales_db.sp_get_customer_orders (
    IN p_customer_id INTEGER
)
BEGIN
    SELECT
        order_id,
        order_date,
        order_amount
    FROM sales_db.orders
    WHERE customer_id = p_customer_id;
END;
