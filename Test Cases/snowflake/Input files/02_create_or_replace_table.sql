CREATE OR REPLACE TABLE customers (
    customer_id NUMBER,
    customer_name VARCHAR(50),
    created_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);
