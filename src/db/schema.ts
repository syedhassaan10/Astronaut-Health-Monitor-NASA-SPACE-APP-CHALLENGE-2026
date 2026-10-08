import type { ExerciseId } from '../engine/gravityEngine'
import type { CheckIn } from '../engine/healthTypes'

export interface CrewRow {
  id: string
  name: string
  role: string
  massKg: number
}

export type SessionStatus = 'active' | 'completed'
export type SessionSource = 'webcam' | 'video' | 'demo-seed' | 'import'

/** One workout session. `active` means it was never closed (e.g. the tab was closed mid-set). */
export interface SessionRow {
  id: string
  crewId: string
  exercise: ExerciseId
  /** Mission day the session counts for. */
  day: number
  gravityG: number
  targetLoadKg: number
  prescribedReps: number
  status: SessionStatus
  startedAt: number
  endedAt: number | null
  source: SessionSource
}

/** One rep, written to IndexedDB the moment it completes. id = `${sessionId}#${repNo}`. */
export interface RepRow {
  id: string
  sessionId: string
  crewId: string
  exercise: ExerciseId
  /** Epoch ms when the rep completed. */
  timestamp: number
  gravityG: number
  targetLoadKg: number
  repNo: number
  minKneeAngle: number
  eccentricS: number
  concentricS: number
  /** Mean |left - right| knee angle, degrees. */
  asymmetry: number
  confidence: number
  formScore: number
  flags: string[]
  level: 'green' | 'amber' | 'red'
}

export type { CheckIn }

/** Alert log entry: written when an alert first appears (or escalates). key = `${alertId}|${level}`. */
export interface AlertRow {
  key: string
  crewId: string
  exercise: ExerciseId | null
  rule: string
  level: 'WATCH' | 'ACT'
  title: string
  summary: string
  /** Mission day it was first raised. */
  day: number
  raisedAt: number
  acknowledged: boolean
}

/**
 * A packet waiting for, in, or past the (simulated) Earth downlink. Persisted so a queued
 * packet survives reloads. The packet itself is stored as JSON in `payload`.
 */
export interface QueueRow {
  id: string
  createdAt: number
  /** queued = waiting for a comms window; sent = in transit / awaiting ACK; acked = Earth confirmed. */
  status: 'queued' | 'sent' | 'acked'
  payload: string
  sizeBytes: number
  missionDay: number
  /** When the current attempt started, and when the packet reaches Earth (simulated delay). */
  sentAt: number | null
  deliverAt: number | null
  /** Set once the packet has actually been broadcast. */
  transmittedAt: number | null
  ackedAt: number | null
  attempts: number
}

export interface NoteRow {
  crewId: string
  text: string
  updatedAt: number
}
