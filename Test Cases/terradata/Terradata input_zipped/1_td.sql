-- Create database with space allocation
CREATE DATABASE sales_db AS PERM = 100000000;

-- Create table
CREATE MULTISET TABLE sales_db.customers (
    customer_id INTEGER,
    customer_name VARCHAR(50),
    city VARCHAR(30),
    region VARCHAR(20)
)
PRIMARY INDEX (customer_id);
