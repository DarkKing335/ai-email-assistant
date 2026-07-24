# AI Email Assistant — Demo Guide

> **Project version:** backend `0.2.0`  
> **Last verified:** 2026-07-24  
> **Audience:** mentor, evaluator, and demo presenter  
> **Recommended duration:** 6–8 minutes

## Demo objective

Show that the system can:

1. connect to Gmail without placing Google credentials in the extension;
2. process only explicitly whitelisted senders;
3. summarize an incoming email and identify its action items;
4. generate a reply as a real draft in the original Gmail thread;
5. leave the final send decision to the user; and
6. make its decisions visible through the Inbox, Logs, and Dashboard views.

The most important safety statement is:

> **The assistant creates drafts; it never sends email.**

## 30-second product introduction

“AI Email Assistant is a Chrome side-panel extension backed by a local FastAPI
service. The backend checks Gmail for new messages, filters them through a
user-managed whitelist, summarizes matching mail, and creates a reply draft in
Gmail. The user reviews, edits, and sends the draft manually. Messages from
unlisted senders are logged as skipped and never reach the AI pipeline.”

## What the audience will see

| Product area | What it proves |
|---|---|
| **Settings** | The backend is reachable and a Gmail account is connected. |
| **Whitelist** | Processing is opt-in by exact address or domain. |
| **Inbox** | The structured summary, key points, action items, and draft status are available. |
| **Gmail thread** | The generated response is a real, editable Gmail draft and has not been sent. |
| **Logs** | Completed, skipped, processing, and failed outcomes are explainable. |
| **Dashboard** | The system aggregates volume, outcomes, drafts, failures, and top senders. |

## Before the demo

Use two Gmail accounts:

- **Assistant account:** the account connected to the backend.
- **Sender account:** a second account that sends the test message.

Complete this checklist before presenting:

- [ ] `backend/.env` contains at least one working model provider (normally a
      Groq key and model; Gemini can also run as the sole provider).
- [ ] `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` are configured.
- [ ] The Gmail API is enabled in the Google Cloud project.
- [ ] The assistant account is connected under **Settings**.
- [ ] The sender account is present in **Whitelist** as an exact address.
- [ ] The backend health check returns `{"status":"ok"}`.
- [ ] The extension build is loaded from `frontend/dist`.
- [ ] A rehearsal message completed successfully.
- [ ] A previously completed message and Gmail draft are kept as a backup.
- [ ] No terminal, browser tab, or screen share exposes `.env`, API keys, or OAuth tokens.

For Gmail OAuth setup, use [Connecting Gmail](setup/gmail-oauth.md).

## Start the system

Open one terminal for the backend:

```bash
cd backend
uv sync --group dev
uv run uvicorn src.main:app --reload
```

Confirm the API is available:

```bash
curl http://127.0.0.1:8000/health
```

Build the extension in another terminal:

```bash
cd frontend
npm install
npm run build
```

In Chrome:

1. Open `chrome://extensions`.
2. Enable **Developer mode**.
3. Choose **Load unpacked** and select `frontend/dist`.
4. Open Gmail.
5. Click the AI Email Assistant toolbar icon to open the side panel.
6. Open **Settings** and confirm that the expected Gmail address is shown as
   **Connected**.

The backend discovers mail every 60 seconds by default. The open Inbox and
Dashboard views refresh every 30 seconds. Allow up to about 90 seconds during a
live run.

## Recommended live scenario

Send this message from the whitelisted sender account to the connected assistant
account:

```text
Subject: Pricing request for the Pro plan

Hello,

We are evaluating the Pro plan for a team of 12 people. Could you send the
pricing information and confirm whether SSO and priority support are included?
We would like to make a decision by Friday.

Thanks,
Alex
```

This example is useful because it contains:

- a clear intent: pricing inquiry;
- two concrete questions;
- a team size;
- an action item; and
- a deadline stated by the sender.

The exact AI wording can vary. Do not promise an exact summary or draft during
the presentation; verify that the facts and intent are preserved.

## 6–8 minute presentation script

| Time | Action | Suggested explanation |
|---|---|---|
| 0:00 | Open the side panel. | Introduce the problem: important email requires reading context and starting a reply. |
| 0:30 | Open **Settings**. | Show the connected account. Explain that OAuth tokens live in the backend, not in the extension. |
| 1:10 | Open **Whitelist**. | Show the sender rule. Explain exact-address and whole-domain rules and that unlisted mail is skipped before any model call. |
| 2:00 | Send the prepared email. | Point out that the test begins with an ordinary Gmail message; no manual API request is involved. |
| 2:30 | While polling runs, briefly show the architecture diagram. | Explain the path: Gmail → poller → whitelist → summary → route → compose → stored result → Gmail draft. |
| 3:30 | Open **Logs** if the message has appeared. | Show that every inbound message receives a visible outcome and reason. |
| 4:10 | Open **Inbox** and expand the new email. | Show the overview, key points, action items, language, provider, and selected template. |
| 5:20 | Select **Check draft**. | Gmail opens the original thread with the generated draft inline. Emphasize that nothing has been sent. |
| 6:20 | Return to **Dashboard**. | Show how the completed run changes operational metrics. |
| 7:00 | Close with the safety boundary. | “The AI prepares the work, but the user remains the final decision-maker.” |

## Expected result

The run is successful when all of the following are true:

| Check | Expected result |
|---|---|
| Whitelist match | The sender matches the exact address or its domain rule. |
| Log | A row is created and ends in `completed`. |
| Summary | Inbox shows an overview plus supported key points and action items. |
| Classification | The selected template will normally be `PRICING_INQUIRY` for the sample. |
| Draft storage | A generated draft row is saved in SQLite. |
| Gmail | A draft appears inside the original thread. |
| Safety | The message remains a draft until the presenter manually sends or deletes it. |

One matched email normally performs three logical model operations:

1. summarize the email;
2. choose a response template; and
3. compose the response.

Provider retry or fallback can increase the actual number of external calls.
An unmatched sender performs none of these operations.

## Optional negative-path demonstration

If time permits, send a short message from an address that is **not** on the
whitelist.

Expected behavior:

1. the message appears in **Logs** as `skipped`;
2. the detail says the sender is not on the whitelist;
3. it does not appear in the default Inbox view;
4. no summary or draft is generated; and
5. the Dashboard unmatched count increases.

Adding the sender later does not automatically reprocess old mail. A rescan is
an explicit backend operation:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/whitelist/rescan
```

The endpoint returns `202 Accepted`; the background worker processes eligible
skipped messages from the configured lookback window. Use this only when you
intend to spend model calls and create real Gmail drafts.

## Architecture explanation for the demo

Use this one-line view when time is limited:

```text
Gmail → backend poller → whitelist → summarize → route → compose
      → SQLite audit record → Gmail draft → Chrome side panel
```

Three boundaries are worth explaining:

- **Chrome extension:** presents data, stores UI preferences, shows badges, and
  reads the sender of the open Gmail thread for quick-add.
- **FastAPI backend:** owns OAuth, Gmail polling, business rules, AI
  orchestration, persistence, and REST APIs.
- **External services:** Gmail supplies mail and stores drafts; Groq is the
  primary model provider and Gemini is the configured fallback.

The full design is in
[System Architecture](architecture/system-architecture.md).

## Troubleshooting during a demo

| Symptom | Check |
|---|---|
| Side panel says the backend is unavailable | Open `http://127.0.0.1:8000/health`; then verify the saved API URL in Settings. |
| Gmail is not connected | Confirm the OAuth client, test user, redirect URI, scopes, and backend restart. |
| New message does not appear | Wait for the 60-second backend poll and 30-second panel refresh; confirm the message is in the Gmail inbox and the poller has no error in Settings. |
| Message is `skipped` | Add the exact sender or `@domain` rule. This is expected whitelist behavior, not an AI failure. |
| Message is `failed` before a summary | Verify the model key/model, provider quota, and that the email has readable text. |
| Reply was generated but Gmail has no draft | Expand the Inbox item. The UI reports when generation succeeded but Gmail filing failed; verify the `gmail.compose` scope and connection. |
| OAuth succeeds but Gmail calls return 403 | Enable the Gmail API in the same Google Cloud project as the OAuth client. |
| The live provider is slow or unavailable | Use the previously rehearsed completed message and its existing Gmail draft, then describe the live run as a recorded result. |

## Presenter notes

- Keep the sender and subject unique so the new row is easy to find.
- Start the backend before sending the demo message.
- Do not use a busy personal inbox for the presentation.
- Keep the whitelist narrow to avoid unrelated messages consuming model quota.
- Do not manually send the generated reply unless the demonstration explicitly
  requires it.
- Use `/docs` only for a technical audience; the side panel is the product
  experience.

## Suggested evidence to capture for a report

Capture these five screenshots after a successful rehearsal:

1. Settings showing **Connected** with secrets hidden.
2. Whitelist showing the test sender.
3. Expanded Inbox item showing the structured summary.
4. Gmail thread showing the unsent draft.
5. Dashboard showing the updated counts.

Use synthetic or redacted email content in any document that will be shared.
