# Test runner image: Python + Chromium + all suites. Also runs the app for the docker-compose demo.
FROM mcr.microsoft.com/playwright/python:v1.47.0-jammy

WORKDIR /work
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
CMD ["pytest", "-m", "smoke"]
