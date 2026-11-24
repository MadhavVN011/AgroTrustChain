# Security

AgroTrustChain is an **academic prototype** that accompanies a research paper. It is meant to run
on a single machine for demonstration and study. It is **not hardened for production** or for
exposure to the internet. The Docker setup binds every port to `127.0.0.1` for this reason.

## Reporting a Vulnerability

Please report security issues privately rather than in a public issue: use **Report a
vulnerability** under this repository's *Security* tab on GitHub, or contact the maintainers
through their GitHub profiles. Include steps to reproduce and the affected file or route.

## Known Limitations

These are known and not yet fixed. Keep them in mind before deploying the app anywhere shared.

| Area | Limitation | Mitigation today |
| --- | --- | --- |
| Passwords | Stored and compared in plain text in the `Users` table. | None. They should be salted and hashed with bcrypt or Argon2. |
| CSRF | Forms carry no CSRF token. | Session cookies are `SameSite=Lax` and `HttpOnly`, so browsers do not send them on cross-site POSTs. |
| Default credentials | The seed database has the login `1@1.com` / `1`. Docker defaults the SQL Server `sa` password to a value published in this repository. | Ports are bound to localhost. Change both before sharing a deployment: set `MSSQL_SA_PASSWORD` in `.env` before the first start. |
| Session key | Without `FLASK_SECRET_KEY`, a random key is generated at each start. | Set `FLASK_SECRET_KEY` for any long-running deployment. |
| Database privileges | The app connects as `sa` under Docker. | Use a least-privilege SQL login for anything beyond local use. |
| Hash chain | Someone with write access to the database can rewrite a record *and every later hash*, which yields a chain that verifies. | Edits, deletions and re-ordering are detected unless every later hash is recomputed. Anchoring the latest hash on-chain would close this (see Future Work in the README). |
| Ethereum account | Transactions are sent from Ganache's unlocked `accounts[0]`. | Acceptable only on a private development chain. A real network needs proper key management. |
| Personal data | Farmer and buyer records hold contact details and Aadhaar numbers in clear text. | Don't load real personal data into a demo deployment. |

## Resolved

Issues present in earlier versions, now fixed:

- **SQL injection** in login, password change and block generation. All queries are now
  parameterised.
- **Shared login state.** The logged-in user and role were Python globals, so one login unlocked
  the app for every visitor until restart, and *Logout* did not log out. Logins are now per-browser
  Flask sessions, and the user and role are reloaded on each request.
- **Unauthenticated blockchain pages.** *Generate Blocks* and *Blockchain Report* now require a
  login with the `canTransactionDetails` permission.
- **Weak hash chain.** Block hashes covered only four fields and not the previous hash, and the
  report never re-checked them. Hashes now cover every field and `prevHash`, and the report
  verifies the whole chain.
- **Edits silently unsealed transactions.** Editing a transaction reset its seal and set its
  `sequenceNumber` to 0. Edits now leave the seal intact, so they show as tampering.
