FROM python:3.11-alpine3.20

COPY requirements.txt .
COPY dist/trixellookupserver* ./dist/
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir --force-reinstall dist/*.whl

EXPOSE 80

CMD ["uvicorn", "trixellookupserver:app", "--host", "0.0.0.0", "--port", "80"]