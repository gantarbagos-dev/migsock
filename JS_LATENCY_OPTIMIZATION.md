# JavaScript latency optimization

## Scope

Only the active JavaScript in `public/index.html` was changed. The scripts in `public/admin.html` and `public/login.html` were regression-checked and left unchanged. `check.js` and `extracted.js` are not referenced by the HTML pages or Python server, so they were left unchanged as dormant/source-extraction artifacts rather than changing code that is not part of the active browser path.

## Changes

1. Added a normalized-key `Map` index from target username to its DOM row.
2. Target count and remaining target capacity now use the existing authoritative `appState.targets` map instead of querying the DOM.
3. Backend auto-config sync and KICK ALL target collection now read the same in-memory target state instead of scanning and mapping all `.target-item` nodes.
4. Confirmed target removal now removes its indexed row directly instead of scanning every target row.
5. All three existing target-list reset paths clear both the target state and the row index.

## Preserved behavior and contracts

- No change to the 500 ms auto-config watcher cadence or its 5-second unchanged-payload refresh rule.
- No change to target limit (10), loop limit, socket/target delay values, or kick limits.
- No change to KICK ALL handlers, endpoint names, request payload fields, WebSocket message format, countdown logic, retry behavior, or server authorization.
- No changes to Python backend files, authentication, UI markup, or CSS.

## Regression checks

- Node.js syntax check passed for `check.js`, `extracted.js`, and all four inline JavaScript blocks across the three HTML pages.
- Python compile check passed for `app.py` and `auth.py` (regression guard; these files were not edited).
- Static state-consistency checks passed: target additions index their rows; confirmed removals remove the indexed row; all three clear paths reset the index; count/capacity/config/KICK ALL use the same target state.
- Static contract checks passed: 500 ms watcher retained; kick loop/stop endpoints and WebSocket kick markers retained.
- ZIP integrity check passed after packaging.

No browser-driven end-to-end test or live-server latency benchmark was available in this environment. Therefore no numerical latency improvement is claimed; the optimization removes repeated DOM traversal and allocation from the recurring sync path.
