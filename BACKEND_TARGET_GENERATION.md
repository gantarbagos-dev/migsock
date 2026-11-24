# Backend Target Generation

## Changes
- Moved Auto Target v2 candidate grouping and ranking from `public/index.html` into `app.py`.
- Backend now captures room participant snapshots directly from upstream `room.participants.result` / `room.participants` messages.
- Added authenticated `POST /api/target-generate`; the browser sends only the room and exclusion/current-selection state, not the participant list.
- Frontend remains responsible only for displaying the returned target names and preserving manual target selection.
- Existing KICK ALL dispatch, loop, delay, rate-limit, BANK isolation, and upstream protocol were not changed.
- Troop reset clears backend-cached participant snapshots. Normal connection close removes that socket's snapshot; detached upstream connections retain their snapshot while the backend still owns the connection.

## Validation
- `app.py` compiles with `py_compile`.
- Both inline JavaScript blocks pass `node --check`.
- Backend target-generation checks cover numeric, multi-segment numeric, alphabetic suffix, alphabetic token, own-socket exclusion, kicked-target exclusion, existing-target capacity, and participant extraction.
- Live upstream integration was not available in this environment; deploy and verify using a real room participant listing before relying on generated targets.
