FROM python:3.12-slim
WORKDIR /srv
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

# docker compose build --build-arg ENABLE_OCR=true   (adds tesseract for scanned PDFs; set OCR_ENABLED=true at runtime)
ARG ENABLE_OCR=false
RUN if [ "$ENABLE_OCR" = "true" ]; then \
      apt-get update && apt-get install -y --no-install-recommends tesseract-ocr && rm -rf /var/lib/apt/lists/*; \
    fi

COPY requirements.txt requirements-ocr.txt ./
RUN pip install --no-cache-dir -r requirements.txt && \
    if [ "$ENABLE_OCR" = "true" ]; then pip install --no-cache-dir -r requirements-ocr.txt; fi

COPY app ./app
RUN useradd -r -u 10001 appuser && mkdir -p /data && chown appuser /data
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --retries=5 CMD python -c "import urllib.request as u; u.urlopen('http://localhost:8000/health')" || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
