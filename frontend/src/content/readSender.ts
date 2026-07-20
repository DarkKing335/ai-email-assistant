/**
 * Read the sender of the Gmail thread currently on screen.
 *
 * ⚠️ **Gmail's DOM is undocumented, obfuscated and changes without notice.**
 * Every selector here is an observed pattern, not a contract. The strategies
 * are ordered most-to-least durable and tried in turn, so one of them breaking
 * degrades the feature rather than killing it. When quick-add stops finding
 * senders, this file is the thing to fix.
 *
 * The function is pure with respect to the document — it reads, never writes —
 * so it can be exercised against a synthetic DOM.
 */

export type ReadResult =
  | { found: true; email: string; name: string | null; subject: string | null; strategy: string }
  | { found: false; reason: string }

/** Cheap sanity check; the backend's guardrail is the real validator. */
function looksLikeEmail(value: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)
}

function normalize(value: string | null | undefined): string | null {
  const trimmed = value?.trim()
  return trimmed ? trimmed : null
}

/**
 * Gmail renders the subject in an `h2` carrying a thread id. The `hP` class is
 * the long-standing fallback for the same element.
 */
function readSubject(root: ParentNode): string | null {
  const node =
    root.querySelector('h2[data-thread-perm-id]') ??
    root.querySelector('h2.hP') ??
    root.querySelector('.hP')
  return normalize(node?.textContent)
}

/**
 * The most recent *expanded* message in the thread.
 *
 * A thread renders collapsed messages too; their headers are in the DOM but are
 * not what the reader is looking at. Gmail marks collapsed rows with `.kv` /
 * `.kQ`, and expanded ones contain a `.adn` body wrapper — the presence of the
 * body is the more reliable signal.
 */
function findOpenMessage(root: ParentNode): Element | null {
  const messages = Array.from(root.querySelectorAll('[data-message-id]'))
  if (messages.length === 0) return null

  const expanded = messages.filter((message) => message.querySelector('.adn'))
  const candidates = expanded.length > 0 ? expanded : messages

  // Last in document order is the newest message in the thread.
  return candidates[candidates.length - 1] ?? null
}

/**
 * Pull an address out of a message header.
 *
 * Deliberately scoped to the header region: a message *body* frequently quotes
 * other addresses (forwarded mail, signatures), and picking one of those would
 * whitelist the wrong person — a silent, consequential mistake.
 */
function senderFromMessage(message: Element): {
  email: string
  name: string | null
  strategy: string
} | null {
  // 1. `.gD` is Gmail's sender-name span and carries the address in an
  //    `email` attribute. The most specific signal available.
  const gD = message.querySelector('span.gD[email]')
  if (gD) {
    const email = gD.getAttribute('email')
    if (email && looksLikeEmail(email)) {
      return {
        email,
        name: normalize(gD.getAttribute('name')) ?? normalize(gD.textContent),
        strategy: 'span.gD[email]',
      }
    }
  }

  // 2. Any `span[email]` inside the header block. `.gE`/`.iw` wrap the
  //    from/to region; the first address there is the sender.
  const header = message.querySelector('.gE, .iw, .adn .gE')
  const headerSpan = (header ?? message).querySelector('span[email]')
  if (headerSpan) {
    const email = headerSpan.getAttribute('email')
    if (email && looksLikeEmail(email)) {
      return {
        email,
        name:
          normalize(headerSpan.getAttribute('name')) ??
          normalize(headerSpan.textContent),
        strategy: 'span[email] in header',
      }
    }
  }

  // 3. Hovercards. Newer Gmail attaches `data-hovercard-id` to person chips.
  const hovercard = message.querySelector('[data-hovercard-id]')
  if (hovercard) {
    const email = hovercard.getAttribute('data-hovercard-id')
    if (email && looksLikeEmail(email)) {
      return {
        email,
        name: normalize(hovercard.textContent),
        strategy: 'data-hovercard-id',
      }
    }
  }

  return null
}

export function readCurrentSender(root: ParentNode = document): ReadResult {
  const message = findOpenMessage(root)

  if (message) {
    const sender = senderFromMessage(message)
    if (sender) {
      return {
        found: true,
        email: sender.email.toLowerCase(),
        name: sender.name,
        subject: readSubject(root),
        strategy: sender.strategy,
      }
    }
  }

  // 4. Last resort: no message container matched, so search the document for a
  //    sender span. Weaker — it can pick up a list row rather than an open
  //    thread — but better than nothing when Gmail reshuffles its containers.
  const loose = root.querySelector('span.gD[email]')
  if (loose) {
    const email = loose.getAttribute('email')
    if (email && looksLikeEmail(email)) {
      return {
        found: true,
        email: email.toLowerCase(),
        name: normalize(loose.getAttribute('name')) ?? normalize(loose.textContent),
        subject: readSubject(root),
        strategy: 'document-wide span.gD[email]',
      }
    }
  }

  return {
    found: false,
    reason: message
      ? 'Found an open message but no sender address in its header.'
      : 'No open thread on screen.',
  }
}
