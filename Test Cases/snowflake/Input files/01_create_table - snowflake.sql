CREATE TABLE sales (
    sale_id NUMBER(10,0),
    product_name VARCHAR(100),
    sale_amount NUMBER(10,2),
    sale_date TIMESTAMP_NTZ
)
COMMENT = 'Sales table';