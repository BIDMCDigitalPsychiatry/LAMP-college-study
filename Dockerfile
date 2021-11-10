FROM python:3.9
COPY requirements.txt /tmp/
RUN pip install git+https://github.com/BIDMCDigitalPsychiatry/LAMP-cortex.git
RUN pip install -r /tmp/requirements.txt
WORKDIR /app
COPY main.py /app
COPY module_scheduler.py /app
CMD ["python", "-u", "main.py"]