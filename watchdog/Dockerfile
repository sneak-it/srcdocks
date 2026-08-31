FROM node:26-trixie-slim AS node

RUN dpkg --add-architecture i386 \
		&& apt-get update \
    && apt-get install -y --no-install-recommends --no-install-suggests \
        ca-certificates \
				curl



FROM node AS node-modules

WORKDIR /INSTALL
COPY ./watchdog/*.* ./
RUN npm install --omit=dev



FROM node

ENV SM_VERSION=1.11
ENV MM_VERSION=1.11
ENV STEAMCMD_LOGIN=anonymous
ARG UID=1000

ENV APPS="cs2cl:730"
ENV KEEPCOUNT=3

RUN userdel -r node \
		&& useradd -m -u $UID srcds
RUN apt-get install -y --no-install-recommends --no-install-suggests \
			lib32gcc-s1 \
			rsync

RUN apt-get clean autoclean \
		&& apt-get autoremove -y \
		&& rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

WORKDIR /steamcmd

RUN curl -sqL "https://steamcdn-a.akamaihd.net/client/installer/steamcmd_linux.tar.gz" | tar zxvf -
# We could prepare steamcmd, but that adds like 250 mb of stuff that will probably be re-downloaded anyways
#RUN ./steamcmd.sh +quit

# All downloaded servers will be stored here
VOLUME ["/repo"]

# Install / Config watchdog
WORKDIR /watchdog

COPY ./watchdog/*.js ./
COPY --from=node-modules /INSTALL/node_modules/ ./node_modules/

RUN chown -R srcds ./ /steamcmd

USER srcds

# Cleanup
# RUN apt-get remove --purge -y apt-transport-https lsb-release gnupg \
# 		&& apt-get clean autoclean \
# 		&& apt-get autoremove -y \
# 		&& rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

ENTRYPOINT ["node", "/watchdog/main.js"]
