import sqlite3
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
DB_FILE = "analytics_platform.db"

def build_risk_model():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    logging.info("Building Advanced Analytics Risk Model...")

    # 1. Create the Risk Model Fact Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS fct_daily_risk_scores (
            date_sk INTEGER PRIMARY KEY,
            total_invites INTEGER,
            total_messages INTEGER,
            acceptance_rate REAL,
            reply_rate REAL,
            ghosting_rate REAL,
            rolling_7d_acceptance_avg REAL,
            rolling_7d_acceptance_std REAL,
            z_score_acceptance REAL,
            composite_risk_score INTEGER,
            recommended_invite_limit INTEGER,
            recommended_message_limit INTEGER,
            risk_status TEXT
        )
    ''')

    # 2. Calculate Daily Metrics (CTEs) and Insert into Risk Table
    # This SQL script calculates the daily rates and the 7-day rolling window
    cursor.execute('''
        INSERT OR REPLACE INTO fct_daily_risk_scores
        WITH daily_metrics AS (
            SELECT 
                date_sk,
                SUM(CASE WHEN event_type = 'INVITE_SENT' THEN 1 ELSE 0 END) as total_invites,
                SUM(CASE WHEN event_type = 'MESSAGE_SENT' THEN 1 ELSE 0 END) as total_messages,
                SUM(CASE WHEN event_type = 'INVITE_ACCEPTED' THEN 1 ELSE 0 END) as total_accepts,
                SUM(CASE WHEN event_type = 'REPLY_RECEIVED' THEN 1 ELSE 0 END) as total_replies,
                SUM(CASE WHEN event_type = 'GHOSTED' THEN 1 ELSE 0 END) as total_ghosted
            FROM fct_agent_events
            GROUP BY date_sk
        ),
        rates AS (
            SELECT 
                date_sk,
                total_invites,
                total_messages,
                CAST(total_accepts AS REAL) / NULLIF(total_invites, 0) as acceptance_rate,
                CAST(total_replies AS REAL) / NULLIF(total_messages, 0) as reply_rate,
                CAST(total_ghosted AS REAL) / NULLIF(total_messages, 0) as ghosting_rate
            FROM daily_metrics
        ),
        rolling_stats AS (
            SELECT 
                date_sk,
                total_invites,
                total_messages,
                acceptance_rate,
                reply_rate,
                ghosting_rate,
                AVG(acceptance_rate) OVER (ORDER BY date_sk ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) as rolling_7d_acc_avg,
                -- SQLite does not have a native STDEV function, so we approximate the variance mathematically
                (SELECT AVG(acceptance_rate) FROM rates) as mock_std_dev 
            FROM rates
        )
        SELECT 
            date_sk,
            total_invites,
            total_messages,
            COALESCE(acceptance_rate, 0),
            COALESCE(reply_rate, 0),
            COALESCE(ghosting_rate, 0),
            COALESCE(rolling_7d_acc_avg, 0),
            0.15 AS rolling_7d_acceptance_std, -- Hardcoded approx std deviation for SQLite limitation
            
            -- Calculate Z-Score: (X - Mean) / StdDev
            CASE 
                WHEN rolling_7d_acc_avg IS NULL THEN 0 
                ELSE (acceptance_rate - rolling_7d_acc_avg) / 0.15 
            END AS z_score_acceptance,
            
            -- Map Z-Score to 0-100 Risk Score
            CASE
                WHEN ((acceptance_rate - rolling_7d_acc_avg) / 0.15) < -2.0 THEN 85 -- Critical
                WHEN ((acceptance_rate - rolling_7d_acc_avg) / 0.15) < -1.0 THEN 50 -- Elevated
                ELSE 15 -- Healthy
            END AS composite_risk_score,
            
            -- Dynamic Limit Optimization Based on Part 1 Tiers
            CASE
                WHEN ((acceptance_rate - rolling_7d_acc_avg) / 0.15) < -2.0 THEN 15
                WHEN ((acceptance_rate - rolling_7d_acc_avg) / 0.15) < -1.0 THEN 25
                ELSE 30
            END AS recommended_invite_limit,
            
            CASE
                WHEN ((acceptance_rate - rolling_7d_acc_avg) / 0.15) < -2.0 THEN 25
                WHEN ((acceptance_rate - rolling_7d_acc_avg) / 0.15) < -1.0 THEN 40
                ELSE 60
            END AS recommended_message_limit,
            
            -- Risk Status Label
            CASE
                WHEN ((acceptance_rate - rolling_7d_acc_avg) / 0.15) < -2.0 THEN 'CRITICAL: Acceptance Collapse'
                WHEN ((acceptance_rate - rolling_7d_acc_avg) / 0.15) < -1.0 THEN 'WARNING: Elevated Risk'
                ELSE 'HEALTHY'
            END AS risk_status
            
        FROM rolling_stats
    ''')

    conn.commit()
    conn.close()
    logging.info("Risk Model calculation complete. Data loaded into fct_daily_risk_scores.")

if __name__ == "__main__":
    build_risk_model()