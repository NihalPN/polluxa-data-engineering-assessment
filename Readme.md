# Polluxa Data Engineering Assessment: LinkedIn Agent Analytics

## 📌 Project Overview
This repository contains a full-stack, production-ready data pipeline and analytics platform built for the Polluxa engineering assessment. It ingests simulated LinkedIn automation event data, enforces data quality, detects operational anomalies via a risk model, and surfaces insights through a Power BI dashboard.

## 🏗️ Architectural Decisions (Part 1)
Given the requirements for a self-contained, reproducible environment, the backend is orchestrated using **Python** and **SQLite3**. 
*   **Storage:** SQLite provides a zero-config, portable relational database that allows reviewers to test the environment instantly.
*   **Modeling:** The database is structured using a strict Kimball Star Schema.
*   **Idempotency:** All inserts utilize `ON CONFLICT` constraints or `WHERE NOT EXISTS` logic to prevent duplication during re-runs.

## ⚙️ Data Ingestion & Transformation (Part 2 & 3)
The ETL pipeline (`ingestion_pipeline.py` and `build_star_schema.py`) simulates fetching API data via incremental CSV processing.
*   **Watermarking:** A `watermarks` table tracks the `max(event_timestamp)` of successful runs to enable incremental loading.
*   **Dead-Letter Queue (DLQ):** Malformed payloads (e.g., missing `lead_id`) are routed to a `dead_letter_queue` table with rejection reasons rather than halting the pipeline.
*   **Star Schema:** The staging data is transformed into a centralized Fact table (`fct_agent_events`) surrounded by strictly conforming Dimensions (`dim_lead`, `dim_campaign`, `dim_agent`, `dim_date`).

## 🛡️ Data Quality & Observability (Part 4)
Data Quality is treated as a first-class citizen.
*   **Completeness, Uniqueness, & Validity:** The DQ pipeline calculates a composite score. If the score drops below the 95.0% threshold, it triggers an alert and halts downstream processing.
*   **Audit Logging:** Every ETL execution writes telemetry (rows processed, duration, status) to a `pipeline_runs` audit table using a unique UUID as a correlation ID.

## 🚨 Risk Intelligence & Anomaly Detection (Part 5)
The `anomaly_risk_model.py` module establishes a programmatic safety limit for LinkedIn agents.
*   **Dynamic Limits:** Calculates a Rolling 7-Day Acceptance Rate. 
*   **Z-Score Anomaly Detection:** Compares daily agent throughput against historical averages to calculate a risk score (0-100). If an agent spikes activity abnormally, their recommended limits are throttled to prevent account bans.

## 📊 BI & Visualization (Part 6)
The presentation layer is handled via Power BI (`LinkedIn_Agent_Analytics.pbix`).
*   **Explicit DAX:** All aggregations are handled via explicit measures in a dedicated `_Measures` table (e.g., `COUNTROWS`, `DIVIDE`, `AVERAGEX`) rather than implicit visual aggregations.
*   **Reporting:** The canvas provides a high-level view of Core KPIs, Campaign ROI, Risk Intelligence thresholds, and individual Account Health funnels. 

## 🚀 DevOps & CI/CD (Part 7)
The pipeline is designed for containerized deployment and automated testing.
*   **Containerization:** A `Dockerfile` is provided with pinned dependencies (`pandas==2.1.4`) and externalized environment variables (`POLLUXA_API_TOKEN`).
*   **CI/CD Pipeline:** A GitHub Actions workflow (`.github/workflows/data_pipeline_ci.yml`) triggers on pull requests to run code linting (`flake8`) and a dry-run integration test.
*   **Structured Logging & Alerting:** The Python modules output machine-parseable JSON logs containing the `correlation_id`. A mocked webhook function simulates triggering PagerDuty/Slack alerts upon pipeline failure.

## 🛠️ How to Run Locally

**Option 1: Python Virtual Environment**
```bash
pip install -r requirements.txt
python ingestion_pipeline.py
python build_star_schema.py
python anomaly_risk_model.py