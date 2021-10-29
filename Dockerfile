FROM python:3.7
COPY requirements.txt /tmp/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir LAMP-cortex
RUN pip install -r /tmp/requirements.txt
WORKDIR /app
COPY main.py /app
CMD ["python", "main.py"]