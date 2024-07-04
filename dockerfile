FROM python:3.11-alpine3.20

COPY requirements.txt .
COPY dist/trixellookupserver* ./dist/
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir --force-reinstall dist/*.whl

# Add different adapter requirements for compatibility
RUN apk update \
    && apk add --virtual build-deps gcc python3-dev musl-dev \
    && apk add --no-cache mariadb-dev libpq-dev
RUN pip install --no-cache-dir asyncmy aiomysql cryptography asyncpg
RUN apk del build-deps

EXPOSE 80

CMD ["uvicorn", "trixellookupserver:app", "--host", "0.0.0.0", "--port", "80"]