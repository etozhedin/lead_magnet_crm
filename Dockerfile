FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY . .
RUN DEBUG=1 DB_ENGINE=sqlite python manage.py collectstatic --noinput
RUN useradd --create-home app && chown -R app:app /app
USER app
EXPOSE 8017
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8017", "--workers", "2", "--access-logfile", "-"]
