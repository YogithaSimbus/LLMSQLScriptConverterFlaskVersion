CREATE EXTERNAL TABLE ext_events (
    event_id NUMBER,
    event_type VARCHAR
)
WITH LOCATION='@my_stage/events/'
FILE_FORMAT=(TYPE=CSV);
