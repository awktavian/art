import type { Metadata, Viewport } from 'next'
import { Inter, Cormorant_Garamond } from 'next/font/google'
import '@/styles/globals.css'
import { Providers } from './providers'
import { Header, AmbientCanvas } from '@/components/layout'

const inter = Inter({
  subsets: ['latin'],
  display: 'swap',
  variable: '--font-inter',
})

const cormorant = Cormorant_Garamond({
  subsets: ['latin'],
  weight: ['400', '500', '600', '700'],
  display: 'swap',
  variable: '--font-cormorant',
})

export const metadata: Metadata = {
  title: {
    template: '%s | Kagami QA Dashboard',
    default: 'Kagami QA Dashboard',
  },
  description: 'High-craft QA Dashboard for user journey test videos. Monitor, analyze, and improve your test automation across all platforms.',
  keywords: ['QA', 'testing', 'automation', 'dashboard', 'video', 'Kagami'],
  authors: [{ name: 'Kagami' }],
  creator: 'Kagami',
  metadataBase: new URL('https://qa.kagami.dev'),
  openGraph: {
    type: 'website',
    locale: 'en_US',
    url: 'https://qa.kagami.dev',
    title: 'Kagami QA Dashboard',
    description: 'High-craft QA Dashboard for user journey test videos',
    siteName: 'Kagami QA',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Kagami QA Dashboard',
    description: 'High-craft QA Dashboard for user journey test videos',
  },
  robots: {
    index: true,
    follow: true,
  },
}

export const viewport: Viewport = {
  themeColor: [
    { media: '(prefers-color-scheme: dark)', color: '#0A0A0F' },
    { media: '(prefers-color-scheme: light)', color: '#FAFAFC' },
  ],
  width: 'device-width',
  initialScale: 1,
  maximumScale: 5,
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className={`${inter.variable} ${cormorant.variable} dark`} suppressHydrationWarning>
      <head>
        <link rel="icon" href="/favicon.ico" sizes="any" />
        <link rel="icon" href="/icon.svg" type="image/svg+xml" />
        <link rel="apple-touch-icon" href="/apple-touch-icon.png" />
        <link rel="manifest" href="/manifest.json" />
      </head>
      <body className="min-h-screen bg-void text-white antialiased font-sans">
        <AmbientCanvas />
        <Providers>
          <Header />
          <main id="main-content" className="relative z-10 min-h-[calc(100vh-4rem)]">
            {children}
          </main>
        </Providers>
      </body>
    </html>
  )
}
