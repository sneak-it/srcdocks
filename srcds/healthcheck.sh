#!/bin/bash

port=${HEALTH_PORT-${PORT-27015}}

# A wildcard bind address is not a destination: it resolves to loopback, where srcds ignores queries
ip=${HEALTH_IP-$IP}
if [[ -z $ip || $ip == "0.0.0.0" || $ip == "::" ]]
then
	ip=$(hostname)
fi

# Replies are handled as hex text because bash cannot hold the nullbytes in them
query() {
	local bytes
	bytes=($(printf '%b' "\xff\xff\xff\xffTSource Engine Query\0$1" | nc -u -w 1 "$ip" "$port" | od -An -tx1))
	echo "${bytes[*]}"
}

unhex() {
	printf '\\x%s' "$@"
}

reply=$(query)

# Any query may be answered with a challenge ('A', 0x41), which has to be echoed back verbatim
# https://developer.valvesoftware.com/wiki/Server_queries#Challenge_Mechanism
if [[ $reply == "ff ff ff ff 41 "* ]]
then
	challenge=($reply)
	reply=$(query "$(unhex "${challenge[@]:5:4}")")
fi

# Some older titles precede the reply with a GoldSource one, so find the Source header ('I', 0x49) anywhere
info=${reply#*ff ff ff ff 49 }

if [[ $info == "$reply" ]]
then
	exit 1
fi

# Drop the protocol byte, leaving the server name onwards for the docker health log
printf '%b' "$(unhex ${info#* })" | tr '\0' ' '
