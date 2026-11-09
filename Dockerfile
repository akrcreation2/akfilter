FROM python:3.11-slim

RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y git && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt /requirements.txt
RUN pip3 install --no-cache-dir -U pip && \
    pip3 install --no-cache-dir -U -r /requirements.txt

RUN mkdir /shobanafilterbot
WORKDIR /shobanafilterbot
COPY . /shobanafilterbot

EXPOSE 8080

CMD ["python3", "bot.py"]
