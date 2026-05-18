export function simpleMarkdown(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/### (.+)/g, '<h4>$1</h4>')
    .replace(/## (.+)/g, '<h3>$1</h3>')
    // Convert list items, then group consecutive ones into <ul>
    .replace(/^- (.+)/gm, '<li>$1</li>')
    .replace(/((?:<li>.*?<\/li>)(?:\n<li>.*?<\/li>)*)/g, '<ul>\n$1\n</ul>')
    .replace(/\n/g, '<br/>')
}
