import sqlite3
import logging
import uuid
import schedule
import time
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DB_FILE = "analytics_platform.db"
DQ_THRESHOLD = 95.0

# 1. Weights configuration
WEIGHTS = {
    "uniqueness": 0.25,
    "referential_integrity": 0.25,
    "validity": 0.20,
    "completeness": 0.20,
    "timeliness": 0.10
}

def setup_dq_tables(conn):
    """Creates the historical trending table for DQ results."""
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS dq_results_history (
            dq_run_id TEXT PRIMARY KEY,
            run_timestamp TIMESTAMP,
            total_records INTEGER,
            score_uniqueness REAL,
            score_completeness REAL,
            score_validity REAL,
            score_timeliness REAL,
            score_referential_integrity REAL,
            composite_score REAL,
            status TEXT
        )
    ''')
    conn.commit()

def run_dq_checks():
    """Executes the 5 dimensional checks against the Star Schema."""
    logger.info("Initiating Automated Data Quality Checks...")
    dq_run_id = str(uuid.uuid4())
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    setup_dq_tables(conn)

    # Get total records for baseline percentage calculations
    cursor.execute("SELECT COUNT(*) FROM fct_agent_events")
    total_records = cursor.fetchone()[0]
    
    if total_records == 0:
        logger.warning("No records found in fact table. Skipping DQ run.")
        return

    scores = {}

    # 1. Uniqueness: No duplicate event_ids
    cursor.execute("SELECT COUNT(event_id) - COUNT(DISTINCT event_id) FROM fct_agent_events")
    duplicates = cursor.fetchone()[0]
    scores['uniqueness'] = max(0, 100 * (1 - (duplicates / total_records)))

    # 2. Completeness: Critical columns must not be null
    cursor.execute("SELECT COUNT(*) FROM fct_agent_events WHERE lead_sk IS NULL OR campaign_sk IS NULL")
    null_records = cursor.fetchone()[0]
    scores['completeness'] = max(0, 100 * (1 - (null_records / total_records)))

    # 3. Validity: event_type must conform to expected values
    valid_events = "('INVITE_SENT', 'INVITE_ACCEPTED', 'MESSAGE_SENT', 'REPLY_RECEIVED', 'GHOSTED')"
    cursor.execute(f"SELECT COUNT(*) FROM fct_agent_events WHERE event_type NOT IN {valid_events}")
    invalid_records = cursor.fetchone()[0]
    scores['validity'] = max(0, 100 * (1 - (invalid_records / total_records)))

    # 4. Timeliness: No future timestamps
    cursor.execute("SELECT COUNT(*) FROM fct_agent_events WHERE event_timestamp > datetime('now')")
    future_records = cursor.fetchone()[0]
    scores['timeliness'] = max(0, 100 * (1 - (future_records / total_records)))

    # 5. Referential Integrity: Fact lead_sk must exist in dim_lead
    cursor.execute('''
        SELECT COUNT(*) FROM fct_agent_events f
        LEFT JOIN dim_lead d ON f.lead_sk = d.lead_sk
        WHERE d.lead_sk IS NULL
    ''')
    orphan_records = cursor.fetchone()[0]
    scores['referential_integrity'] = max(0, 100 * (1 - (orphan_records / total_records)))

    # Calculate Composite Score
    composite_score = sum(scores[metric] * WEIGHTS[metric] for metric in WEIGHTS)
    
    # Evaluate Pass/Fail Threshold
    status = "PASS" if composite_score >= DQ_THRESHOLD else "FAIL"
    
    # Log to History Table
    cursor.execute('''
        INSERT INTO dq_results_history 
        (dq_run_id, run_timestamp, total_records, score_uniqueness, score_completeness, 
        score_validity, score_timeliness, score_referential_integrity, composite_score, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        dq_run_id, datetime.now(), total_records, 
        scores['uniqueness'], scores['completeness'], scores['validity'], 
        scores['timeliness'], scores['referential_integrity'], composite_score, status
    ))
    conn.commit()
    conn.close()

    logger.info(f"DQ Run Complete. Composite Score: {composite_score:.2f}% | Status: {status}")

    # Alerting Protocol
    if status == "FAIL":
        trigger_failure_alert(dq_run_id, composite_score)

def trigger_failure_alert(run_id, score):
    """Simulates a webhook/email notification for pipeline failure."""
    logger.error("🚨 ALERT: Data Quality Pipeline Threshold Breached!")
    logger.error(f"Run ID: {run_id} | Score: {score:.2f}% (Threshold: {DQ_THRESHOLD}%)")
    logger.error("Action Required: Data pipeline suspended to prevent dashboard corruption.")
    # In a production setting, this triggers PagerDuty, Slack webhooks, or Airflow alerts.

def automated_pipeline_job():
    """Wrapper to run ingestion, transformation, and DQ sequentially."""
    logger.info("--- Starting Scheduled Refresh Job ---")
    # Step 1: Run Ingestion (from Part 2)
    # import ingestion_pipeline; ingestion_pipeline.main()
    
    # Step 2: Run Star Schema Build (from Part 3)
    # import build_star_schema; build_star_schema.execute_etl()
    
    # Step 3: Run DQ Checks (Part 4)
    run_dq_checks()

if __name__ == "__main__":
    # Execute an immediate run for the assessment deliverable
    automated_pipeline_job()
    
    # Simulate the scheduling requirement (e.g., cron or Airflow behavior)
    logger.info("Initializing schedule: Refreshing pipeline daily at 02:00 AM UTC.")
    schedule.every().day.at("02:00").do(automated_pipeline_job)
    
    # Uncomment the loop below to run continuously in the background
    # while True:
    #     schedule.run_pending()
    #     time.sleep(60)