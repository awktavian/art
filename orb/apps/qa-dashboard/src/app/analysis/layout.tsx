import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Analysis',
  description: 'AI-detected issues and recommendations across all tests',
}

export default function AnalysisLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return children
}
