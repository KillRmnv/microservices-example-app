import Link from 'next/link'

export function SiteFooter() {
  return (
    <footer className="site-footer" data-testid="site-footer">
      <div className="site-footer-inner">
        <span className="site-footer-copy">© 2026 «Досуг» · городская газета о досуге</span>
        <nav className="site-footer-links" aria-label="Подвал сайта">
          <Link href="/events">События</Link>
          <Link href="/places">Места</Link>
          <Link href="/about">О проекте</Link>
        </nav>
        <span className="site-footer-edition">№ 014 · МИНСК · СВЕЖИЙ ВЫПУСК</span>
      </div>
    </footer>
  )
}
