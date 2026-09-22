// Upstream edges (Steam, AlliedModders) answer with HTML error pages. Without these guards a 404
// becomes a version string and then a download URL, and an HTML body reaches JSON.parse as a bare
// "Unexpected token '<'" with no hint of which request produced it.

const TIMEOUT_MS = 20000;

const snippet = (body) => JSON.stringify(body.slice(0, 200));

async function getText(url, timeoutMs = TIMEOUT_MS) {
	const res = await fetch(url, {signal: AbortSignal.timeout(timeoutMs)});
	// Read the body first so failures can quote what actually came back
	const body = await res.text();

	if(!res.ok)
		throw new Error(`HTTP ${res.status} for ${url}: ${snippet(body)}`);

	return body.trim();
}

async function getJson(url, timeoutMs) {
	const body = await getText(url, timeoutMs);

	try {
		return JSON.parse(body);
	} catch {
		throw new Error(`Non-JSON response from ${url}: ${snippet(body)}`);
	}
}

module.exports = {getText, getJson};

if(require.main === module) {
	const assert = require("assert");
	const http = require("http");

	const servers = [];

	const serve = (handler) => new Promise((ready) => {
		const server = http.createServer(handler);

		servers.push(server);
		server.listen(0, "127.0.0.1", () => ready(`http://127.0.0.1:${server.address().port}/`));
	});

	(async() => {
		// The reported failure: an HTML error page must name its status and body, not a parse error
		await assert.rejects(getJson(await serve((req, res) => {
			res.writeHead(503, {"content-type": "text/html"});
			res.end("<html>\n<head><title>503 Service Unavailable</title></head>\n</html>");
		})), /HTTP 503 .*<html>/s);

		// HTML served with a 200 still must not surface as a bare JSON.parse error
		await assert.rejects(getJson(await serve((req, res) => res.end("<html></html>"))),
			/Non-JSON response .*<html>/s);

		// Surrounding whitespace is trimmed, so a body never becomes a dirty version string
		assert.strictEqual(
			await getText(await serve((req, res) => res.end("  sourcemod-1.12.0-git7210-linux.tar.gz\n"))),
			"sourcemod-1.12.0-git7210-linux.tar.gz");

		assert.strictEqual(
			(await getJson(await serve((req, res) => res.end('{"response":{"required_version":14181}}')))).response.required_version,
			14181);

		// A server that never answers aborts instead of hanging until undici's default
		await assert.rejects(getText(await serve(() => {}), 100), {name: "TimeoutError"});

		for(const server of servers) {
			server.closeAllConnections();
			server.close();
		}

		console.log("httpGet: ok");
	})();
}
