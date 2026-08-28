import pandas as pd
import random
import uuid
from datetime import datetime, timedelta
from faker import Faker

# Initialize Faker and seed for reproducibility
fake = Faker()
Faker.seed(42)
random.seed(42)

# Configuration based on Part 1 Baseline (1+ Year Tier)
NUM_DAYS = 90
START_DATE = datetime.now() - timedelta(days=NUM_DAYS)
TIER_INVITE_LIMIT = 30
TIER_MESSAGE_LIMIT = 60
CAMPAIGNS = ["Recruiter_Outreach_Q3", "Data_Engineer_Hiring", "Executive_Search"]

events = []
lead_states = {}

def create_lead():
    """Generates a new mock target lead."""
    return {
        "lead_id": str(uuid.uuid4()),
        "campaign_id": random.choice(CAMPAIGNS),
        "state": "NEW"
    }

print("Initiating synthetic data generation engine...")

# Execute the daily chronological loop
for day_offset in range(NUM_DAYS):
    current_date = START_DATE + timedelta(days=day_offset)
    
    # 1. Generate Invites (Strictly capped at 30 per day)
    invites_today = random.randint(20, TIER_INVITE_LIMIT)
    for _ in range(invites_today):
        lead = create_lead()
        lead["state"] = "INVITED"
        lead_states[lead["lead_id"]] = lead
        
        events.append({
            "event_id": str(uuid.uuid4()),
            "event_timestamp": current_date + timedelta(hours=random.randint(8, 11), minutes=random.randint(0, 59)),
            "lead_id": lead["lead_id"],
            "campaign_id": lead["campaign_id"],
            "event_type": "INVITE_SENT"
        })
        
    # 2. Process Acceptances (Simulating a ~40% acceptance rate)
    invited_leads = [lead for lead in lead_states.values() if lead["state"] == "INVITED"]
    for lead in invited_leads:
        if random.random() < 0.40: 
            lead["state"] = "ACCEPTED"
            events.append({
                "event_id": str(uuid.uuid4()),
                "event_timestamp": current_date + timedelta(hours=random.randint(11, 13), minutes=random.randint(0, 59)),
                "lead_id": lead["lead_id"],
                "campaign_id": lead["campaign_id"],
                "event_type": "INVITE_ACCEPTED"
            })
            
    # 3. Generate Messages (Strictly capped at 60 per day, only to accepted leads)
    accepted_leads = [lead for lead in lead_states.values() if lead["state"] == "ACCEPTED"]
    messages_today = min(random.randint(30, TIER_MESSAGE_LIMIT), len(accepted_leads))
    
    if messages_today > 0:
        leads_to_message = random.sample(accepted_leads, messages_today)
        for lead in leads_to_message:
            lead["state"] = "MESSAGED"
            events.append({
                "event_id": str(uuid.uuid4()),
                "event_timestamp": current_date + timedelta(hours=random.randint(13, 16), minutes=random.randint(0, 59)),
                "lead_id": lead["lead_id"],
                "campaign_id": lead["campaign_id"],
                "event_type": "MESSAGE_SENT"
            })
            
    # 4. Process Replies and Ghosting (Simulating ~25% reply rate and ~15% ghosting)
    messaged_leads = [lead for lead in lead_states.values() if lead["state"] == "MESSAGED"]
    for lead in messaged_leads:
        outcome = random.random()
        if outcome < 0.25: 
            lead["state"] = "REPLIED"
            events.append({
                "event_id": str(uuid.uuid4()),
                "event_timestamp": current_date + timedelta(hours=random.randint(16, 20), minutes=random.randint(0, 59)),
                "lead_id": lead["lead_id"],
                "campaign_id": lead["campaign_id"],
                "event_type": "REPLY_RECEIVED"
            })
        elif outcome > 0.85: 
            lead["state"] = "GHOSTED"
            events.append({
                "event_id": str(uuid.uuid4()),
                "event_timestamp": current_date + timedelta(days=3), # Ghosting is historically lagging
                "lead_id": lead["lead_id"],
                "campaign_id": lead["campaign_id"],
                "event_type": "GHOSTED"
            })

# Inject Data Quality Anomalies (2% corruption for Part 4 testing)
print("Injecting deliberate anomalies into the dataset...")
for event in events:
    anomaly_chance = random.random()
    if anomaly_chance < 0.015:
        event["lead_id"] = None # Simulating a null ID drop
    elif anomaly_chance > 0.985:
        event["event_id"] = events[0]["event_id"] # Simulating a duplicated event

# Export the raw data
df = pd.DataFrame(events)
df = df.sort_values(by="event_timestamp")
output_file = "raw_linkedin_events.csv"
df.to_csv(output_file, index=False)

print(f"Success: Generated {len(df)} synthetic events and saved to '{output_file}'.")