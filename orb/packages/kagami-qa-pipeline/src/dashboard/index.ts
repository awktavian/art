/**
 * @fileoverview Dashboard Module Exports
 *
 * Publishing and visualization capabilities for Byzantine quality metrics.
 */

export {
  CIPublisher,
  getPublisher,
  publishCIResults,
  createPayloadFromResults,
} from './ci-publisher.js';

export type {
  ByzantineScores,
  CIAnalysisPayload,
  DashboardConfig,
  TrendDataPoint,
} from './ci-publisher.js';
