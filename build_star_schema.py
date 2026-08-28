import sqlite3
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

DB_FILE = "analytics_platform.db"

def execute_etl():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    logging.info("Building Star Schema DDL (Data Definition Language)...")

    # ==========================================
    # 1. DDL: Create Dimension Tables
    # ==========================================
    
    # Date Dimension
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS dim_date (
            date_sk INTEGER PRIMARY KEY,
            full_date DATE,
            year INTEGER,
            month INTEGER,
            day INTEGER,
            day_of_week TEXT
        )
    ''')

    # Agent Dimension (Capturing the risk configuration limits)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS dim_agent (
            agent_sk INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_name TEXT,
            account_age_tier TEXT,
            daily_invite_limit INTEGER,
            daily_message_limit INTEGER
        )
    ''')

    # Campaign Dimension
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS dim_campaign (
            campaign_sk INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id TEXT UNIQUE,
            campaign_name TEXT,
            status TEXT DEFAULT 'ACTIVE'
        )
    ''')

    # Lead Dimension (SCD Type 2 structure)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS dim_lead (
            lead_sk INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id TEXT,
            target_segment TEXT DEFAULT 'Unknown',
            valid_from TIMESTAMP,
            valid_to TIMESTAMP,
            is_current BOOLEAN,
            UNIQUE(lead_id, valid_from)
        )
    ''')

    # ==========================================
    # 2. DDL: Create Fact Table
    # ==========================================
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS fct_agent_events (
            event_sk INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT UNIQUE,
            date_sk INTEGER,
            lead_sk INTEGER,
            campaign_sk INTEGER,
            agent_sk INTEGER,
            event_type TEXT,
            event_timestamp TIMESTAMP,
            FOREIGN KEY (date_sk) REFERENCES dim_date(date_sk),
            FOREIGN KEY (lead_sk) REFERENCES dim_lead(lead_sk),
            FOREIGN KEY (campaign_sk) REFERENCES dim_campaign(campaign_sk),
            FOREIGN KEY (agent_sk) REFERENCES dim_agent(agent_sk)
        )
    ''')

    logging.info("Executing DML (Data Manipulation Language) to transform and load data...")

    # ==========================================
    # 3. DML: Transform and Load Dimensions
    # ==========================================

    # Load Agent Dimension (Mocking your declared Step 6 configuration)
    cursor.execute('''
        INSERT OR IGNORE INTO dim_agent (agent_sk, agent_name, account_age_tier, daily_invite_limit, daily_message_limit)
        VALUES (1, 'Primary_Agent', '1+ Year', 30, 60)
    ''')

    # Load Campaign Dimension from Staging
    cursor.execute('''
        INSERT OR IGNORE INTO dim_campaign (campaign_id, campaign_name)
        SELECT DISTINCT campaign_id, campaign_id 
        FROM stg_linkedin_events
        WHERE campaign_id IS NOT NULL
    ''')

    # Load Lead Dimension (Initializing SCD Type 2 logic)
    # If a lead_id doesn't exist, insert it as the current active record.
    cursor.execute('''
        INSERT OR IGNORE INTO dim_lead (lead_id, valid_from, valid_to, is_current)
        SELECT DISTINCT 
            lead_id, 
            MIN(event_timestamp) as valid_from, 
            '9999-12-31 23:59:59' as valid_to, 
            1 as is_current
        FROM stg_linkedin_events
        WHERE lead_id IS NOT NULL
        GROUP BY lead_id
    ''')

    # Load Date Dimension (Dynamically parsing timestamps from staging)
    cursor.execute('''
        INSERT OR IGNORE INTO dim_date (date_sk, full_date, year, month, day)
        SELECT DISTINCT 
            CAST(strftime('%Y%m%d', event_timestamp) AS INTEGER) as date_sk,
            date(event_timestamp) as full_date,
            CAST(strftime('%Y', event_timestamp) AS INTEGER) as year,
            CAST(strftime('%m', event_timestamp) AS INTEGER) as month,
            CAST(strftime('%d', event_timestamp) AS INTEGER) as day
        FROM stg_linkedin_events
    ''')

    # ==========================================
    # 4. DML: Transform and Load Fact Table
    # ==========================================
    
    # Join staging data with dimensions to swap Natural Keys for Surrogate Keys
    cursor.execute('''
        INSERT OR IGNORE INTO fct_agent_events 
        (event_id, date_sk, lead_sk, campaign_sk, agent_sk, event_type, event_timestamp)
        SELECT 
            stg.event_id,
            CAST(strftime('%Y%m%d', stg.event_timestamp) AS INTEGER) AS date_sk,
            dl.lead_sk,
            dc.campaign_sk,
            1 AS agent_sk,  -- Defaulted to our single mock agent
            stg.event_type,
            stg.event_timestamp
        FROM stg_linkedin_events stg
        LEFT JOIN dim_lead dl 
            ON stg.lead_id = dl.lead_id AND dl.is_current = 1
        LEFT JOIN dim_campaign dc 
            ON stg.campaign_id = dc.campaign_id
    ''')

    conn.commit()
    
    # Print a quick summary of the loaded facts
    cursor.execute("SELECT COUNT(*) FROM fct_agent_events")
    fact_count = cursor.fetchone()[0]
    
    conn.close()
    logging.info(f"ETL complete. Successfully loaded {fact_count} events into the Star Schema fact table.")

if __name__ == "__main__":
    execute_etl()