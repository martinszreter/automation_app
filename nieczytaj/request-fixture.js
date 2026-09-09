'use strict';
// Exercise the actual HTTP request handler without opening ports or fetching feeds.
module.exports = function requestFixture(server, host, path) {
  return new Promise(resolve => {
    let status = 200, headers = {};
    server.emit('request', { method: 'GET', url: path, headers: { host } }, {
      writeHead(code, values = {}) { status = code; headers = values; },
      end(body = '') { resolve({ status, location: headers.location || '', body: String(body) }); },
    });
  });
};
