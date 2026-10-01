# Home Assistant Integration for 1KOMMA5GRAD

## Work in Progress

This integration is still in development and not yet ready for production use.

Feel free to contribute to this project, raise issues or submit pull
requests to improve and help finishing the integration.

## Good to know

The 1KOMMA5GRAD API is not officially documented and may change at any time.
Use mitmproxy or similar tools to intercept the API calls from the official app
to get an idea of the API structure.

What has been observed so far is collected in
[docs/heartbeat-openapi.json](docs/heartbeat-openapi.json). To add a new mitmproxy
dump to it (`pip install brotli` first, the app's responses are often brotli compressed):

```bash
python tools/heartbeat_openapi.py path/to/flows
```

Only Heartbeat API calls are used and no captured values are written; the run aborts
if any would end up in the file. New endpoints are added and seen ones updated, while
endpoints missing from the dump are kept (see their `x-last-seen` date). Flow dumps
contain your password and tokens, so never commit them.

## Current state

- [x] Login
- [x] Sensor for current electricity price
- [x] Sensor for current electricity consumption and production
- [x] Read and manage of electric vehicle charging stations
- [ ] Read and manage of heat pumps

## Known issues

- Currently only EUR currency is supported, the API does not provide the currency for the customer
- Currently the time zone is hardcoded to Europe/Berlin, the API does not provide the time zone for the customer

### Development Setup

Documented for macOS, but should be similar for other operating systems.

```bash
brew install python3 autoconf ffmpeg cmake make

pip install -r requirements.txt
```