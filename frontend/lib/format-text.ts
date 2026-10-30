/** Turn scraped one-line descriptions into readable paragraphs. */

function decodeEntities(raw: string): string {
  if (typeof document === 'undefined') return raw
  const el = document.createElement('textarea')
  el.innerHTML = raw
  return el.value
}

const BLOCK_TAG = /<\s*\/?\s*(?:p|div|li|h[1-6]|section|article|br)\b[^>]*>/gi
const ANY_TAG = /<[^>]+>/g

function splitSentences(text: string): string[] {
  // Protect common abbreviations so "г. Минск" / "им. Купалы" stay intact.
  const guarded = text
    .replace(/\bг\.\s/g, 'г\u0000 ')
    .replace(/\bим\.\s/g, 'им\u0000 ')
    .replace(/\bт\.\s?е\.\s/g, 'т\u0000 ')
    .replace(/\bдр\.\s/g, 'др\u0000 ')
  const parts = guarded.match(/[^.!?]+[.!?]+(?:["»”']?)|[^.!?]+$/g) ?? [guarded]
  return parts.map((part) => part.replace(/\u0000/g, '. ').trim()).filter(Boolean)
}

function groupParagraphs(sentences: string[]): string[] {
  const paragraphs: string[] = []
  let buffer: string[] = []
  for (const sentence of sentences) {
    buffer.push(sentence)
    if (buffer.length >= 3) {
      paragraphs.push(buffer.join(' '))
      buffer = []
    }
  }
  if (buffer.length) paragraphs.push(buffer.join(' '))
  return paragraphs
}

export function formatDescription(raw?: string | null): string[] {
  if (!raw) return []
  let text = decodeEntities(raw)
    .replace(/\r\n?/g, '\n')
    .replace(BLOCK_TAG, '\n')
    .replace(ANY_TAG, ' ')
    .replace(/\u00a0/g, ' ')
    .replace(/[ \t]+/g, ' ')
    .replace(/\n[ \t]+/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim()

  if (!text) return []
  const blocks = text.split(/\n+/).map((block) => block.trim()).filter(Boolean)
  if (blocks.length > 1) {
    // Source already has structure; keep it but still wrap very long blocks.
    return blocks.flatMap((block) => block.length > 700
      ? groupParagraphs(splitSentences(block))
      : [block])
  }
  return groupParagraphs(splitSentences(blocks[0]))
}
