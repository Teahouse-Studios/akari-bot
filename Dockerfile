FROM python:3.10
WORKDIR ./akari-bot
ADD . .
RUN pip install -r requirements.txt
CMD ["python", "./bot.py"]
