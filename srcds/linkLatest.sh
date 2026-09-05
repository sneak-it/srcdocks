#!/bin/bash

REPO=${REPO:-/repo}
SRV=${SRV:-/srcds/srv}
OVERLAYS=${OVERLAYS:-/overlays}
OVERLAYS=${OVERLAYS%/}
LAYERS=${LAYERS:-/layers}
CUSTOM=${CUSTOM:-/custom}

# Set by loadLatestVersion, read by addOverlays to know which links are current
serverFiles=""

# When you mount something to, say, /srcds/srv/csgo/addons/sourcemod/logs, -mount prevents the files
# in the logs folder from being deleted as the bind-mound is a different "device" / filesystem
safeEmpty() {
	find "$1" -mount -type f,l -delete
}

APP_MAIN_FOLDER=$APP_NAME

if [[ $APP_NAME == "cs2cl" ]]
then
	APP_MAIN_FOLDER="game/csgo"
fi

# Seeds an overlay with what the game shipped so it adds to the server instead of replacing it.
# Returns non-zero when the overlay must be skipped, which beats leaving a server with no stock
# files at all and no explanation for the boot loop that follows.
mergeOverlay() {
	local overlay=$1 target=$2 keep

	if [[ ! -d $target ]]; then
		echo "  Nothing shipped at '$target', not seeding"
		return 0
	fi

	# Docker creates a missing bind source as root, but we run unprivileged
	if [[ ! -w $overlay ]]; then
		echo "  WARNING: '$overlay' is not writable by uid $(id -u), skipping this overlay"
		return 1
	fi

	# Purge by source rather than by brokenness: KEEPCOUNT leaves old versions on disk, so last
	# boot's links still resolve and the -n below would keep them pinned to a stale build.
	# Links to the version being loaded are kept so a server booting alongside this one never
	# has a map unlinked out from under it.
	keep=${serverFiles:-/nonexistent}
	if [[ $REPO == /?* ]]; then
		find "$overlay" -type l \
			\( -lname "$REPO/*" -o -lname "$LAYERS/*" -o -lname "$CUSTOM/*" \) \
			-not -lname "$keep*" -delete || true
	fi

	echo "  Seeding stock files into '$overlay'"
	cp -Prn "$target/." "$overlay/" || echo "  WARNING: seeding '$overlay' failed"
}

addOverlays() {
	echo "Adding overlays..."
	# Lord send help
	while IFS= read -r overlay; do
		# Overlaying the mod folder itself would rm -rf the whole server
		[[ ${overlay%/} == "$OVERLAYS" ]] && continue
		mountpoint -q "$overlay" || continue

		local target="$SRV/$APP_MAIN_FOLDER${overlay#"$OVERLAYS"}"

		echo "Mounting '$overlay' in place of '$target'"

		if [[ ${OVERLAY_MODE:-replace} == "merge" ]] && ! mergeOverlay "$overlay" "$target"; then
			continue
		fi

		mkdir -p "$target"
		rm -rf "$target"
		ln -s "$overlay" "$target"
	done < <(find "$OVERLAYS/" -mount -type d)
}

loadLatestVersion() {
	local latestVersion
	latestVersion=$(ls -td -- "$REPO/$APP_NAME"/v_*/ | head -n 1)

	serverFiles=$VERSION_PIN

	if [ -z "$latestVersion" ]
	then
		echo "No Serverfiles found. Looked for '$REPO/$APP_NAME/v_*'"
		exit 1
	fi

	if [[ $VERSION_PIN ]]; then
		serverFiles=$REPO/$APP_NAME/$serverFiles/
		echo "Using pinned Server files from '$serverFiles'..."
	else
		serverFiles=$latestVersion
		echo "No version specified, using(serverFiles) Server files from '$serverFiles'..."
	fi

	# Ensure we dont encounter a half-written version.
	# If the folder is newer than 6 seconds sleep a bit for good measure
	if [[ -n "$(find "$serverFiles" -mmin -0.1)" ]]; then
		sleep 3
	fi

	# Make sure to delete only symlinks, this way if e.g. the logs directory is bind-mounted
	# Files written to it will not be deleted as they're not symlinks but real files
	safeEmpty "$SRV/"
	cp -rsf "$serverFiles"* "$SRV/"

	if [[ $VERSION_PIN && $FAKELATEST ]]; then
		echo "Using steam.inf from '$latestVersion'..."
		cp -rsf "$latestVersion/$APP_MAIN_FOLDER/steam.inf" "$SRV/$APP_MAIN_FOLDER/"
	fi

	# The CS2 Release is a Dumpsterfire (This is temporary (Hopefully))
	# Update: Seeing how the CS2 "Server" is still the client... I lost hope of this being temporary
	if [[ $APP_NAME == "cs2cl" ]]; then
		ln -s "$SRV/game/csgo" "$SRV/cs2cl"
		mkdir -p ~/.steam/sdk64/
		ln -sf "$SRV/steamclient.so" ~/.steam/sdk64/
	fi

	# CS:GO bundles a libgcc_s that predates the distro libstdc++ linking against it
	if [[ $APP_NAME == "csgo" ]]; then
		rm -f "$SRV/bin/libgcc_s.so.1"
	fi

	# While we're here we might as well create these files to prevent unnecessary console messages
	ln -sf "$SRV/bin/steamclient.so" ~/.steam/sdk32/ 2> /dev/null || true
	(cd "$SRV/$APP_MAIN_FOLDER/" && touch cfg/default.cfg cfg/server.cfg)

	if [[ $NO_BSP_CVAR == "1" && $APP_NAME != "cs2cl" ]]; then
		rm -f "$SRV/$APP_MAIN_FOLDER/bspconvar_whitelist.txt"
	fi
}

loadCleanAddons() {
	safeEmpty "$SRV/$APP_NAME/addons/" 2> /dev/null

	cp -rsf "$REPO"/mm/* "$SRV/$APP_NAME/" || true

	if [[ $APP_NAME != "cs2cl" ]]; then
		cp -rsf "$REPO"/sm/* "$SRV/$APP_NAME/" || true

		if [[ $STOCK_SM_PLUGINS ]]; then
			local keepList
			keepList="\($(echo "$STOCK_SM_PLUGINS" | sed "s/,/\\\\|/g")\).smx"
			# Hack with -mount so that we dont delete stuff in a possibly mounted plugins folder
			# incase the user goofs. We only find / delete links anyways and not files but eh
			find "$SRV/$APP_NAME/addons/sourcemod" -mount -type l -path "*/plugins/*.smx" -not -regex ".*/$keepList$" -delete
		fi
	fi
}

# cp will not merge a directory into a symlinked one, so anything whose top-level name collides
# with an overlay gets dropped unless we descend into it explicitly
# ponytail: only the top level is handled, a collision nested deeper still fails
linkInto() {
	local src name dest=$SRV/$APP_MAIN_FOLDER

	for src in $1; do
		[ -e "$src" ] || continue
		name=${src##*/}

		if [ -d "$src" ]; then
			mkdir -p "$dest/$name"
			cp -rsf "$src/." "$dest/$name/"
		else
			cp -sf "$src" "$dest/"
		fi
	done
}

addCustomFiles() {
	echo "Adding custom layers..."
	linkInto "$LAYERS/*/*"

	echo "Adding custom files..."
	linkInto "$CUSTOM/*"
}

if [[ ${BASH_SOURCE[0]} == "$0" ]]; then
	cd "$SRV" || exit 1

	loadLatestVersion
	loadCleanAddons
	addOverlays
	addCustomFiles
fi
