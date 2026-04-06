FROM python:3.10-slim

WORKDIR /app

# Hugging Face Spaces requires the Dockerfile at the root of the repository
COPY feature-flag-agent-env/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the actual application files and set ownership to user 1000
COPY --chown=1000:1000 feature-flag-agent-env/ .

# Give the container permission to write inside /app (for logs and databases)
RUN mkdir -p logs/audit && chmod -R 777 /app

# Hugging Face explicitly expects apps to listen on port 7860
EXPOSE 7860

# Hugging Face runs containers securely using user 1000
USER 1000

# Start the uvicorn server
CMD ["uvicorn", "feature_flag_env.server.app:app", "--host", "0.0.0.0", "--port", "7860"]
