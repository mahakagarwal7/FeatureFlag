FROM python:3.10-slim

WORKDIR /app

# Hugging Face Spaces requires the Dockerfile at the root of the repository
# So we copy the requirements from the subdirectory
COPY feature-flag-agent-env/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the actual application files
COPY feature-flag-agent-env/ .

# Hugging Face explicitly expects apps to listen on port 7860
EXPOSE 7860

# Hugging Face runs containers securely using user 1000
USER 1000

# Start the uvicorn server on port 7860
CMD ["uvicorn", "feature_flag_env.server.app:app", "--host", "0.0.0.0", "--port", "7860"]
