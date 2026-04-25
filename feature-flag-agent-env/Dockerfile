# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Make logs more readable in containerized environments.
ENV PYTHONUNBUFFERED=1 \
	PYTHONDONTWRITEBYTECODE=1

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install dependencies securely without saving the cache to save space
RUN python -m pip install --upgrade pip && \
	pip install --no-cache-dir -r requirements.txt

# Copy the rest of the project files into the container
COPY . .

# Expose the Hugging Face / OpenEnv port
EXPOSE 7860

# Command to run the FastAPI app using uvicorn
CMD ["uvicorn", "feature_flag_env.server.app:app", "--host", "0.0.0.0", "--port", "7860"]
