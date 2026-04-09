# Iskander Chat Widget Implementation

Create `src/IskanderOS/services/loomio/iskander-chat-widget/`.

## Architecture

```
Loomio Page → widget.js → WebSocket → OpenClaw :3100/chat → Clerk Agent → Response → widget.js
```

## Files

### widget.js (~150 lines)
- Creates floating chat button (bottom-right corner)
- On click: opens chat panel (400px wide, 500px tall)
- Connects to `ws://localhost:3100/chat` via WebSocket
- Sends: `{ "message": "...", "user_id": "...", "context": { "thread_id": "...", "group_id": "..." } }`
- Receives: streamed text chunks, renders in chat panel
- Extracts Loomio context from current page URL:
  - `/d/123` → thread_id = 123
  - `/g/456` → group_id = 456
- Auth: reads Loomio session cookie, passes as user identifier

### inject.js (~20 lines)
- Appends `<link>` for style.css and `<script>` for widget.js to document head
- Auto-executes on page load

### style.css (~80 lines)
- `.iskander-chat-button`: fixed bottom-right, circular, cooperative brand color
- `.iskander-chat-panel`: slide-up panel, message bubbles (user right, clerk left)
- `.iskander-chat-input`: text input + send button at panel bottom
- Matches Loomio's design language (use CSS variables from Loomio's theme)

## Injection Method

Mount the widget directory into Loomio's Docker container as a volume, then add a custom initializer that injects the script tag. In `docker-compose.mvp.yml`:

```yaml
loomio:
  volumes:
    - ./iskander-chat-widget:/loomio/public/iskander
```

Add to Loomio's custom head HTML (via THEME_CUSTOM_HEAD env var):
```env
THEME_CUSTOM_HEAD=<script src="/iskander/inject.js" defer></script>
```
