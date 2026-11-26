import type { Metadata, Viewport } from 'next'
import { AuthProvider } from '@/lib/auth'
import { SiteChrome } from '@/components/site-chrome'
import { ThemeProvider } from '@/lib/theme'
import { CityProvider } from '@/lib/city'
import './globals.css'
import './secondary-pages.css'

export const metadata: Metadata = {
  title: 'ДОСУГ — городская газета о досуге',
  description: 'События, места и впечатления Минска. Найдите, куда пойти сегодня.',
  icons: {
    icon: [
      { url: '/icon-light-32x32.png', media: '(prefers-color-scheme: light)' },
      { url: '/icon-dark-32x32.png', media: '(prefers-color-scheme: dark)' },
      { url: '/icon.svg', type: 'image/svg+xml' },
    ],
    apple: '/apple-icon.png',
  },
}

export const viewport: Viewport = {
  colorScheme: 'light dark',
  themeColor: [
    { media: '(prefers-color-scheme: light)', color: 'white' },
    { media: '(prefers-color-scheme: dark)', color: 'black' },
  ],
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="ru" suppressHydrationWarning>
      <head>
        <script
          // Apply the saved theme before paint to avoid a light-theme flash.
          dangerouslySetInnerHTML={{
            __html:
              "try{var t=localStorage.getItem('dosugTheme');if(t==='dark'||(!t&&window.matchMedia('(prefers-color-scheme: dark)').matches)){document.documentElement.classList.add('dark-mode')}}catch(e){}",
          }}
        />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,500;0,600;0,700;1,500;1,600&family=PT+Serif:wght@400;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="antialiased">
        <ThemeProvider>
          <CityProvider>
            <AuthProvider>
              <SiteChrome>{children}</SiteChrome>
            </AuthProvider>
          </CityProvider>
        </ThemeProvider>
      </body>
    </html>
  )
}
