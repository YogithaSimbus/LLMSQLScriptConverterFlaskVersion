# Databricks notebook source
# MAGIC %md
# MAGIC # t-sql scripts - codebase celebal_query_1
# MAGIC This notebook was automatically converted from the script below. It may contain errors, so use it as a starting point and make necessary corrections.
# MAGIC
# MAGIC Source script: `/Volumes/lakebridge/switch/switch_volume/upload_1771854827/t-sql scripts - codebase celebal_query_1.sql`

# COMMAND ----------

# Create a view equivalent in Databricks
spark.sql("""
CREATE OR REPLACE VIEW MNSReporting_4P_MobilityData AS
SELECT 
    `Consumption Period`,
    `GIDUser Business` AS GIDUserBusiness,
    `GIDUser CustomerLevel1` AS GIDUSerCustomerLevel1,
    `GIDUser CustomerLevel2` AS GIDUSerCustomerLevel2,
    `GIDUser CustomerLevel3` AS GIDUSerCustomerLevel3,
    SUM(CAST(`Amount before Tax USD` AS DECIMAL(18,2))) AS Amount
FROM 
    MNS_Shell_Business_Mobility_Detailed
WHERE 
    (`Consumption Period` IN ('201912', '202012') 
     OR `Consumption Period` >= DATE_FORMAT(DATE_SUB(current_date(), 6), 'yyyyMM'))
GROUP BY 
    `Consumption Period`, 
    `GIDUser Business`, 
    `GIDUser CustomerLevel1`, 
    `GIDUser CustomerLevel2`, 
    `GIDUser CustomerLevel3`
""")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Static Syntax Check Results
# MAGIC No syntax errors were detected during the static check.
# MAGIC However, please review the code carefully as some issues may only be detected during runtime.