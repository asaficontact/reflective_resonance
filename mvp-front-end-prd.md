# Reflective Resonance — MVP Front-End PRD

**Document status**: Complete (implementation-ready)
**Owner**: Front-end team
**Last updated**: 2025-12-30
**Repo**: `reflective_resonance/`
**Version**: 1.0  

---

## 1) Overview

Reflective Resonance is an interactive art installation where **six speakers** produce water-wave patterns. The MVP front-end is a **minimalist, artistic control surface** that lets a user:

- Select from **six pre-created LLM "agents"** (models).
- Assign agents to **six speaker slots** (drag & drop or click-to-assign).
- Send a **single user message** and view **up to six agent responses** streaming in independently.

**Important**: This PRD covers only the front-end MVP. The backend (`rawagents`) and conversion of text → speaker parameters will be implemented later.

---

## 1.1) Problem Statement

**The core problem**: Exhibition operators and visitors need an intuitive way to configure which AI agents respond through each of the six speakers in the Reflective Resonance installation. Currently, there is no interface to:

1. **Visualize** the mapping between AI models and physical speakers.
2. **Experiment** with different agent combinations to observe how varied AI "voices" create different water-wave patterns.
3. **Interact** with multiple AI agents simultaneously and see their responses in real-time.

**Why this matters**: The art installation's impact depends on the visitor understanding the relationship between their words, the AI responses, and the resulting water patterns. Without a clear, artistic interface, this connection is lost.

**What success looks like**: A visitor approaches the kiosk, intuitively assigns agents to speakers within seconds, sends a message, and watches as six distinct AI responses appear—each destined for a different speaker and wave pattern.

---

## 2) Goals (What MVP must achieve)

- **Fast, clear assignment** of agents to speaker slots (1–6 slots; allow duplicates).
- **Single chat input** that can broadcast the user's message to the assigned slots.
- **Concurrent responses**: show responses from each slot as they arrive.
- **Minimalist + artistic UI** consistent with the installation's visual language (dark, neon violet/blue, subtle glow, fluid motion cues).
- **Lean code**: minimal dependencies, easy to maintain, easy to extend once backend arrives.

### 2.1) Feature Prioritization (MoSCoW)

| Priority | Feature | Rationale |
|----------|---------|-----------|
| **Must** | 6 speaker slot rings with visual states | Core UI element |
| **Must** | Agent palette with 6 agents | Required for assignment |
| **Must** | Drag-and-drop assignment | Primary interaction |
| **Must** | Click-to-assign fallback | Accessibility requirement (WCAG 2.2) |
| **Must** | Chat input with broadcast to assigned slots | Core functionality |
| **Must** | Mock response mode (simulated streaming) | Enables frontend-only development |
| **Must** | Per-slot error state with retry | Resilience requirement |
| **Must** | Empty state guidance | First-time user experience |
| **Should** | Token-by-token streaming simulation | Realistic preview of final UX |
| **Should** | localStorage persistence for slot assignments | Kiosk refresh resilience |
| **Should** | Keyboard shortcuts (1-6 for slots, Enter to send) | Power user efficiency |
| **Should** | Response column with slot color indicators | Readability for multiple responses |
| **Could** | Slot-to-slot swap via drag | Convenience feature |
| **Could** | "Fill all with same agent" quick action | Speed optimization |
| **Could** | JSON export of session | Debugging utility |
| **Could** | Per-slot conversation clear | Granular control |
| **Won't** | Agent personalities/custom system prompts | Deferred to post-MVP |
| **Won't** | Voice input (STT) | Deferred to post-MVP |
| **Won't** | Backend integration | Separate workstream |
| **Won't** | Mobile-optimized layout | Desktop/kiosk only for MVP |

---

## 3) Non-goals (Explicitly out of scope for MVP)

- Voice input (STT), audio pipeline, microphone UX
- Agent-to-agent conversation and orchestration
- Text → ML conversion into speaker parameters
- TouchDesigner integration and hardware control
- Auth, user accounts, persistence across sessions (beyond optional localStorage)
- Complex agent "personalities" (system prompt stays identical; only `model` varies)
- Mobile-optimized layout (desktop/kiosk only; responsive for different desktop screen sizes)
- Analytics, tracking, or success metrics collection

---

## 4) Users & primary use cases

### Primary user
- **Exhibition operator / viewer** interacting with the installation via a kiosk-style UI.

### Core use cases
- **Assign agents** to speaker slots.
- **Swap/replace** an agent in a slot.
- **Duplicate** one agent across multiple slots.
- **Send message** and watch responses populate per slot.
- **Reset** configuration (clear slots and/or clear conversation).

---

## 4.1) User Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           USER JOURNEY FLOW                                  │
└─────────────────────────────────────────────────────────────────────────────┘

    ┌──────────────┐
    │  User lands  │
    │   on page    │
    └──────┬───────┘
           │
           ▼
    ┌──────────────┐     ┌─────────────────────────────────────────────┐
    │  Empty State │────▶│ See 6 empty slot rings + agent palette      │
    │   Display    │     │ Guidance text: "Drag an agent to a speaker" │
    └──────┬───────┘     └─────────────────────────────────────────────┘
           │
           ▼
    ┌──────────────┐
    │ Assign Agent │◀───────────────────────────┐
    │   to Slot    │                            │
    └──────┬───────┘                            │
           │                                    │
           ├──── Option A: Drag agent ──────────┤
           │     from palette to ring           │
           │                                    │
           ├──── Option B: Click slot, ─────────┤
           │     then click agent               │
           │                                    │
           ▼                                    │
    ┌──────────────┐                            │
    │  Slot shows  │     Repeat for             │
    │ agent label  │     more slots ────────────┘
    │  + glow      │
    └──────┬───────┘
           │
           ▼
    ┌──────────────┐     ┌─────────────────────────────────────────────┐
    │ Chat dock    │────▶│ Text input appears/enables                  │
    │  activates   │     │ (≥1 slot assigned)                          │
    └──────┬───────┘     └─────────────────────────────────────────────┘
           │
           ▼
    ┌──────────────┐
    │  User types  │
    │   message    │
    └──────┬───────┘
           │
           ▼
    ┌──────────────┐     ┌─────────────────────────────────────────────┐
    │  User sends  │────▶│ Message broadcast to all assigned slots     │
    │   (Enter)    │     │ Slots enter "streaming" state               │
    └──────┬───────┘     └─────────────────────────────────────────────┘
           │
           ▼
    ┌──────────────┐
    │  Responses   │
    │   stream in  │
    │ (per slot)   │
    └──────┬───────┘
           │
           ├──── Success: Slot shows response ──────────┐
           │                                            │
           ├──── Error: Slot shows error + retry btn ───┤
           │                                            │
           ▼                                            ▼
    ┌──────────────┐                          ┌──────────────┐
    │  User reads  │                          │  User clicks │
    │  responses   │                          │    retry     │
    └──────┬───────┘                          └──────┬───────┘
           │                                         │
           └─────────────┬───────────────────────────┘
                         │
                         ▼
              ┌────────────────────┐
              │ Continue chatting  │
              │ or reset/reassign  │
              └────────────────────┘
```

### Key decision points
1. **Empty → First assignment**: User must understand how to assign (guidance text + visual affordance).
2. **Assignment method**: Drag-drop (primary) or click-to-assign (accessibility fallback).
3. **When to enable chat**: After ≥1 slot assigned (configurable to require all 6).
4. **Error recovery**: Per-slot retry without blocking other slots.

---

## 5) UX + Visual Direction ("Minimalist Artistic")

The installation visuals emphasize **deep blacks** with **neon violet/blue** light, reflective surfaces, and fluid wave textures. The UI should feel like a **quiet instrument panel** in dark space:

- **Background**: near-black with layered, low-opacity radial gradients (violet/blue) and soft blur.
- **Speaker slots**: six **glowing rings** (circles) that subtly animate on hover/active/streaming.
- **Restraint**: minimal borders; rely on spacing, glow, and typography rather than boxes.
- **Motion**: slow, subtle transitions (150–250ms). No bouncy, “app-like” animations.
- **Typography**: clean sans-serif, low visual noise, clear hierarchy.

### Visual tokens (initial recommended defaults)
Front-end should centralize tokens in CSS variables (Tailwind-friendly):

- `--rr-bg`: `#05060A` (near black)
- `--rr-panel`: `rgba(255,255,255,0.03)` (frosted panel)
- `--rr-text`: `rgba(255,255,255,0.86)`
- `--rr-muted`: `rgba(255,255,255,0.56)`
- `--rr-accent-violet`: `#7C3AED`
- `--rr-accent-blue`: `#0EA5E9`
- `--rr-glow`: `rgba(124,58,237,0.35)` and `rgba(14,165,233,0.28)`

### Slot (ring) states
- **Empty**: faint ring + subtle glow; shows “Drop agent” / “Assign” label.
- **Hover (drop-target)**: brighter glow and slight scale (≤ 1.02).
- **Assigned**: ring glow tinted to agent color; shows agent label.
- **Active (selected)**: stronger glow and a thin inner ring.
- **Streaming**: slow “shimmer” (opacity pulse), not distracting.
- **Error**: small red indicator dot + tooltip (no modal).

### Accessibility & comfort
- Respect `prefers-reduced-motion`: disable shimmer/pulses, keep only fades.
- Maintain readable contrast (target WCAG AA for text; glows are decorative).

---

## 6) Information architecture / Layout

### Desktop / kiosk layout
- **Left rail** (agent palette): list of available agents (6 total).
- **Main canvas**: six speaker rings arranged as a **2×3 grid** by default.
  - If physical arrangement is hexagonal, the grid can be replaced with a hex layout later without changing slot state model.
- **Bottom dock**: chat input and send controls.
- **Responses**: show responses either:
  - **Inside each ring** (short preview + expand on click), OR
  - In a **right-side column** grouped by slot (recommended for readability).

### Responsive breakpoints (desktop only)

The MVP targets desktop/kiosk displays. No mobile layout is required, but the UI should adapt gracefully to different desktop screen sizes.

| Breakpoint | Width | Layout Adjustments |
|------------|-------|-------------------|
| **Large** | ≥1440px | Full 3-column layout: Left rail (240px) + Main canvas + Response column (320px) |
| **Medium** | 1280–1439px | Narrower left rail (200px), response column (280px) |
| **Small desktop** | 1024–1279px | Compact left rail (180px), responses below slots instead of side column |
| **Minimum** | <1024px | Show warning: "Please use a larger screen for the best experience" |

### Layout grid (recommended)
```
┌─────────────────────────────────────────────────────────────────┐
│                         Header (optional)                        │
├──────────┬────────────────────────────────┬─────────────────────┤
│          │                                │                     │
│  Agent   │      Speaker Slot Rings        │    Responses        │
│ Palette  │         (2×3 grid)             │     Column          │
│          │                                │                     │
│  ┌────┐  │    ┌───┐   ┌───┐   ┌───┐      │   ┌─────────────┐   │
│  │ A1 │  │    │ 1 │   │ 2 │   │ 3 │      │   │ Slot 1 resp │   │
│  ├────┤  │    └───┘   └───┘   └───┘      │   ├─────────────┤   │
│  │ A2 │  │                                │   │ Slot 2 resp │   │
│  ├────┤  │    ┌───┐   ┌───┐   ┌───┐      │   ├─────────────┤   │
│  │ A3 │  │    │ 4 │   │ 5 │   │ 6 │      │   │ Slot 3 resp │   │
│  ├────┤  │    └───┘   └───┘   └───┘      │   ├─────────────┤   │
│  │ A4 │  │                                │   │    ...      │   │
│  ├────┤  │                                │   └─────────────┘   │
│  │ A5 │  │                                │                     │
│  ├────┤  │                                │                     │
│  │ A6 │  │                                │                     │
│  └────┘  │                                │                     │
├──────────┴────────────────────────────────┴─────────────────────┤
│                        Chat Dock (fixed)                         │
│  ┌──────────────────────────────────────────────┐  ┌────────┐   │
│  │ Type your message...                         │  │  Send  │   │
│  └──────────────────────────────────────────────┘  └────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 7) Functional requirements

### 7.1 Agent list (palette)

Display the six available agents with brief descriptions to help users differentiate:

| Agent | Model ID | Description | Accent Color |
|-------|----------|-------------|--------------|
| Claude Sonnet 4.5 | `claude-sonnet-4-5` | Fast, balanced responses | Violet (`#7C3AED`) |
| Claude Opus 4.5 | `claude-opus-4-5` | Deep, thoughtful analysis | Deep Violet (`#6D28D9`) |
| GPT 5.2 | `gpt-5.2` | Latest OpenAI reasoning | Blue (`#0EA5E9`) |
| GPT 5.1 | `gpt-5.1` | Stable, reliable outputs | Sky Blue (`#38BDF8`) |
| GPT-4o | `gpt-4o` | Multimodal capabilities | Cyan (`#22D3EE`) |
| Gemini 3 | `gemini-3` | Google's frontier model | Teal (`#14B8A6`) |

**Note**: In MVP, all agents share the same system prompt. Descriptions are for user differentiation only; actual behavior differences come from the underlying models.

Each agent item displays:
- Name + small "model tag" (e.g., "Anthropic" / "OpenAI" / "Google")
- Brief tagline (optional, can be hidden if space is tight)
- Assigned count badge (e.g., "×2" if used in two slots)
- Drag handle (optional; whole row draggable is fine)
- Accent color indicator (small colored dot or border)

### 7.2 Speaker slot assignment (6 slots)

- There are exactly **6 slots**, representing the 6 physical speakers.
- Each slot can be:
  - **Empty**
  - **Assigned** to an agent (agents may be duplicated across multiple slots)
- Slot UI must show:
  - Slot label (e.g., “Speaker 1” … “Speaker 6”)
  - Assigned agent name (if assigned)
  - Streaming indicator (when response is in progress)
  - Clear/remove control (minimal icon button)

#### Assignment interactions (must-have)
- **Drag & drop**:
  - Drag an agent from the palette onto a slot ring to assign.
  - Dropping onto an occupied ring **replaces** the slot’s agent.
- **Click-to-assign fallback** (required for accessibility and touch devices):
  - Click a slot to “select” it.
  - Click an agent in the palette to assign to the selected slot.
  - `Esc` clears selection.
- **Remove**:
  - Slot has a small clear button (or context menu) to unassign.
- **Reset all**:
  - One control to clear all slot assignments (confirm via small inline confirm, not a modal).

#### Nice-to-have (if time permits)
- Slot-to-slot **swap** via drag between rings.
- "Fill all" action that assigns a default mapping quickly.

### 7.2.1 Empty state UX (first-time experience)

When a user first lands on the page with no assignments, the UI must guide them to take action:

**Visual treatment**:
- All 6 slot rings display in "empty" state (faint glow, dashed or dotted border)
- Each empty ring shows text: "Drop agent" or numbered "1", "2", etc.
- A subtle animated hint (gentle pulse on first ring, respecting `prefers-reduced-motion`)

**Guidance text** (displayed above or within the slot grid):
- Primary: **"Drag an agent to a speaker to begin"**
- Secondary (muted): "Or click a speaker, then click an agent"

**Progressive disclosure**:
1. On first assignment: Guidance text updates to "Great! Assign more agents or start chatting"
2. On first message sent: Guidance disappears entirely
3. After reset: Guidance returns

**Empty response panel**:
- Before any messages: Show placeholder text "Responses will appear here"
- Use a subtle illustration or icon (optional) to fill the space without clutter

### 7.3 Chat: input + broadcast + responses

#### Chat visibility / enablement
The MVP should allow messaging when the user has assigned the slots they intend to use.

**Default behavior (recommended)**:
- Chat dock becomes visible once **≥ 1 slot** is assigned.
- “Send” is enabled when:
  - input is non-empty, AND
  - at least 1 slot assigned, AND
  - not currently sending (or allow queuing; see below)

**Config flag (optional)**:
- `REQUIRE_ALL_SLOTS = true|false`
  - If `true`, only enable “Send” once all 6 slots are assigned.

#### Broadcast behavior
- A single "Send" fans out the user message to **each assigned slot**.
- Responses may return at different times; UI should render each as soon as available.
- Each slot maintains its own conversation thread (for future backend parity).

#### Concurrent request handling

**What happens if the user sends a new message while responses are still streaming?**

| Approach | Behavior | Recommendation |
|----------|----------|----------------|
| **Block** | Disable Send button until all slots complete or error | ✅ **Recommended for MVP** |
| **Queue** | Queue the new message, send after current completes | More complex, defer |
| **Cancel** | Cancel in-flight responses, send new message | Risky UX, not recommended |

**MVP behavior (Block)**:
- Send button disabled while `isSending = true`
- `isSending` becomes `false` only when ALL assigned slots have completed (success or error)
- Visual indicator: Send button shows loading state or "Waiting..."
- User can still scroll/read responses while waiting

#### Response rendering
- Each slot shows:
  - Latest response text (streaming supported)
  - Timestamp (optional; can be hidden by default)
  - Status: idle / streaming / done / error
- UX should support reading multiple responses without clutter:
  - Recommended: a **Responses column** grouped by slot, with subtle slot color indicator.

#### Response length limits

| Constraint | Value | Behavior |
|------------|-------|----------|
| **Max display length** | 2000 characters | Truncate with "Show more" expander |
| **Max tokens (backend)** | 500 tokens | Set in backend config (not frontend concern for MVP) |
| **Scroll behavior** | Auto-scroll during stream | Stop auto-scroll if user manually scrolls up |

**Long response handling**:
- During streaming: Show full response, container scrolls
- After completion: If >2000 chars, collapse to ~500 chars with "Show more" button
- "Show more" expands inline (no modal)

#### Slot-to-response visual mapping

Users must clearly understand which response came from which slot/agent:

**Response card design**:
```
┌─────────────────────────────────────────┐
│ ● Speaker 3 · Claude Sonnet 4.5         │  ← Slot number + Agent name
│   ─────────────────────────────────     │  ← Colored accent bar (agent color)
│                                         │
│   Response text appears here...         │
│                                         │
│                          ⟳ Retry   ✓    │  ← Status indicators
└─────────────────────────────────────────┘
```

**Visual indicators**:
- **Accent bar**: Left border or top bar colored with agent's accent color
- **Slot number**: "Speaker 1", "Speaker 2", etc. (matches physical installation)
- **Agent name**: Displayed alongside slot number
- **Status icon**: Spinner (streaming), checkmark (done), warning (error)

#### Error handling (must-have)

**Error types and handling**:

| Error Type | Cause | User Message | Action |
|------------|-------|--------------|--------|
| **Network** | Connection lost | "Connection lost" | Retry button |
| **Timeout** | Response took >30s | "Response timed out" | Retry button |
| **Rate limit** | Too many requests | "Too many requests. Wait a moment." | Auto-retry after delay |
| **Server error** | 5xx from backend | "Something went wrong" | Retry button |
| **Unknown** | Unexpected error | "Unable to get response" | Retry button |

**Error UX principles**:
- **Position error close to context**: Error indicator appears on the specific slot ring AND in the response card
- **Don't blame the user**: Use neutral language ("Connection lost" not "You lost connection")
- **Provide clear action**: Always show a Retry button
- **Don't block siblings**: One slot's error must not prevent other slots from completing

**Retry behavior**:
- Single retry: Click retry on specific slot
- "Retry all failed": Button appears when ≥2 slots have errors
- Retry preserves the original message (user doesn't re-type)
- Max retries: 3 per slot per message, then show "Unable to complete. Please try again later."

**Timeout configuration**:
```typescript
const ERROR_CONFIG = {
  RESPONSE_TIMEOUT_MS: 30000,      // 30 seconds
  RETRY_DELAY_MS: 1000,            // 1 second between retries
  MAX_RETRIES: 3,
  RATE_LIMIT_BACKOFF_MS: 5000      // 5 seconds for rate limit
};
```

### 7.4 Session controls
- **Clear conversation**:
  - Clears messages for all slots (or provide per-slot clear; per-slot is nice-to-have)
- **Clear all**:
  - Clears slots + messages
- **Export (optional)**:
  - JSON export of current mapping + conversation (useful for debugging later)

### 7.5 Keyboard shortcuts

For kiosk and power-user efficiency, implement keyboard navigation:

| Shortcut | Action | Context |
|----------|--------|---------|
| `1` - `6` | Select slot 1-6 | When chat input not focused |
| `Escape` | Clear slot selection / Cancel | Global |
| `Enter` | Send message | When chat input focused |
| `Shift + Enter` | New line in message | When chat input focused |
| `Tab` | Move focus forward | Global (standard) |
| `Shift + Tab` | Move focus backward | Global (standard) |
| `/` or `Ctrl + K` | Focus chat input | When chat input not focused (optional) |

**Implementation notes**:
- Number keys (1-6) only work when chat textarea is NOT focused
- All shortcuts should be discoverable via tooltip on hover (e.g., "Press 1-6 to select a speaker")
- Respect standard browser shortcuts (don't override Ctrl+C, Ctrl+V, etc.)

### 7.6 Offline / degraded mode

**Network interruption handling**:

| Scenario | Detection | User Feedback | Recovery |
|----------|-----------|---------------|----------|
| **Offline** | `navigator.onLine === false` | Toast: "You're offline" | Auto-retry when online |
| **Slow connection** | Response latency >5s | Subtle indicator on affected slot | Continue waiting |
| **Mid-stream disconnect** | SSE connection drops | Preserve partial response + "Connection lost" | Retry button |

**Graceful degradation**:
- If offline, disable Send button with tooltip "No internet connection"
- Preserve all UI state (assignments, messages) during offline period
- On reconnect: Show toast "Back online" and re-enable Send
- Never lose user's typed message due to network issues

---

## 8) Product requirements (quality bars)

### Performance
- First load should be fast and smooth on a typical laptop/kiosk.
- No heavy animation loops; avoid expensive canvas/WebGL for MVP.
- All motion must degrade with `prefers-reduced-motion`.

### Accessibility
- Full usability without drag & drop via click-to-assign + keyboard.
- Clear focus states for:
  - Agent list items
  - Slot rings
  - Chat input + send button
- Use semantic controls and ARIA where needed (e.g., “selected slot”).

### Reliability
- UI must not lock up if one slot errors/hangs.
- “Reset all” always returns UI to a known state.

---

## 9) Tech stack & implementation guidance

### Core stack
- **SvelteKit** (latest stable, v2.x)
- **Svelte 5** with Runes (see Runes guidance below)
- **TypeScript** (strict mode)
- **Tailwind CSS** (v4 or v3.4+)
- **shadcn-svelte** (selectively; keep usage minimal)
  - Note: shadcn-svelte now supports Svelte 5. Use the migration guide at https://shadcn-svelte.com/docs/migration/svelte-5

### Svelte 5 Runes guidance

Svelte 5 introduces Runes for explicit reactivity. Follow these patterns:

```svelte
<script lang="ts">
  // ✅ Use $state for reactive variables
  let slots = $state<Slot[]>(initialSlots);
  let selectedSlotId = $state<number | null>(null);
  let isSending = $state(false);

  // ✅ Use $derived for computed values (90% of cases)
  let assignedSlots = $derived(slots.filter(s => s.agentId !== null));
  let canSend = $derived(
    input.trim().length > 0 &&
    assignedSlots.length > 0 &&
    !isSending
  );

  // ✅ Use $effect for side effects (DOM updates, logging, external calls)
  $effect(() => {
    if (isSending) {
      console.log('Sending to slots:', assignedSlots.map(s => s.id));
    }
  });

  // ❌ Don't use $effect for derived values
  // Bad: $effect(() => { canSend = ...; })
</script>
```

**Key rules**:
- Prefer `$derived` over `$effect` (90% of the time you want `$derived`)
- `$state` works in `.svelte` and `.svelte.ts` files
- `$derived` is memoized and only recalculates when dependencies change
- `$effect` runs after DOM updates; return a cleanup function if needed

### UI component usage (keep lean)
Use shadcn-svelte for:
- Buttons, icon buttons
- Inputs / textarea
- Scroll area (if needed)
- Tooltips (optional)
- Toast notifications (for offline/online status)

Custom-build for:
- Speaker rings (circles) — core visual identity
- Agent palette styling (chips/cards)
- Response panels (to match the art direction)

### Drag & drop

**Recommended: `svelte-dnd-action`** (v0.9.54+)
- Actively maintained, supports Svelte 5
- Use `onconsider` and `onfinalize` (Svelte 5 event syntax)
- Full accessibility support with keyboard navigation

```svelte
<div
  use:dndzone={{ items: agents, type: 'agent' }}
  onconsider={handleConsider}
  onfinalize={handleFinalize}
>
  {#each agents as agent (agent.id)}
    <AgentCard {agent} />
  {/each}
</div>
```

**Alternative: `@thisux/sveltednd`**
- Built specifically for Svelte 5 with Runes
- Lighter weight, but less battle-tested

**Always implement click-to-assign fallback** regardless of DnD library choice.

### Icons
- `lucide-svelte` (or `@lucide/svelte` for Svelte 5)

### Styling approach
- Tailwind utilities for layout/spacing
- CSS custom properties for design tokens (colors, glows)
- `@apply` sparingly for reusable glow effects
- Use CSS `@media (prefers-reduced-motion: reduce)` to disable animations

---

## 10) Suggested app structure (front-end package)

This repo currently contains Python code. The front-end should live as a separate package:

```
reflective_resonance/
├── frontend/                      # SvelteKit app
│   ├── src/
│   │   ├── lib/
│   │   │   ├── components/
│   │   │   │   ├── AgentPalette.svelte
│   │   │   │   ├── AgentCard.svelte
│   │   │   │   ├── SpeakerSlots.svelte
│   │   │   │   ├── SpeakerSlotRing.svelte
│   │   │   │   ├── ChatDock.svelte
│   │   │   │   ├── ResponsesPanel.svelte
│   │   │   │   ├── ResponseCard.svelte
│   │   │   │   └── ui/              # shadcn-svelte components
│   │   │   │       ├── button/
│   │   │   │       ├── input/
│   │   │   │       └── ...
│   │   │   ├── stores/
│   │   │   │   └── app.svelte.ts    # Global state with runes
│   │   │   ├── types/
│   │   │   │   └── index.ts         # TypeScript types
│   │   │   ├── utils/
│   │   │   │   ├── mock-responses.ts
│   │   │   │   └── streaming.ts
│   │   │   └── config/
│   │   │       └── agents.ts        # Agent definitions
│   │   ├── routes/
│   │   │   ├── +page.svelte         # Main (only) page
│   │   │   └── +layout.svelte       # Global layout + styles
│   │   └── app.css                  # Global styles + design tokens
│   ├── static/
│   ├── tests/
│   │   ├── unit/                    # Vitest tests
│   │   └── e2e/                     # Playwright tests
│   ├── package.json
│   ├── svelte.config.js
│   ├── tailwind.config.js
│   ├── vite.config.ts
│   └── README.md                    # How to run, build, test
├── backend/                         # Python backend (future)
├── README.md
└── mvp-front-end-prd.md
```

The MVP should be implemented as **one screen** (single route), e.g. `/`.

---

## 11) State model (front-end)

Keep state explicit and serializable (for debugging and future backend parity).

### Core types (TypeScript)

```typescript
// src/lib/types/index.ts

export type AgentId = 'claude-sonnet-4-5' | 'claude-opus-4-5' | 'gpt-5.2' | 'gpt-5.1' | 'gpt-4o' | 'gemini-3';
export type SlotId = 1 | 2 | 3 | 4 | 5 | 6;
export type SlotStatus = 'idle' | 'streaming' | 'done' | 'error';
export type ErrorType = 'network' | 'timeout' | 'rate_limit' | 'server' | 'unknown';

export interface Agent {
  id: AgentId;
  label: string;                    // Display name, e.g., "Claude Sonnet 4.5"
  model: string;                    // Backend identifier
  provider: 'anthropic' | 'openai' | 'google';
  description: string;              // Brief tagline
  accentColor: string;              // Hex color for visual distinction
}

export interface Slot {
  id: SlotId;
  agentId: AgentId | null;
  status: SlotStatus;
  errorType?: ErrorType;
  retryCount: number;
}

export interface Message {
  id: string;                       // UUID
  role: 'user' | 'agent';
  slotId?: SlotId;                  // Only for agent messages
  agentId?: AgentId;                // Only for agent messages
  content: string;
  isStreaming: boolean;
  createdAt: number;                // Unix timestamp
  error?: {
    type: ErrorType;
    message: string;
  };
}

export interface AppState {
  slots: Slot[];
  messages: Message[];
  selectedSlotId: SlotId | null;
  inputValue: string;
  isSending: boolean;
  isOnline: boolean;
}

// Configuration constants
export interface AppConfig {
  REQUIRE_ALL_SLOTS: boolean;
  PERSIST_TO_LOCAL_STORAGE: boolean;
  MOCK_MODE: boolean;
  RESPONSE_TIMEOUT_MS: number;
  MAX_RETRIES: number;
}
```

### Derived state (using $derived)

```typescript
// In component or store
let assignedSlots = $derived(slots.filter(s => s.agentId !== null));
let emptySlots = $derived(slots.filter(s => s.agentId === null));
let hasAssignments = $derived(assignedSlots.length > 0);
let allSlotsAssigned = $derived(assignedSlots.length === 6);

let canSend = $derived(
  inputValue.trim().length > 0 &&
  hasAssignments &&
  !isSending &&
  isOnline
);

let streamingSlots = $derived(slots.filter(s => s.status === 'streaming'));
let errorSlots = $derived(slots.filter(s => s.status === 'error'));
let hasErrors = $derived(errorSlots.length > 0);

// Agent usage counts for palette badges
let agentUsageCounts = $derived(
  agents.reduce((acc, agent) => {
    acc[agent.id] = slots.filter(s => s.agentId === agent.id).length;
    return acc;
  }, {} as Record<AgentId, number>)
);
```

### Persistence (optional)

```typescript
// src/lib/stores/persistence.ts
const STORAGE_KEY = 'reflective-resonance-state';

export function saveState(state: Partial<AppState>) {
  if (!config.PERSIST_TO_LOCAL_STORAGE) return;
  localStorage.setItem(STORAGE_KEY, JSON.stringify({
    slots: state.slots,
    // Don't persist messages or isSending
  }));
}

export function loadState(): Partial<AppState> | null {
  if (!config.PERSIST_TO_LOCAL_STORAGE) return null;
  const stored = localStorage.getItem(STORAGE_KEY);
  return stored ? JSON.parse(stored) : null;
}
```

- Store `slots` mapping in `localStorage` so kiosk refresh doesn't wipe assignment.
- Do NOT persist: messages, isSending, selectedSlotId (transient state)
- Make this opt-in via `PERSIST_TO_LOCAL_STORAGE` constant.

---

## 12) Backend integration contract (future-proof, not implemented now)

Even though backend is out of scope, the UI should be built to integrate cleanly later.

### Proposed API contract

```typescript
// POST /api/chat
interface ChatRequest {
  slotId: SlotId;
  agentId: AgentId;
  message: string;
  threadId?: string;           // For conversation continuity
}

// Response: Server-Sent Events stream
// Event types:
// - 'token': { content: string }
// - 'done': { fullContent: string, usage?: { tokens: number } }
// - 'error': { type: ErrorType, message: string }
```

### Streaming implementation (SSE)

**Recommended: `sveltekit-sse`** library or native EventSource

```typescript
// src/lib/utils/streaming.ts
import { source } from 'sveltekit-sse';

export async function streamResponse(
  slotId: SlotId,
  agentId: AgentId,
  message: string,
  onToken: (token: string) => void,
  onDone: () => void,
  onError: (error: Error) => void
) {
  const connection = source('/api/chat', {
    options: {
      method: 'POST',
      body: JSON.stringify({ slotId, agentId, message }),
    },
  });

  connection.select('token').subscribe((token) => {
    onToken(JSON.parse(token).content);
  });

  connection.select('done').subscribe(() => {
    onDone();
  });

  connection.select('error').subscribe((error) => {
    onError(new Error(JSON.parse(error).message));
  });

  return connection;
}
```

### MVP mocking strategy (must-have)

Implement a robust mock mode for frontend-only development:

```typescript
// src/lib/utils/mock-responses.ts

const MOCK_RESPONSES: Record<AgentId, string[]> = {
  'claude-sonnet-4-5': [
    "I appreciate your question. Let me think about this carefully...",
    "That's an interesting perspective. Here's what I think...",
    // More varied responses
  ],
  // ... other agents
};

interface MockConfig {
  minDelayMs: number;          // 200
  maxDelayMs: number;          // 1500
  tokenDelayMs: number;        // 30-80 (per token)
  errorRate: number;           // 0.05 (5% chance of error in dev)
  deterministicMode: boolean;  // For tests
}

export async function mockStreamResponse(
  slotId: SlotId,
  agentId: AgentId,
  message: string,
  config: MockConfig,
  onToken: (token: string) => void,
  onDone: () => void,
  onError: (error: Error) => void
) {
  // Initial delay (simulates network + model warmup)
  await delay(randomBetween(config.minDelayMs, config.maxDelayMs));

  // Simulate error (for testing error handling)
  if (!config.deterministicMode && Math.random() < config.errorRate) {
    onError(new Error('Simulated network error'));
    return;
  }

  // Pick a response
  const response = config.deterministicMode
    ? MOCK_RESPONSES[agentId][0]
    : pickRandom(MOCK_RESPONSES[agentId]);

  // Stream token by token
  const tokens = response.split(' ');
  for (const token of tokens) {
    await delay(randomBetween(30, 80));
    onToken(token + ' ');
  }

  onDone();
}
```

**Mock mode activation**:
- Set via environment variable: `PUBLIC_MOCK_MODE=true`
- Or via URL param for quick testing: `?mock=true`
- Always use deterministic mode in Playwright tests

---

## 13) Detailed UI spec (component-level)

### `AgentPalette`

**Purpose**: Display the 6 available agents for assignment.

**Props**:
```typescript
interface AgentPaletteProps {
  agents: Agent[];
  usageCounts: Record<AgentId, number>;
  selectedSlotId: SlotId | null;
  onAgentClick: (agentId: AgentId) => void;
}
```

**Behavior**:
- Renders 6 agents in a vertical list
- Each item is draggable (using `svelte-dnd-action`)
- Click on agent → assigns to selected slot (if any)
- Shows usage count badge when agent is assigned to ≥1 slot
- Visual states: default, hover, dragging, disabled (if no slot selected for click-assign)

**Accessibility**:
- `role="listbox"` on container
- `role="option"` on each agent
- `aria-selected` when agent matches selected slot's agent
- Keyboard: Arrow keys to navigate, Enter to select

### `AgentCard`

**Purpose**: Individual agent item in the palette.

**Content**:
```
┌─────────────────────────────────┐
│ ● Claude Sonnet 4.5        ×2  │  ← Accent dot + name + usage badge
│   Anthropic · Fast responses   │  ← Provider + description
└─────────────────────────────────┘
```

### `SpeakerSlots`

**Purpose**: Container for the 6 speaker slot rings.

**Props**:
```typescript
interface SpeakerSlotsProps {
  slots: Slot[];
  agents: Agent[];
  selectedSlotId: SlotId | null;
  onSlotClick: (slotId: SlotId) => void;
  onSlotClear: (slotId: SlotId) => void;
  onAgentDrop: (slotId: SlotId, agentId: AgentId) => void;
}
```

**Layout**: 2×3 grid (CSS Grid recommended)

### `SpeakerSlotRing`

**Purpose**: Individual speaker slot with visual states.

**Visual states**:

| State | Ring Style | Inner Content | Animation |
|-------|------------|---------------|-----------|
| Empty | Dashed border, faint glow | "Speaker N" | Subtle pulse (first slot only, on first load) |
| Hover (drop target) | Brighter glow, scale 1.02 | "Drop here" | - |
| Selected | Strong glow, inner ring | "Speaker N" | - |
| Assigned | Solid border, agent-colored glow | Agent label | - |
| Streaming | Agent glow + shimmer | "Responding..." | Slow opacity pulse |
| Error | Red accent dot | Agent label + ⚠️ | - |

**Interactions**:
- Click → select/deselect slot
- Drop → assign agent
- Clear button (X icon, appears on hover when assigned)

**Accessibility**:
- `role="button"`
- `aria-pressed` for selected state
- `aria-label="Speaker 1, assigned to Claude Sonnet 4.5"`

### `ChatDock`

**Purpose**: Fixed bottom input area for sending messages.

**Props**:
```typescript
interface ChatDockProps {
  value: string;
  canSend: boolean;
  isSending: boolean;
  isOnline: boolean;
  onSend: () => void;
  onClear: () => void;
  onValueChange: (value: string) => void;
}
```

**Layout**:
```
┌─────────────────────────────────────────────────────────────────┐
│  ┌─────────────────────────────────────────────────┐  ┌──────┐ │
│  │ Type your message...                            │  │ Send │ │
│  │                                                 │  └──────┘ │
│  └─────────────────────────────────────────────────┘   🗑️      │
└─────────────────────────────────────────────────────────────────┘
```

**Behavior**:
- Textarea auto-grows from 1 to 4 lines
- Send button disabled when `!canSend`
- Shows loading indicator when `isSending`
- Shows offline indicator when `!isOnline`
- Clear button (trash icon) clears conversation (with inline confirm)

**Keyboard**:
- `Enter` → send (if canSend)
- `Shift + Enter` → new line
- `Escape` → blur input

### `ResponsesPanel`

**Purpose**: Display responses from all assigned slots.

**Props**:
```typescript
interface ResponsesPanelProps {
  messages: Message[];
  slots: Slot[];
  agents: Agent[];
  onRetry: (slotId: SlotId) => void;
  onRetryAll: () => void;
}
```

**Layout**: Vertical scroll, one `ResponseCard` per slot's latest response.

**Empty state**: "Responses will appear here" with subtle illustration.

### `ResponseCard`

**Purpose**: Display a single slot's response.

**Content**:
```
┌─────────────────────────────────────────┐
│ ● Speaker 3 · Claude Sonnet 4.5    ✓   │  ← Header with status
│ ─────────────────────────────────────── │  ← Accent bar
│                                         │
│ Response text streams in here...        │  ← Content (streaming or complete)
│                                         │
│ [Show more]                ⟳ Retry      │  ← Actions (conditional)
└─────────────────────────────────────────┘
```

**Visual states**:
- Streaming: Content updates in real-time, spinner in header
- Complete: Checkmark in header, "Show more" if truncated
- Error: Warning icon, error message, Retry button

---

## 14) Testing plan (how we ensure it works)

### 14.1 Manual testing checklist (MVP acceptance)

**Assignment**
- [ ] Drag agent to empty slot assigns correctly
- [ ] Drag agent to occupied slot replaces correctly
- [ ] Click-to-assign works: select slot → click agent assigns
- [ ] Clear slot removes assignment (X button)
- [ ] Reset all clears all slots (with confirmation)
- [ ] Keyboard: Press 1-6 to select slot, then click agent
- [ ] Keyboard: Escape clears slot selection

**Chat**
- [ ] Send disabled when input empty
- [ ] Send disabled when no slots assigned
- [ ] Chat dock appears/enables when ≥1 slot assigned
- [ ] Sending dispatches to all assigned slots (verify in mock mode)
- [ ] Responses appear as they complete (order may differ)
- [ ] Streaming animation visible on active slots
- [ ] One slot error does not block others
- [ ] Retry works for a failed slot
- [ ] "Retry all failed" appears when ≥2 slots error
- [ ] Send button disabled while responses streaming

**Empty state & guidance**
- [ ] First load shows guidance text
- [ ] Guidance updates after first assignment
- [ ] Guidance disappears after first message sent
- [ ] Empty response panel shows placeholder

**UX / Visual**
- [ ] Dark theme + neon accents present
- [ ] Hover/active/streaming states visible but subtle
- [ ] Agent accent colors distinguish responses
- [ ] `prefers-reduced-motion` disables shimmer/pulse animations

**Responsiveness (desktop)**
- [ ] Works at 1280×800 (kiosk minimum)
- [ ] Works at 1440×900 (common laptop)
- [ ] Works at 1920×1080 (full HD)
- [ ] Shows warning below 1024px width

**Keyboard & accessibility**
- [ ] Tab navigation through all interactive elements
- [ ] Focus indicators visible
- [ ] Screen reader announces slot states
- [ ] All functionality accessible without mouse

**Error & offline handling**
- [ ] Offline toast appears when network lost
- [ ] Send button disabled when offline
- [ ] Reconnect toast appears when back online
- [ ] Partial response preserved on mid-stream disconnect

### 14.2 Automated tests

**Unit tests (Vitest + Testing Library)**

```typescript
// Example test cases
describe('State logic', () => {
  it('assignedSlots filters correctly');
  it('canSend is false when input empty');
  it('canSend is false when no slots assigned');
  it('canSend is false when isSending');
  it('canSend is true when all conditions met');
});

describe('Slot assignment', () => {
  it('assigns agent to empty slot');
  it('replaces agent in occupied slot');
  it('clears slot assignment');
  it('tracks agent usage counts correctly');
});

describe('Mock streaming', () => {
  it('emits tokens at realistic intervals');
  it('calls onDone after all tokens');
  it('calls onError when error rate triggers');
});
```

**E2E tests (Playwright)**

```typescript
// Example E2E scenarios
test('click-to-assign flow', async ({ page }) => {
  await page.goto('/');
  await page.click('[data-slot="1"]');  // Select slot 1
  await page.click('[data-agent="claude-sonnet-4-5"]');  // Assign agent
  await expect(page.locator('[data-slot="1"]')).toContainText('Claude Sonnet');
});

test('send message and receive 6 responses', async ({ page }) => {
  // Assign all 6 slots
  // Type message
  // Click send
  // Verify all 6 response cards appear
});

test('error and retry', async ({ page }) => {
  // Force error on slot 3
  // Verify error state
  // Click retry
  // Verify success
});
```

### 14.3 Performance sanity checks

**Lighthouse targets (informal)**:
- Performance: >80
- Accessibility: >90
- Best Practices: >90
- No layout shift in primary UI region
- First Contentful Paint <1.5s

**Bundle size targets**:
- Initial JS: <150KB gzipped
- Total assets: <500KB gzipped

---

## 15) Acceptance criteria (definition of done)

MVP front-end is "done" when:

**Core functionality**
- [ ] Users can assign any of the 6 agents to any of the 6 slots (duplicates allowed)
- [ ] Users can message and receive up to 6 concurrent responses, visible per slot
- [ ] The UI works without drag-and-drop via click-to-assign (accessibility)
- [ ] Mock mode exists so frontend can be demoed without backend

**Visual & UX**
- [ ] The UI is minimalist and visually aligned with the installation (dark + neon glow rings)
- [ ] Empty state provides clear guidance for first-time users
- [ ] Response cards clearly identify which slot/agent they belong to
- [ ] All visual states (empty, hover, selected, streaming, error) are implemented

**Quality**
- [ ] No blocking errors in console
- [ ] Keyboard navigation works for all core flows
- [ ] `prefers-reduced-motion` respected
- [ ] Works on screens ≥1024px wide

**Code quality**
- [ ] The codebase remains lean: minimal dependencies, simple state, single-page flow
- [ ] TypeScript strict mode with no type errors
- [ ] Core state logic has unit tests
- [ ] At least one E2E test covers the happy path

---

## 16) Delivery plan (suggested milestones)

| Milestone | Focus | Deliverables |
|-----------|-------|--------------|
| **M1** | Project scaffold | SvelteKit + Tailwind + shadcn-svelte setup, design tokens in CSS, static layout skeleton, README with dev instructions |
| **M2** | Slot assignment | State model with Svelte 5 runes, DnD with `svelte-dnd-action`, click-to-assign fallback, slot visual states, agent palette with usage counts |
| **M3** | Chat & responses | Chat dock component, mock streaming implementation, response panel with cards, concurrent response handling |
| **M4** | Error & edge cases | Error states with retry, offline detection, keyboard shortcuts, empty state guidance |
| **M5** | Polish & testing | Animation refinements, accessibility audit, unit tests, Playwright smoke tests, performance check |

---

## 17) Glossary

| Term | Definition |
|------|------------|
| **Agent** | An LLM model (e.g., Claude Sonnet 4.5) that can respond to messages |
| **Slot** | One of 6 speaker positions that can be assigned to an agent |
| **Ring** | The circular UI element representing a speaker slot |
| **Palette** | The left sidebar showing available agents for assignment |
| **Streaming** | Token-by-token display of an agent's response as it's generated |
| **Mock mode** | Frontend-only mode that simulates agent responses for development |
| **Runes** | Svelte 5's reactivity primitives ($state, $derived, $effect) |

---

## 18) References

- [Svelte 5 Runes documentation](https://svelte.dev/docs/svelte/$state)
- [shadcn-svelte Svelte 5 migration](https://shadcn-svelte.com/docs/migration/svelte-5)
- [svelte-dnd-action](https://github.com/isaacHagoel/svelte-dnd-action)
- [sveltekit-sse for streaming](https://github.com/razshare/sveltekit-sse)
- [WCAG 2.2 Dragging Movements](https://www.w3.org/WAI/WCAG22/Understanding/dragging-movements.html)
- [W3C ARIA Authoring Practices](https://www.w3.org/WAI/ARIA/apg/practices/keyboard-interface/)
- [Reflective Resonance Instructables](https://www.instructables.com/Reflective-Resonance/)


