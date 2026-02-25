MERGE INTO sales_db.customers tgt
USING sales_db.customers_staging src
ON tgt.customer_id = src.customer_id
WHEN MATCHED THEN
    UPDATE SET
        customer_name = src.customer_name,
        city = src.city,
        region = src.region
WHEN NOT MATCHED THEN
    INSERT (
        customer_id,
        customer_name,
        city,
        region
    )
    VALUES (
        src.customer_id,
        src.customer_name,
        src.city,
        src.region
    );
