---
name: seo-feedback-handoff
description: >-
  Turns the open client comments on a client's SEO article page in Notion into a
  partner-ready feedback handoff PDF (article rendered with each open comment anchored
  to its passage and color-coded by type), saves it to the client's handoff Drive
  folder, and posts a Slack alert with the link. Trigger whenever the user asks to
  "build the SEO feedback handoff," "consolidate the comments for [article],"
  "package the client feedback for the SEO partner," "HC1 feedback handoff for an
  article," or any variation of turning Notion review comments into a handoff for an
  outside SEO/content partner. Also the logic invoked by the HC1 scheduled
  feedback-handoff task. Scoped per client; defaults to HC1 (Home Carpet One). Does
  NOT create the article page (that is the seo-article-builder skill) and does NOT
  email the partner.
---

# SEO Feedback Handoff

Closes the SEO content feedback loop. Given a client's article page in their SEO Articles Notion database, this skill pulls the OPEN client comments, rebuilds the article with each comment anchored to its passage, generates the locked handoff PDF, saves it to the client's handoff Drive folder, and posts a Slack alert so the account/project manager can forward it to the SEO partner.

The partner-facing format is fixed and lives in the bundled generator (`seo_handoff_generator.py`). Do not re-improvise the layout; always render through the generator so every handoff is identical.

## When This Runs

- On demand, e.g. `HC1 feedback handoff: <article name or page link>`, or "build the handoff for <article>."
- As the per-article step of a scheduled task that has already identified which articles qualify (status moved off "For review").

## Client Defaults

Default client is **HC1 (Home Carpet One)**.

| Setting | HC1 value |
|---|---|
| Articles database | `HC1 SEO Articles` (inside the `HC1 SEO Project Status` pipeline page) |
| Slack destination | `#01-hc1-seo` (`C0BA36LTQEB`) |
| Slack mention | `@olivia` (Olivia White, `U08T5AUND8A`) |
| Handoff Drive folder | `https://drive.google.com/drive/u/0/folders/1rkk5Mf0eojkQ1ouLgewy4-i6D81FNnPi` |

Resolve the database fresh by name every run (Notion can reassign IDs when pages are duplicated or moved); never hardcode IDs. For other clients, swap these four values.

## Step-by-Step Workflow

### 1. Resolve the article page
`notion-search` for the article in the `HC1 SEO Articles` database (or open the page link the user gave). Read the page body and properties: Topic/Article Name, Status, Keyword Targets, Original Article. Note the current Status (it drives the handoff framing: "Revisions in progress" vs "Approved").

### 2. Pull the open comments with their anchors
`notion-fetch` the page with discussions enabled, and `notion-get-comments` on the page. For each comment capture: the comment text, the author, the date, the resolved/open state, and the passage (block text) it is attached to.
- **Include OPEN (unresolved) comments only.** Skip resolved threads.
- If a thread has replies, use the originating client comment as the item; fold material replies into its text if they change the ask.
- If a comment is page-level (not anchored to a block), list it under a "General" passage at the top of the body.

### 3. Classify each comment
Tag each open comment as exactly one of:
- **REVISION REQUEST** - asks for a change to the content (edits, additions, cuts, tone, links to add).
- **QUESTION** - asks something that needs an answer/decision before proceeding.
- **APPROVAL** - signals a passage is good as-is / explicit sign-off.
When ambiguous, default to REVISION REQUEST (the safer "needs action" bucket).

### 4. Decide whether a handoff is needed (dedup)
Search `#01-hc1-seo` for the most recent prior handoff message about this exact article.
- Build a handoff if there is no prior message, OR if at least one open comment was created after the most recent prior handoff message (a new review round).
- If Status is "Approved" with zero open comments and a prior approval message already exists, skip.
- Otherwise skip - already handed off, nothing new.

### 5. Build the spec and render the PDF
Construct a JSON spec for the generator:
- `meta`: title, client, status, round (infer the review round, default 1), keywords (from Keyword Targets), source, generated date, footer (`<CLIENT> SEO content review - client feedback handoff - prepared by Kulin Agency`).
- `blocks`: the article in order. Headings as `{"type":"h2","text":...}`. Paragraphs as `{"type":"p","text":...}`. For any paragraph carrying a comment, insert a `{{n}}` token at the anchor point (end of the anchored sentence/phrase if an exact offset is not recoverable) and attach the comment object(s) under `comments`.
Then run:
```
python3 seo_handoff_generator.py spec.json "<output>.pdf"
```
Name the file: `<CLIENT> - <Article Name> - Client Feedback - <YYYY-MM-DD>.pdf`.

Special case - "Approved" with zero open comments: skip the PDF and go to step 7 with a short approval message instead.

### 6. Save to the handoff Drive folder
Upload the PDF to the client's handoff Drive folder (HC1: the folder above). Capture the shareable link. Note: this skill cannot change the folder's sharing settings - the folder must already be shared so the link resolves for the PM and partner.

### 7. Post the Slack alert
Post to the client's Slack destination (`#01-hc1-seo` for HC1) in exactly this format:
```
SEO article ready for next step: <Article Name>
Status: <status value>
<X> open client comments - <Y> revision requests, <Z> questions, <W> approvals
Handoff PDF: <Drive link>
<@mention>
```
For the approved-clean case:
```
SEO article approved - no changes requested: <Article Name>
Status: Approved
Ready to publish / hand back to partner.
<@mention>
```
Slack delivery is a link in the message, not a native file attachment (the integration does not expose file upload). Never email the partner or anyone outside the team; the PM forwards manually.

### 8. Report back (on-demand runs)
In chat, give the PM the Drive link, the comment counts, and a one-line note of anything that needed a judgment call (e.g. a page-level comment, an ambiguous classification).

## Error Handling
- If comments cannot be read or the PDF cannot be saved, post a short note to the Slack channel naming the article and the problem, and do NOT mark it handed off, so it retries next run.
- If the article body cannot be read, stop and flag it; do not post a partial handoff.
- If Keyword Targets or other properties are missing, render with what is available and note the gap in the report-back.

## Important Notes
- The partner-facing layout is owned by `seo_handoff_generator.py`. Format changes go in the generator, not in ad-hoc rendering, so on-demand and scheduled runs stay identical.
- Open comments only, always. Resolved threads never appear in a handoff.
- Comment-type colors are fixed: orange = revision request, blue = question, green = approval.
- Default scope is HC1; for another client, swap the four Client Defaults values and resolve that client's database by name.
