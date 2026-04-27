## Snowflake Authentication

### Authentication methods

Six authenticators, selected via the `authenticator` field on a connection:

| Authenticator | Class | Key fields |
|---|---|---|
| `username_password` (default) | `UsernamePasswordAuth` | `user`, `password` |
| `username_password_mfa` | `UsernamePasswordMFAAuth` | `user`, `password` |
| `externalbrowser` | `ExternalBrowserAuth` | `user` |
| `jwt` | `JWTAuth` | `user`, `private_key_path` or `private_key` |
| `oauth` | `OAuthAuth` | `token` |
| `programmatic_access_token` | `ProgrammaticAccessTokenAuth` | `token` |

All Snowflake authenticators share: `account`, `warehouse`, and optional `role`, `database`, `schema`.

**MFA reminder:** `username_password_mfa` and `externalbrowser` prompt the user on their MFA device. Tell the user to be ready when you run `rai connect`.

**CI / non-interactive:** `externalbrowser` requires an interactive session and will fail in CI. Use `jwt` or `username_password` instead.

### Active Session auto-detection (SPCS / Snowflake Notebooks)

When running inside Snowflake (notebooks, stored procedures, UDFs), PyRel auto-detects the active Snowpark session. No config file needed — `create_config()` returns a `ConfigFromActiveSession` that wraps `get_active_session()`.
