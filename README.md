# FlexiMart Data Architecture Project
**Student Name**: Yaswant Singh

**Student ID**: bitsom_ba_25071501

**Email**: yash.tech1122@gmail.com

**Date**: 07-JAN-2026

## Project Overview
This project implements an end-to-end data architecture for FlexiMart, covering transactional data ingestion, data cleaning, relational storage, NoSQL modeling, and analytical reporting. It includes a Python-based ETL pipeline for structured data, MongoDB-based flexible product catalog storage.

## Repository Structure
├── part1-database-etl/
│   ├── etl_pipeline.py
│   ├── schema_documentation.md
│   ├── business_queries.sql
│   └── data_quality_report.txt
├── part2-nosql/
│   ├── nosql_analysis.md
│   ├── mongodb_operations.js
│   └── products_catalog.json
├── part3-datawarehouse/
│   ├── star_schema_design.md
│   ├── warehouse_schema.sql
│   ├── warehouse_data.sql
│   └── analytics_queries.sql
└── README.md

## Technologies Used

- Python 3.x, pandas, mysql-connector-python
- MySQL 8.0 / PostgreSQL 14
- MongoDB 6.0

## Setup Instructions

### Database Setup

```bash
# Create databases
mysql -u root -p -e "CREATE DATABASE fleximart;"
mysql -u root -p -e "CREATE DATABASE fleximart_dw;"

# Run Part 1 - ETL Pipeline
python part1-database-etl/etl_pipeline.py

# Run Part 1 - Business Queries
mysql -u root -p fleximart < part1-database-etl/business_queries.sql

# Run Part 3 - Data Warehouse
mysql -u root -p fleximart_dw < part3-datawarehouse/warehouse_schema.sql
mysql -u root -p fleximart_dw < part3-datawarehouse/warehouse_data.sql
mysql -u root -p fleximart_dw < part3-datawarehouse/analytics_queries.sql


### MongoDB Setup

mongosh < part2-nosql/mongodb_operations.js

## Key Learnings
This project strengthened my understanding of real-world data quality challenges and how to address them using ETL best practices. I learned how relational databases and NoSQL databases serve different business needs and how to choose the right data model accordingly. Designing a star schema helped me understand dimensional modeling and its importance for analytical workloads.

## Challenges Faced
**1. Handling inconsistent and missing data in CSV files**
This was resolved by applying appropriate transformation strategies such as deduplication, default value imputation, and standardization using pandas.

**2. Designing a schema that supports flexible product attributes**
This challenge was addressed by using MongoDB’s document-based model with embedded documents, eliminating the need for frequent schema changes.
