## Snowflake Authentication

### Authentication methods

Eight authenticators, selected via the `authenticator` field on a connection:

| Authenticator | Class | Key fields |
|---|---|---|
| `username_password` (default) | `UsernamePasswordAuth` | `user`, `password` |
| `username_password_mfa` | `UsernamePasswordMFAAuth` | `user`, `password`, `passcode` (conditional — see MFA reminder) |
| `externalbrowser` | `ExternalBrowserAuth` | `user` |
| `jwt` | `JWTAuth` | `user`, `private_key_path` or `private_key` |
| `oauth` | `OAuthAuth` | `token` |
| `oauth_authorization_code` | `OAuthAuthorizationCodeAuth` | `oauth_client_id`, `oauth_redirect_uri` (must be localhost), optional `oauth_client_secret` |
| `oauth_client_credentials` | `OAuthClientCredentialsAuth` | `oauth_client_id`, `oauth_client_secret`, `oauth_token_request_url`, optional `oauth_scope` |
| `programmatic_access_token` | `ProgrammaticAccessTokenAuth` | `token` |

All Snowflake authenticators share: `account`, `warehouse`, and optional `role`, `database`, `schema`.

**MFA reminder:** `username_password_mfa` behavior depends on how the user's MFA is enrolled with Snowflake (via Duo), not on which authenticator app they use (Duo Mobile, Google Authenticator, Authy, etc. — Snowflake validates a standard TOTP/push challenge regardless of app):
- **Push-enrolled users:** the connector triggers a push notification and blocks until the user approves it on their device. No `passcode` field needed.
- **Passcode/TOTP-only-enrolled users:** the connector requires an explicit `passcode` field (a current TOTP code) in config — omitting it fails with an error demanding "a current TOTP passcode." Since a code is single-use and short-lived, supply it via env var templating and export a fresh, unused code immediately before every connection attempt (a stale or reused code is rejected).

`externalbrowser` and `oauth_authorization_code` prompt interactively via a browser window instead. Tell the user to be ready to complete sign-in (or approve a push, for push-enrolled MFA) when you run `rai connect`.

**CI / non-interactive:** `externalbrowser` requires an interactive session and will fail in CI. Use `jwt` or `username_password` instead.

### Active Session auto-detection (SPCS / Snowflake Notebooks)

When running inside Snowflake (notebooks, stored procedures, UDFs), PyRel auto-detects the active Snowpark session. No config file needed — `create_config()` returns a `ConfigFromActiveSession` that wraps `get_active_session()`.
