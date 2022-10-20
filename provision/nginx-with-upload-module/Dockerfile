FROM debian:stretch

RUN apt-get update
RUN apt-get install -y \
    build-essential \
    curl \
    libgd-dev \
    libgeoip-dev \
    git \
    libxslt1-dev \
    libssl-dev \
    libpcre3-dev \
    libperl-dev \
    zlib1g-dev

COPY install.sh /

RUN sh -x /install.sh
