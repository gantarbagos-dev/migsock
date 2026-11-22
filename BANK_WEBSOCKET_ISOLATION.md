# BANK WebSocket Isolation Patch

## Changes
- Added explicit upstream socket roles (`troop` / `bank`) in the backend registry.
- The BANK browser socket announces its role before developer login; the proxy consumes this local control frame and does not forward it upstream.
- KickAll socket selection and own-session username filtering now use troop sockets only.
- Troop reset closes and removes troop sockets only, preserving the BANK socket registry.
- Added a local `proxy.logout` control frame. The proxy consumes it, cancels the relay, unregisters the BANK socket, and closes the upstream connection instead of retaining it as a detached session.
- BANK logout stops its ping timer, invalidates its generation, clears its balance, and independently refreshes troop balances as before.

## Validation
- `python -m py_compile app.py`: passed.
- Inline JavaScript syntax check (`node --check`): passed for both inline scripts.
- Backend role-isolation smoke test: passed; KickAll socket selection excludes BANK and troop unregister leaves BANK role intact.

## Notes
This isolates BANK from KickAll dispatch and troop reset at the application socket-selection layer. Both still share the same Python process/event loop and network resources, so severe process-wide CPU or network saturation can still add latency. No upstream protocol, credentials, or server authorization limits were changed.
