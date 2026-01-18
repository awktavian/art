import type { Metadata } from 'next'

// Generate metadata for journey pages
export async function generateMetadata({
  params,
}: {
  params: { id: string }
}): Promise<Metadata> {
  // In production, fetch journey data to get the name
  return {
    title: `Journey ${params.id}`,
    description: 'View user journey test details and video playback',
  }
}

export default function JourneyLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return children
}
