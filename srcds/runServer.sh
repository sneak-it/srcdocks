#!/bin/bash

# AUTOUPDATE=1 (default): includes -autoupdate flag for auto-restart
# AUTOUPDATE=0: excludes -autoupdate flag
AUTOUPDATE="${AUTOUPDATE:-1}"
if [[ "$AUTOUPDATE" != "0" && "$AUTOUPDATE" != "1" ]]; then
	echo "Warning: AUTOUPDATE must be '0' or '1'. Defaulting to '1'."
	AUTOUPDATE="1"
fi
AUTOP_FLAG=""
if [[ "$AUTOUPDATE" == "1" ]]; then
	AUTOP_FLAG="-autoupdate"
fi

runServerCustom() {
	export LD_LIBRARY_PATH="/srcds/srv:/srcds/srv/bin"
	./${SRCDS_BIN-srcds_linux} -game $APP_NAME $SRCDS_ARGS -strictportbind -port ${PORT-27015} -ip ${IP-0.0.0.0} $AUTOP_FLAG -nobreakpad
}

runServer() {
	# The order is IMPORTANT. -autoupdate enables auto-restart,
	# but -norestart removes it again, keeping autoupdate active but using my autorestart instead
	/bin/bash srcds_run $SRCDS_ARGS -strictportbind -port ${PORT-27015} -ip ${IP-0.0.0.0} $AUTOP_FLAG -norestart -nobreakpad
}

cd /srcds/srv

if [[ $SRCDS_RUN == "1" || $APP_NAME == "cs2cl" ]]
then
	runServer
else
	runServerCustom
fi