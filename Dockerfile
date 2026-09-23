FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

RUN chmod +x /app/docker-entrypoint.sh
ENTRYPOINT [ "/app/docker-entrypoint.sh" ]

HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD wget --spider 0.0.0.0:8000 || exit 1

CMD ["gunicorn", "-c", "gunicorn.conf.py", "family_chore_app.wsgi:application"]