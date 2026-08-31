# Current work

Implement the customer-surface rebuild using **`PLAN.md`** as the live status board (mark work items done as you go). Design detail: **`docs/ROTI_CONNECT_WIREFRAME_PLAN.md`**. That plan wins over the wireframe extract on auth and order numbers.

Readable UI spec: `docs/_wireframe_spec_extract.md`. Behaviour: `docs/SPEC_v1.1.md` + `docs/DECISIONS.md`. Agent conventions: `AGENTS.md`.

Do not rewrite capacity, transitions, or staff `/manage`. Do not invent a second status machine or `RC-` order numbers. **v1 Account is password login, not OTP — do not render Send code.**
