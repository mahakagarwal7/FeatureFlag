# Stage 1: Build the frontend
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend

# Copy frontend dependency files
COPY frontend/package*.json ./
RUN npm install

# Copy frontend source
COPY frontend/ ./

# Run build
RUN npm run build

# Stage 2: Build the backend and serve the frontend
FROM python:3.10-slim
WORKDIR /app

# Copy the backend requirements first
COPY feature-flag-agent-env/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the backend source
COPY feature-flag-agent-env/ ./

# Copy the frontend static build to the 'static' directory in backend
# The path in stage 1 was /app/frontend/out
COPY --from=frontend-builder /app/frontend/out ./static

# Expose port 7860 (default for Hugging Face Spaces)
EXPOSE 7860

# Command to run the FastAPI app
CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "7860"]
