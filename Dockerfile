# Use an official, lightweight Python runtime
FROM python:3.9-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all your pipeline scripts, mock data, and database into the container
COPY ingestion_pipeline.py .
COPY build_star_schema.py .
COPY anomaly_risk_model.py .
COPY raw_linkedin_events.csv .
COPY analytics_platform.db .

# Create a master orchestrator script on the fly
RUN echo 'import os\n\
os.system("python ingestion_pipeline.py")\n\
os.system("python build_star_schema.py")\n\
os.system("python anomaly_risk_model.py")\n\
print("Pipeline Execution Complete!")' > run_all.py

# Set environment variables for security (Simulated)
ENV POLLUXA_API_TOKEN="secure-mock-token-123"
ENV ENVIRONMENT="PRODUCTION"

# Run the master orchestrator when the container launches
CMD ["python", "run_all.py"]