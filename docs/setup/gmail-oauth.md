# Connecting Gmail

One-time setup so the backend can read your inbox. Roughly 10 minutes, most of
it in Google's console.

**Nothing here touches the Chrome extension.** It requests no Gmail permissions
and holds no Google credentials — consent is granted to the backend, which is
what polls Gmail and creates drafts. The extension only displays the connection
status.

---

## 1. Create a Google Cloud project

<https://console.cloud.google.com/projectcreate> — any name.

## 2. Enable the Gmail API

**APIs & Services → Library** → search "Gmail API" → **Enable**.

Without this, consent succeeds and every API call then fails with a 403 that
does not mention the missing API.

## 3. Configure the consent screen

**APIs & Services → OAuth consent screen**

| Field | Value |
|---|---|
| User type | **External** |
| App name | AI Email Assistant |
| Support email | your address |
| Developer contact | your address |

Add these scopes:

```
https://www.googleapis.com/auth/gmail.readonly
https://www.googleapis.com/auth/gmail.compose
https://www.googleapis.com/auth/userinfo.email
```

Then — **this is the step people miss** — under **Test users**, add your own
Gmail address. Leave publishing status as **Testing**.

Testing mode allows up to 100 test users with no review process. Both Gmail
scopes are classed "sensitive", so *publishing* would require Google's
verification (and possibly a third-party security assessment). None of that
applies while the app stays in Testing.

## 4. Create the OAuth client

**APIs & Services → Credentials → Create credentials → OAuth client ID**

- Application type: **Web application** — **not** "Desktop app"
- Authorised redirect URI — exactly this, no trailing slash:

```
http://localhost:8000/api/v1/gmail/auth/callback
```

Copy the client ID and client secret.

> The redirect URI must match character for character. A mismatch is the most
> common failure, and Google reports it as `redirect_uri_mismatch` — the backend
> expands that into a readable message if you hit it.

> **Choosing "Desktop app" here does not work.** Desktop clients use the
> *loopback IP address flow*, which Google now blocks — consent fails with
> "Error 400: invalid_request" and a buried message about the loopback flow
> being blocked for security. Web application clients register explicit redirect
> URIs, and `http://localhost` is permitted for them. A Desktop client has no
> "Authorised redirect URIs" field at all, which is the quickest way to tell
> which type you created.

## 5. Configure the backend

Create `backend/.env`:

```ini
# Gmail OAuth
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret

# LLM — required, or every email fails before producing anything
GROQ_API_KEY=gsk_your_key
GROQ_MODEL=llama-3.3-70b-versatile
```

A free Groq key: <https://console.groq.com>.

Restart the backend.

## 6. Connect

Open the extension → **⚙ Settings** → **Connect Gmail**.

A tab opens with Google's consent screen. You will see an **"unverified app"**
warning — expected in Testing mode. Click **Advanced → Go to AI Email Assistant
(unsafe)** and grant access.

The tab confirms the connection and can be closed.

---

## What happens next

The backend checks for new mail every 60 seconds
(`GMAIL_POLL_INTERVAL_SECONDS`). Each message is matched against the whitelist:

- **no match** → logged as `skipped`, nothing else happens
- **match** → summarised, a draft is generated, and it appears in Logs

On first connect only the last hour is examined
(`GMAIL_INITIAL_LOOKBACK_MINUTES`), so linking an account does not process a
month of history.

To test end to end: add your own address to the whitelist, send yourself an
email, wait a minute, check the **Logs** tab.

---

## Settings worth knowing

| Variable | Default | Notes |
|---|---|---|
| `GMAIL_POLL_INTERVAL_SECONDS` | `60` | Spends Gmail API quota. Distinct from the extension's own refresh interval. |
| `GMAIL_POLL_QUERY` | `in:inbox -in:chats` | Any Gmail search expression. |
| `GMAIL_MAX_RESULTS_PER_POLL` | `25` | Stops a backlog stampeding the pipeline. |
| `GMAIL_INITIAL_LOOKBACK_MINUTES` | `60` | How far back the first poll looks. |

Each whitelisted email costs **two LLM calls** (summarise + route). A free-tier
Groq key will hit rate limits on a busy inbox — keep the whitelist narrow while
testing.

---

## Security

**The refresh token is stored in plaintext in `email_assistant.db`.** It grants
continuing access to your mailbox until revoked. Treat that file as a secret:
never commit it, never copy it off the machine. It is already gitignored.

**Every API endpoint is unauthenticated.** Fine bound to localhost; unacceptable
deployed, where anyone reaching the URL could read every stored summary and
trigger a disconnect.

To revoke access at any time, independently of this app:
<https://myaccount.google.com/permissions>

---

## Troubleshooting

| Symptom | Cause |
|---|---|
| **Error 400: `invalid_request`**, "Access blocked" | The OAuth client is a **Desktop app**. Google blocks the loopback flow it uses. Create a **Web application** client instead — see step 4. |
| `redirect_uri_mismatch` | The URI in Google Cloud differs from `GOOGLE_REDIRECT_URI`. They must be identical. |
| "Gmail is not set up" in Settings | Backend has no `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`, or it was not restarted. |
| `access_denied` | Your address is not in **Test users**. |
| Connected, but no logs appear | Sender is not whitelisted (expected), or the poll is failing — Settings shows the error. |
| Everything fails right after connecting | Usually a missing `GROQ_API_KEY`. Check the backend terminal. |
| `invalid_grant` after working | Token revoked or expired. Disconnect and connect again. |
