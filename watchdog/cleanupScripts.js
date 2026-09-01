const fs = require("fs");

// Legacy CS:GO moved to its own AppID
const CSGO_LEGACY_APPID = "4465480";

const patchSteamInfAppId = (content) => content.replace(/^appID=730\b/m, `appID=${CSGO_LEGACY_APPID}`);

const setLegacyAppId = (path) => {
	if(process.env.CSGO_APPID_PATCH === "0")
		return console.log("CSGO_APPID_PATCH=0, leaving steam.inf appID as shipped");

	const file = `${path}/csgo/steam.inf`;
	const patched = patchSteamInfAppId(fs.readFileSync(file, "utf8"));

	if(!patched.includes(`appID=${CSGO_LEGACY_APPID}`))
		return console.warn("No appID=730 line in %s, leaving it as-is", file);

	// Version dirs are hardlinked to latest/, so replace the file instead of writing through it
	fs.unlinkSync(file);
	fs.writeFileSync(file, patched);
	console.log("Set steam.inf appID to %s", CSGO_LEGACY_APPID);
};

module.exports = {
	740: [
		// Delete Windows / 64bit files
		"rm -r steamapps srcds.exe chrome.pak",
		"find . -name '*.dll' -type f,l -delete",

		"find . -path '*linux64*' -type d -prune -exec rm -r '{}' \\;",

		// Client files obviously are only needed on the client
		"find . -name '*_client.so' -type f,l -delete",

		// Unnecessary platform files
		"find platform/* -maxdepth 0 -type d -prune -exec rm -r '{}' \\;",
		"find platform/* -not -name '*_dir.vpk' -type f,l -delete",
		// Delete platform paks entirely (Saves 1gb, shaders, prevents sv_pure on them)
		// "rm -r ./platform",

		// China / low violence Paks, no need
		`find csgo/* -name 'pakxv*.vpk' -type f,l -delete`,

		// Unnecessary configs
		`find csgo/cfg/ -not -name 'gamemode_*.cfg' -not -name 'valve.rc' -not -name 'cpu_level_2*' -not -name 'mem_level_2*' -type f,l -delete`,

		// - Panorama UI stuff, only needed on the client
		// - Resources are unused on the server, altho you could possibly add custom radars etc.
		// - Expressions is some L4D2 stuff lol
		`rm -r csgo/panorama csgo/resource csgo/expressions`,

		`find csgo/scenes/* -not -name 'scenes.image' -type f,l -delete`,

		// I think the soundcache isnt needed on the server either?
		`rm -r csgo/maps/soundcache`,

		// Defaultmap images are not needed on the server, neither are stories
		`find csgo/maps/* -name '*.jpg' -type f,l -delete`,
		`find csgo/maps/* -name '*.txt' -not -name '*_cameras.txt' -type f,l -delete`,

		// By defaults the models folder doesnt contain anything useful to the server as they're in paks
		`rm -rf csgo/models/*`,

		// These files arent really big but theres many of them
		"rm -rf bin/v8_winxp bin/prefabs bin/locales",
		`rm -rf csgo/scripts/hammer`,
		`rm -rf csgo/materials/panorama`,

		setLegacyAppId
	],
	730: [
		// THEY INCLUDE BUILDCHAIN STUFF IN THE RELEASE. 8000 FILES
		`rm -rf sniper_*`,
		`rm -rf pressure-vessel`,

		// Dont need low violence paks
		`rm -rf game/csgo_lv`,

		// Dont need Vulkan Shaders
		`rm -rf game/csgo/shaders_.vpk`,

		// Dont need tools.
		`rm -rf game/core/tools`,

		// - Panorama UI stuff, only needed on the client
		// - Resources are unused on the server, altho you could possibly add custom radars etc.
		`rm -r game/csgo/panorama game/csgo/resource`,

		// We are downloading the CS2 client, not server (Which doesnt exist because reasons (Yet ™)) so
		// to streamline things we restructure this client to look like a srcds server.......... kind of

		//`ln -s game/csgo/ cs2cl`,

		(path) => fs.writeFileSync(`${path}/srcds_run`,
`#!/bin/sh
# Yep, that's me. You're probably wondering how I got into this situation ...

# If the cs2 binary is symlinked instead of physically being in the right location,
# the server will resolve the files actual location and use that as its workdir,
# thus, its ran from the repo folder and all the custom content is ignored
# I sure hope this is not needed when we get server binaries
if [ -h game/bin/linuxsteamrt64/cs2 ]
then
	cp --remove-destination "$(readlink game/bin/linuxsteamrt64/cs2)" game/bin/linuxsteamrt64/cs2
fi

game/bin/linuxsteamrt64/cs2 -dedicated $@`),

		`chmod +x srcds_run`,

		// I dont even care at this point
		`cp /steamcmd/linux64/steamclient.so ./`
	]
};

if(require.main === module) {
	const assert = require("assert");

	// Version fields are sample values only; the point is that they come back byte-identical,
	// so whatever build Valve ships keeps its own versions.
	assert.strictEqual(
		patchSteamInfAppId("ClientVersion=1575\nappID=730\nPatchVersion=1.38.8.1\n"),
		"ClientVersion=1575\nappID=4465480\nPatchVersion=1.38.8.1\n"
	);
	// Only the standalone line, not a longer ID or an unrelated key
	assert.strictEqual(patchSteamInfAppId("appID=7300\n"), "appID=7300\n");
	assert.strictEqual(patchSteamInfAppId("ServerAppID=730\n"), "ServerAppID=730\n");
	// CRLF depots keep their line ending
	assert.strictEqual(patchSteamInfAppId("appID=730\r\n"), "appID=4465480\r\n");

	// Opting out returns before any filesystem access, so a bogus path cannot throw
	process.env.CSGO_APPID_PATCH = "0";
	assert.doesNotThrow(() => setLegacyAppId("/nonexistent"));
	delete process.env.CSGO_APPID_PATCH;
	assert.throws(() => setLegacyAppId("/nonexistent"), {code: "ENOENT"});

	console.log("cleanupScripts: ok");
}
