# Security

AgroTrustChain is an **academic prototype** that accompanies a research paper. It is meant to run
on a single machine for demonstration and study. It is **not hardened for production** or for
exposure to the internet. The Docker setup binds every port to `127.0.0.1` for this reason.

## Reporting a Vulnerability

Please report security issues privately rather than in a public issue: use **Report a
vulnerability** under this repository's *Security* tab on GitHub, or contact the maintainers
through their GitHub profiles. Include steps to reproduce and the affected file or route.

## Known Limitations

These remain by design or are not yet addressed. Keep them in mind before deploying the app
anywhere shared.

| Area | Limitation | Mitigation today |
| --- | --- | --- |
| Default credentials | The seed database has the login `1@1.com` / `1`. Docker defaults the SQL Server `sa` password to a value published in this repository. | Ports are bound to localhost. Change both before sharing a deployment: set `MSSQL_SA_PASSWORD` in `.env` before the first start. |
| Session key | Without `FLASK_SECRET_KEY`, a random key is generated at each start. | Set `FLASK_SECRET_KEY` for any long-running deployment. |
| Database privileges | The app connects as `sa` under Docker. | Use a least-privilege SQL login for anything beyond local use. |
| Ethereum account | Transactions and chain anchors are sent from Ganache's unlocked `accounts[0]`, which owns the contract. | Acceptable only on a private development chain. A real network needs proper key management. |
| Hash chain | Someone who controls both the database *and* the contract owner's Ethereum account can rewrite the chain and re-anchor it. | Edits, deletions, re-ordering and full rewrites are all detected unless the owner account is also compromised. Every anchor emits a `ChainAnchored` event, but the app does not audit that history yet. |
| Login hardening | No rate limiting or account lockout on failed logins, and HTTPS is not configured. | Passwords are salted hashes, and ports are bound to localhost. Put a TLS reverse proxy in front for anything shared. |
| Reputation engine | Inspection results are entered by any user with the `canFarmer` permission, and the contract trusts them. A dishonest inspector can penalise or suspend a farmer. | Inspections are on-chain and emit events (`QualityValidated`, `PenaltyApplied`), so they can be audited. Restrict `canFarmer` to trusted inspectors. |
| Personal data | Farmer and buyer records hold contact details and Aadhaar numbers in clear text. | Don't load real personal data into a demo deployment. |

## Resolved

Issues present in earlier versions, now fixed:

- **SQL injection** in login, password change and block generation. All queries are now
  parameterised.
- **Plain-text passwords.** Passwords are stored as salted hashes (Werkzeug `scrypt`). Existing
  plain-text passwords are hashed at startup (`upgrade_passwords.py`) or on the user's next login,
  and the Users form no longer displays the stored password.
- **CSRF.** Every form carries a per-session token, and POSTs without a valid token are rejected.
  Session cookies are also `HttpOnly` and `SameSite=Lax`.
- **Shared login state.** The logged-in user and role were Python globals, so one login unlocked
  the app for every visitor until restart, and *Logout* did not log out. Logins are now per-browser
  Flask sessions, and the user and role are reloaded on each request.
- **Unauthenticated blockchain pages.** *Generate Blocks* and *Blockchain Report* now require a
  login with the `canTransactionDetails` permission.
- **Weak hash chain.** Block hashes covered only four fields and not the previous hash, and the
  report never re-checked them. Hashes now cover every field and `prevHash`, the report verifies
  the whole chain, and the chain's tip is anchored on Ethereum, so a fully re-hashed rewrite is
  also detected.
- **Edits silently unsealed transactions.** Editing a transaction reset its seal and set its
  `sequenceNumber` to 0. Edits now leave the seal intact, so they show as tampering.
- **Database rows without an on-chain record.** A transaction was saved to the database before
  being sent to Ethereum, so an Ethereum failure left an unrecorded row. The chain is now written
  first, and the row stores the Ethereum transaction hash.
