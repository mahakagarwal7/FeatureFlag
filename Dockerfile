# Stage 1: Build the frontend
FROM node:20-slim AS frontend-builder
WORKDIR /frontend

# Copy frontend dependency files
COPY frontend/package*.json ./
RUN npm install

# Copy frontend source and build it
COPY frontend/ ./
RUN npm run build

# Stage 2: Build the backend and serve the frontend
FROM python:3.10-slim
WORKDIR /app

# Copy the backend requirements first for better caching
COPY feature-flag-agent-env/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the backend source tree
COPY feature-flag-agent-env/ ./

# Copy the frontend static build to the 'static' directory in backend
# The FastAPI server is configured to serve files from this directory
COPY --from=frontend-builder /frontend/out ./static

# Expose port 7860 (default for Hugging Face Spaces)
EXPOSE 7860

# Command to run the FastAPI app using uvicorn on port 7860
# We use the 'server.app:app' entry point which correctly discovers the FastAPI instance
CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "7860"]
