# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file from the project subdirectory
COPY feature-flag-agent-env/requirements.txt ./requirements.txt

# Install dependencies securely
RUN pip install --no-cache-dir -r requirements.txt

# Copy the project source tree into the container
COPY feature-flag-agent-env/ ./

# Expose port 7860 as expected by Hugging Face Spaces
EXPOSE 7860

# Command to run the FastAPI app using uvicorn on port 7860
CMD ["uvicorn", "feature_flag_env.server.app:app", "--host", "0.0.0.0", "--port", "7860"]
