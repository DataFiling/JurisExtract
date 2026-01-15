FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Note: No need to run 'playwright install' because the image has it!
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
