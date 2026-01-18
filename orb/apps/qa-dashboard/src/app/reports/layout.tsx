import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Reports',
  description: 'Generate and export QA reports',
}

export default function ReportsLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return children
}
