# 1. Use the official Playwright image for Python (v1.57.0)
# This is based on Ubuntu Jammy and includes all necessary browser dependencies.
FROM mcr.microsoft.com/playwright/python:v1.57.0-jammy

# 2. Set the working directory in the container
WORKDIR /app

# 3. Copy requirements first to leverage Docker layer caching
COPY requirements.txt .

# 4. Install Python dependencies
# We use --no-cache-dir to keep the image size smaller
RUN pip install --no-cache-dir -r requirements.txt

# 5. Install the Chromium browser specifically for v1.57.0
# The --with-deps flag ensures any missing system-level libraries are added.
RUN playwright install --with-deps chromium

# 6. Copy the rest of your application code
COPY . .

# 7. Expose the port FastAPI runs on (Railway uses 8080 by default)
EXPOSE 8080

# 8. Start the application using Uvicorn
# --host 0.0.0.0 is required for the container to be accessible externally.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
