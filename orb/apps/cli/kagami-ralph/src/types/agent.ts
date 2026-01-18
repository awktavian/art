/**
 * Type definitions for Ralph AI training agents
 */

export type AgentStatus =
  | 'idle'
  | 'starting'
  | 'running'
  | 'thinking'
  | 'consensus'
  | 'success'
  | 'warning'
  | 'error'
  | 'complete';

export interface AgentState {
  readonly id: number;
  readonly name: string;
  score: number;
  status: AgentStatus;
  message: string;
  vote: boolean | null;
  lastUpdate: number;
}

export interface AgentPhysics {
  x: number;
  y: number;
  vx: number;
  vy: number;
}

export interface ByzantineVote {
  readonly agentId: number;
  vote: boolean;
  score: number;
  readonly timestamp: number;
}

export interface ConsensusRound {
  readonly roundId: number;
  phase: 'PRE_VOTE' | 'PRE_COMMIT' | 'COMMIT';
  votes: ByzantineVote[];
  readonly quorum: number;
  readonly threshold: number;
}

export interface TrainingMetrics {
  step: number;
  loss: number;
  phase: string;
  receipts: number;
  validations: number;
  uptime: number;
}

export interface RalphMessage {
  type: 'agent_update' | 'consensus_update' | 'metrics_update' | 'error';
  data: AgentState | ConsensusRound | TrainingMetrics | Error;
  timestamp: number;
}
