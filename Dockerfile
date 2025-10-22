FROM python:3.13

LABEL org.opencontainers.image.url=https://github.com/Teahouse-Studios/akari-bot
LABEL org.opencontainers.image.documentation=https://bot.teahouse.team/
LABEL org.opencontainers.image.source=https://github.com/Teahouse-Studios/akari-bot
LABEL org.opencontainers.image.vendor="Teahouse Studios"
LABEL org.opencontainers.image.licenses=AGPL-3.0-or-later
LABEL org.opencontainers.image.title="AkariBot"
LABEL maintainer="Teahouse Studios <admin@teahou.se>"
ARG VERSION
LABEL version=$VERSION

WORKDIR /akari-bot
ADD . .

RUN apt-get update && apt-get install -y \
    fonts-noto-cjk \
    fonts-noto-color-emoji \
    fonts-dejavu \
    && rm -rf /var/lib/apt/lists/*

RUN pip install -r requirements.txt --no-deps
CMD ["python", "./bot.py"]
