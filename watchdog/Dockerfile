FROM node:26-trixie-slim AS node

RUN apt-get update \
		&& apt-get install -y --no-install-recommends binutils \
		&& strip /usr/local/bin/node

FROM debian:trixie-slim

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ENV SM_VERSION=1.11
ENV MM_VERSION=1.11
ENV STEAMCMD_LOGIN=anonymous
ENV APPS="cs2cl:730"
ENV KEEPCOUNT=3
ARG UID=1000

RUN apt-get update \
		&& apt-get install -y --no-install-recommends --no-install-suggests \
			ca-certificates \
			curl \
			lib32gcc-s1 \
			libatomic1 \
			libstdc++6 \
			rsync \
		&& apt-get clean autoclean \
		&& apt-get autoremove -y \
		&& rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Only the node binary; npm is never pulled into the final image
COPY --from=node /usr/local/bin/node /usr/local/bin/node

RUN useradd -lm -u $UID srcds

WORKDIR /steamcmd

RUN curl -sqL "https://steamcdn-a.akamaihd.net/client/installer/steamcmd_linux.tar.gz" | tar zxf - \
		&& chown -R srcds /steamcmd

VOLUME ["/repo"]

WORKDIR /watchdog

COPY --chown=srcds ./watchdog/*.js ./

USER srcds

ENTRYPOINT ["node", "/watchdog/main.js"]
