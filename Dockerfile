# Test runner image: Python + Chromium + all suites. Also runs the app for the docker-compose demo.
# The browser is installed by the same Playwright version that pip resolves, so the two can
# never drift apart (a pinned Playwright base image with an unpinned pip package did).
FROM python:3.12-slim

WORKDIR /work
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
 && python -m playwright install --with-deps chromium

COPY . .
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
CMD ["pytest", "-m", "smoke"]
