import os
import json
import time
import uuid
import sqlite3
import logging
import pandas as pd
from datetime import datetime

# Setup standard logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DB_FILE = "analytics_platform.db"
RAW_DATA_FILE = "raw_linkedin_events.csv"
PIPELINE_NAME = "linkedin_event_ingestion"

def send_alert(correlation_id, issue_type, details):
    """Mocks a webhook to PagerDuty or Slack for critical pipeline failures."""
    alert_payload = {
        "run_id": correlation_id,
        "alert_type": issue_type,
        "details": details,
        "timestamp": datetime.now().isoformat()
    }
    # In production, this would be: requests.post("webhook_url", json=alert_payload)
    print(f"\n[WEBHOOK FIRED] CRITICAL ALERT TRIGGERED: {json.dumps(alert_payload)}\n")


def setup_database(conn):
    """Creates tables if they don't exist yet."""
    cursor = conn.cursor()
    
    # Audit log for pipeline runs
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pipeline_runs (
            run_id TEXT PRIMARY KEY,
            pipeline TEXT,
            start_time TIMESTAMP,
            end_time TIMESTAMP,
            rows_read INTEGER DEFAULT 0,
            rows_inserted INTEGER DEFAULT 0,
            rows_rejected INTEGER DEFAULT 0,
            status TEXT,
            error_msg TEXT
        )
    ''')

    # Watermark for incremental loading
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS watermarks (
            pipeline TEXT PRIMARY KEY,
            last_watermark TIMESTAMP,
            updated_at TIMESTAMP
        )
    ''')

    # Dead Letter Queue (DLQ)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS dead_letter_queue (
            dlq_id TEXT PRIMARY KEY,
            run_id TEXT,
            payload TEXT,
            reason TEXT,
            created_at TIMESTAMP
        )
    ''')

    # Main staging table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stg_linkedin_events (
            event_id TEXT PRIMARY KEY,
            event_timestamp TIMESTAMP,
            lead_id TEXT,
            campaign_id TEXT,
            event_type TEXT,
            run_id TEXT,
            ingested_at TIMESTAMP
        )
    ''')
    conn.commit()

def get_watermark(conn):
    """Fetches the latest timestamp we successfully processed."""
    cursor = conn.cursor()
    cursor.execute("SELECT last_watermark FROM watermarks WHERE pipeline = ?", (PIPELINE_NAME,))
    row = cursor.fetchone()
    return row[0] if row else "1970-01-01 00:00:00"

def fetch_new_data(watermark):
    """Simulates hitting an API by reading the CSV incrementally."""
    token = os.getenv("POLLUXA_API_TOKEN")
    if not token:
        logger.warning("No API token found in environment. Using dev fallback.")
    
    for attempt in range(3):
        try:
            df = pd.read_csv(RAW_DATA_FILE)
            new_rows = df[df['event_timestamp'] > watermark]
            return new_rows.to_dict('records')
        except Exception as e:
            logger.warning(f"Fetch failed (attempt {attempt + 1}/3): {e}")
            time.sleep(2 ** attempt) 
            
    raise ConnectionError("Failed to fetch data after 3 attempts.")

def load_data(conn, records, run_id):
    """Validates and loads data idempotently."""
    cursor = conn.cursor()
    stats = {"inserted": 0, "rejected": 0, "max_ts": None}
    
    for row in records:
        if pd.isna(row.get('lead_id')) or not row.get('lead_id'):
            cursor.execute('''
                INSERT INTO dead_letter_queue (dlq_id, run_id, payload, reason, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (str(uuid.uuid4()), run_id, json.dumps(row), "Missing lead_id", datetime.now()))
            stats["rejected"] += 1
            continue
            
        try:
            cursor.execute('''
                INSERT INTO stg_linkedin_events 
                (event_id, event_timestamp, lead_id, campaign_id, event_type, run_id, ingested_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(event_id) DO NOTHING
            ''', (
                row['event_id'], row['event_timestamp'], row['lead_id'], 
                row['campaign_id'], row['event_type'], run_id, datetime.now()
            ))
            
            if cursor.rowcount > 0:
                stats["inserted"] += 1
                
            ts = row['event_timestamp']
            if not stats["max_ts"] or ts > stats["max_ts"]:
                stats["max_ts"] = ts
                
        except sqlite3.Error as e:
            logger.error(f"DB Error on row {row.get('event_id')}: {e}")
            
    conn.commit()
    return stats

def main():
    run_id = str(uuid.uuid4())
    start_time = datetime.now()
    logger.info(f"Starting pipeline run: {run_id}")
    
    conn = sqlite3.connect(DB_FILE)
    setup_database(conn)
    
    conn.execute('''
        INSERT INTO pipeline_runs (run_id, pipeline, start_time, status)
        VALUES (?, ?, ?, 'RUNNING')
    ''', (run_id, PIPELINE_NAME, start_time))
    conn.commit()
    
    try:
        watermark = get_watermark(conn)
        logger.info(f"Current watermark: {watermark}")
        
        records = fetch_new_data(watermark)
        rows_read = len(records)
        logger.info(f"Fetched {rows_read} new records.")
        
        if rows_read > 0:
            stats = load_data(conn, records, run_id)
            
            if stats["max_ts"]:
                conn.execute('''
                    INSERT INTO watermarks (pipeline, last_watermark, updated_at) 
                    VALUES (?, ?, ?)
                    ON CONFLICT(pipeline) DO UPDATE SET 
                        last_watermark=excluded.last_watermark, 
                        updated_at=excluded.updated_at
                ''', (PIPELINE_NAME, stats["max_ts"], datetime.now()))
                
            logger.info(f"Load complete. Inserted: {stats['inserted']}, DLQ: {stats['rejected']}")
        else:
            stats = {"inserted": 0, "rejected": 0}
            logger.info("No new data to load.")
            
        conn.execute('''
            UPDATE pipeline_runs 
            SET end_time = ?, rows_read = ?, rows_inserted = ?, rows_rejected = ?, status = 'SUCCESS'
            WHERE run_id = ?
        ''', (datetime.now(), rows_read, stats['inserted'], stats['rejected'], run_id))


        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "level": "INFO",
            "correlation_id": run_id,
            "message": "Pipeline completed successfully",
            "rows_processed": rows_read
        }
        print(f"\n[STRUCTURED LOG] {json.dumps(log_entry)}\n")
   
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        
        conn.execute('''
            UPDATE pipeline_runs 
            SET end_time = ?, status = 'FAILED', error_msg = ?
            WHERE run_id = ?
        ''', (datetime.now(), str(e), run_id))

        send_alert(run_id, "PIPELINE_CRASH", str(e))
        
    finally:
        conn.commit()
        conn.close()
        logger.info("Pipeline run finished.")

if __name__ == "__main__":
    main()