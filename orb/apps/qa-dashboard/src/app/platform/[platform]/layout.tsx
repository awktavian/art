import type { Metadata } from 'next'
import type { Platform } from '@/types'

// Generate metadata for platform pages
export async function generateMetadata({
  params,
}: {
  params: { platform: Platform }
}): Promise<Metadata> {
  const platformNames: Record<Platform, string> = {
    ios: 'iOS',
    android: 'Android',
    'android-xr': 'Android XR',
    visionos: 'visionOS',
    watchos: 'watchOS',
    tvos: 'tvOS',
    desktop: 'Desktop',
    hub: 'Hub',
  }

  const name = platformNames[params.platform] || params.platform

  return {
    title: name,
    description: `View all user journey tests for ${name}`,
  }
}

export default function PlatformLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return children
}
