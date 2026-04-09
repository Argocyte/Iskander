# Loomio-Bridge Skill Implementation

Create `src/IskanderOS/openclaw/skills/loomio-bridge/SKILL.md` with these procedures.

Environment variables needed: `LOOMIO_URL`, `LOOMIO_API_KEY`, `LOOMIO_GROUP_ID`

## Procedures

### list-proposals
```bash
curl -s "${LOOMIO_URL}/api/v1/polls?group_id=${LOOMIO_GROUP_ID}&status=active" \
  -H "Authorization: Bearer ${LOOMIO_API_KEY}"
```
Parse JSON response. Format each poll as:
- "[Title] — [poll_type], closes [closing_at]. [voters_count] votes so far."

### summarise-thread
```bash
# Fetch discussion
curl -s "${LOOMIO_URL}/api/v1/discussions/${DISCUSSION_ID}" \
  -H "Authorization: Bearer ${LOOMIO_API_KEY}"
# Fetch comments
curl -s "${LOOMIO_URL}/api/v1/events?discussion_id=${DISCUSSION_ID}&event_types=new_comment" \
  -H "Authorization: Bearer ${LOOMIO_API_KEY}"
```
Combine discussion description + all comments. Use LLM to produce 3-5 sentence summary.

### create-proposal
Collect from member: title, details, poll_type (proposal/poll/count/score), closing_at (default: 3 days).
```bash
curl -s -X POST "${LOOMIO_URL}/api/v1/polls" \
  -H "Authorization: Bearer ${LOOMIO_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "poll": {
      "title": "...",
      "details": "...",
      "poll_type": "proposal",
      "group_id": GROUP_ID,
      "closing_at": "ISO8601_DATE"
    }
  }'
```
Return the poll URL to the member.

### check-outcome
```bash
curl -s "${LOOMIO_URL}/api/v1/polls/${POLL_ID}" \
  -H "Authorization: Bearer ${LOOMIO_API_KEY}"
```
Parse stances_count. Format as: "X agreed, Y disagreed, Z abstained, W blocked. Outcome: [passed/failed/pending]."

### remind-pending
```bash
# Get polls closing within 24 hours
curl -s "${LOOMIO_URL}/api/v1/polls?group_id=${LOOMIO_GROUP_ID}&status=active" \
  -H "Authorization: Bearer ${LOOMIO_API_KEY}"
```
Filter where `closing_at` < now + 24h. For each, format reminder message.
