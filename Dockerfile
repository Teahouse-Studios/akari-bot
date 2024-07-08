FROM python:3.12

LABEL org.opencontainers.image.url https://github.com/Teahouse-Studios/akari-bot
LABEL org.opencontainers.image.documentation https://bot.teahouse.team/
LABEL org.opencontainers.image.source https://github.com/Teahouse-Studios/akari-bot
LABEL org.opencontainers.image.vendor Teahouse Studios
LABEL org.opencontainers.image.licenses AGPL-3.0-or-later
LABEL org.opencontainers.image.title Akari Bot
MAINTAINER Teahouse Studios <admin@teahou.se>

WORKDIR /akari-bot
ADD . .

RUN pip install -r requirements.txt --no-deps
CMD ["python", "./bot.py"]
