# Meeting preparation with the Clerk

The Clerk can pull together a draft agenda from live data — decisions due for review, open tensions, and recent outcomes. It does this in one command. The member still adds standing items and circulates the final agenda.

---

## Getting a draft agenda

Send this message in any Mattermost channel where the Clerk is present:

```
@clerk please prepare a draft agenda for our next meeting
```

To limit the agenda to a specific group:

```
@clerk draft a meeting agenda for the worker-owners group
```

When you send either message, the Clerk calls the Glass Box to fetch agreements due for review, open tensions, and recent decisions. It then returns a Markdown draft that you can copy directly into a Nextcloud document or paste into a Loomio thread.

---

## Reviewing the draft

Before circulating the agenda, read it through and:

- Add standing items that the Clerk does not know about — welcome or introductions, the treasurer's report, any other business.
- Check that review dates are still accurate. If an agreement was handled informally since the last meeting, remove it.
- Remove any items that have already been resolved.

The draft is a starting point. Final editorial judgement stays with the member who called it.

---

## Circulating the agenda

You have two options.

**Option 1 — post via the Clerk:**

```
@clerk post this agenda to #governance-general
```

Posting via the Clerk logs the action in the Glass Box, so there is a clear record of when the agenda was distributed and to which channel.

**Option 2 — copy into Nextcloud:**

Copy the Markdown from the Clerk's reply, paste it into a new Nextcloud document, and share the link with members in the usual way.

Either approach is acceptable. Use option 1 when you want the Glass Box record; use option 2 when you need to make significant edits before sharing.

---

## Checking what is due for review

```
@clerk what agreements are due for review?
```

The Clerk returns a list of agreements whose review date has passed or falls within the next fourteen days, along with the date each was last reviewed.

---

## Checking open tensions

```
@clerk what tensions are currently open?
```

The Clerk returns all tensions that have been logged but not yet resolved, with the driver summary and the person who raised each one.

---

## Further reading

- [Meeting agenda template](../templates/meeting-agenda.md)
- [Glass Box overview](../overview.md)
