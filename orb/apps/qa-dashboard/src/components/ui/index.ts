/**
 * Kagami QA Dashboard - UI Components Index
 *
 * Export all UI components from a single entry point.
 */

// Status badges
export { StatusBadge, SeverityBadge, HealthBadge } from './status-badge'

// Button
export { Button, IconButton } from './button'

// Card
export {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
  CardSkeleton,
} from './card'

// Progress
export { Progress, CircularProgress, HealthRing } from './progress'

// Accessibility
export { LiveRegion, StatusAnnouncer, announce } from './live-region'

// Delight
export {
  CelebrationCanvas,
  SuccessCheckmark,
  getPersonalityMessage,
  PERSONALITY_MESSAGES,
} from './celebration'
