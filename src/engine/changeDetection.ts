import { HEALTH_RULES, type HealthRulesConfig } from '../config/healthRules'
import type { ExerciseId } from './gravityEngine'
import type {
  Alert, Baseline, CrewAssessment, ExerciseAssessment, RuleId, SeriesPoint, SessionMetrics, SessionRecord, Status,
} from './healthTypes'
import { median, summarizeSession } from './sessionMetrics'

type Level = Exclude<Status, 'NOMINAL'>
const RANK: Record<Status, number> = { NOMINAL: 0, WATCH: 1, ACT: 2 }
export const worstStatus = (...s: Status[]): Status => s.reduce((a, b) => (RANK[b] > RANK[a] ? b : a), 'NOMINAL' as Status)

/** Maps a "how much worse than baseline" value to a level (higher value = worse). */
export function levelFor(deterioration: number, t: { watch: number; act: number }): Level | null {
  if (!Number.isFinite(deterioration)) return null
  if (deterioration >= t.act) return 'ACT'
  if (deterioration >= t.watch) return 'WATCH'
  return null
}

/** Baseline = median of the first N usable sessions (low-confidence / too-short sessions excluded). */
export function computeBaseline(usable: SessionMetrics[], cfg: HealthRulesConfig = HEALTH_RULES): Baseline | null {
  const first = usable.slice(0, cfg.baselineSessions)
  if (first.length < cfg.baselineSessions) return null
  return {
    depthDeg: median(first.map((m) => m.depthDeg)),
    concentricS: median(first.map((m) => m.concentricS)),
    asymmetryDeg: median(first.map((m) => m.asymmetryDeg)),
    variabilityDeg: median(first.map((m) => m.variabilityDeg)),
    gravityG: median(first.map((m) => m.gravityG)),
    days: first.map((m) => m.day),
  }
}

interface RuleText {
  title: string
  metric: string
  unit: string
  why: string
  sourceId: string
  actions: Record<Level, string[]>
}

// Wording rules: "estimate", "trend", "decision support"; never "diagnosis".
const TEXT: Record<Exclude<RuleId, 'escalation'>, RuleText> = {
  depth: {
    title: 'Squat depth trend is getting shallower',
    metric: 'Bottom knee angle (median)',
    unit: '°',
    why: 'Less depth can reflect reduced strength or range of motion as muscle is unloaded in microgravity. This is a camera-based kinematic estimate, not a measurement of muscle or bone.',
    sourceId: 'hrp-muscle-bone',
    actions: {
      WATCH: [
        'Repeat the measurement next session with the camera re-positioned (side or front, hips to ankles in view).',
        'Re-check the simulated target load and tempo for the current gravity.',
      ],
      ACT: [
        'Consult the Crew Medical Officer about the depth trend.',
        'Reduce the simulated load and restore full depth before progressing again.',
      ],
    },
  },
  concentric: {
    title: 'Lifting phase is slowing',
    metric: 'Concentric duration (median)',
    unit: 's',
    why: 'A slower lifting phase is a simple proxy for lower power output, which falls with muscle unloading and fatigue. Treat it as a trend estimate.',
    sourceId: 'hrp-muscle-bone',
    actions: {
      WATCH: ['Repeat the measurement and check sleep and fatigue in the daily check-in.', 'Keep load steady; avoid adding volume until the trend settles.'],
      ACT: ['Consult the Crew Medical Officer about the power trend.', 'Lower the simulated load and rebuild tempo before increasing it.'],
    },
  },
  asymmetry: {
    title: 'Left/right asymmetry is rising',
    metric: 'Mean left/right knee-angle difference',
    unit: '°',
    why: 'Growing left/right differences can point to compensation, discomfort or uneven loading, which matters when working under high resistive-exercise loads.',
    sourceId: 'hrp-muscle-bone',
    actions: {
      WATCH: ['Repeat the measurement with the camera centred, then watch foot placement and weight shift.', 'Log any pain or discomfort in the daily check-in.'],
      ACT: ['Consult the Crew Medical Officer before the next loaded session.', 'Reduce the simulated load and use a slower, controlled tempo.'],
    },
  },
  variability: {
    title: 'Rep-to-rep consistency is dropping',
    metric: 'Depth variability (SD across reps)',
    unit: '°',
    why: 'Less consistent reps can signal fatigue or reduced movement control, which raises the chance of poor form under load.',
    sourceId: 'hrp-muscle-bone',
    actions: {
      WATCH: ['Repeat the measurement and add a longer rest between sets.', 'Check sleep and fatigue in the daily check-in.'],
      ACT: ['Consult the Crew Medical Officer about form consistency.', 'Cut volume until reps are consistent again.'],
    },
  },
  adherence: {
    title: 'Exercise volume is below the prescription',
    metric: 'Completed ÷ prescribed volume (recent days)',
    unit: '%',
    why: 'Countermeasure exercise only works when it is done. Missed volume lets the effects of unloading accumulate on a mission where daily exercise is part of the plan.',
    sourceId: 'iss-exercise',
    actions: {
      WATCH: ['Schedule the missed volume over the next sessions.', 'If time or equipment is the problem, tell the Crew Medical Officer.'],
      ACT: ['Consult the Crew Medical Officer about the sustained shortfall.', 'Agree a reduced but achievable plan and re-measure.'],
    },
  },
}

const f1 = (n: number) => n.toFixed(1)

function series(usable: SessionMetrics[], pick: (m: SessionMetrics) => number): SeriesPoint[] {
  return usable.map((m) => ({ day: m.day, value: pick(m) }))
}

interface Ctx {
  crewId: string
  exercise: ExerciseId
  latestDay: number
}

function makeAlert(
  ctx: Ctx, rule: Exclude<RuleId, 'escalation'>, level: Level,
  data: { baseline: number | null; now: number; delta: number; summary: string; series: SeriesPoint[] },
): Alert {
  const t = TEXT[rule]
  return {
    id: `${ctx.crewId}:${ctx.exercise}:${rule}`,
    crewId: ctx.crewId,
    exercise: ctx.exercise,
    rule,
    level,
    title: t.title,
    what: { metric: t.metric, unit: t.unit, ...data },
    why: { text: t.why, sourceId: t.sourceId },
    actions: t.actions[level],
    day: ctx.latestDay,
  }
}

/** Adherence over the last `windowDays` mission days: completed ÷ prescribed reps. */
export function adherenceRatio(all: SessionMetrics[], latestDay: number, windowDays: number): number | null {
  const inWindow = all.filter((m) => m.day > latestDay - windowDays)
  const prescribed = inWindow.reduce((a, m) => a + m.prescribedReps, 0)
  if (prescribed === 0) return null
  // Completed reps, not valid reps: low camera confidence is a measurement problem, not skipped exercise.
  return inWindow.reduce((a, m) => a + m.completedReps, 0) / prescribed
}

/**
 * Assess one crew member on one exercise from their session history.
 * Pure and deterministic; every threshold comes from `cfg`.
 */
export function assessExercise(
  records: SessionRecord[], crewId: string, exercise: ExerciseId, cfg: HealthRulesConfig = HEALTH_RULES,
): ExerciseAssessment {
  const mine = records.filter((r) => r.crewId === crewId && r.exercise === exercise).sort((a, b) => a.day - b.day)
  const all = mine.map((r) => summarizeSession(r, cfg))
  const usable = all.filter((m) => m.usable)
  const latestDay = all.length ? (all[all.length - 1] as SessionMetrics).day : 0
  const ctx: Ctx = { crewId, exercise, latestDay }
  const alerts: Alert[] = []
  const notes: string[] = []

  // Adherence needs no baseline: it compares against the prescription itself.
  const ratio = adherenceRatio(all, latestDay, cfg.adherence.windowDays)
  if (ratio !== null) {
    // Lower is worse, so measure the shortfall below the WATCH/ACT ratios.
    const level: Level | null = ratio < cfg.adherence.act ? 'ACT' : ratio < cfg.adherence.watch ? 'WATCH' : null
    if (level) {
      const pct = ratio * 100
      alerts.push(makeAlert(ctx, 'adherence', level, {
        baseline: 100,
        now: pct,
        delta: pct - 100,
        summary: `${f1(pct)}% of prescribed reps completed over the last ${cfg.adherence.windowDays} days (prescription = 100%).`,
        series: all.map((m) => ({ day: m.day, value: m.prescribedReps ? (100 * m.completedReps) / m.prescribedReps : 0 })),
      }))
    }
  }

  const baseline = computeBaseline(usable, cfg)
  if (!baseline) {
    notes.push(`Building baseline (${Math.min(usable.length, cfg.baselineSessions)}/${cfg.baselineSessions} valid sessions). No trend alerts until it is ready.`)
    const skipped = all.length - usable.length
    if (skipped > 0) notes.push(`${skipped} session(s) ignored: fewer than ${cfg.minValidReps} valid reps or low confidence.`)
    return finish(ctx, null, usable.length, alerts, notes, cfg)
  }

  const after = usable.slice(cfg.baselineSessions)
  const comparable = after.filter((m) => Math.abs(m.gravityG - baseline.gravityG) <= cfg.gravityTolerance)
  if (comparable.length < after.length) {
    notes.push(`${after.length - comparable.length} session(s) at a different gravity than the baseline (${f1(baseline.gravityG)} g) were not compared.`)
  }
  if (comparable.length < cfg.minRecentSessions) {
    notes.push(`Waiting for ${cfg.minRecentSessions} comparable sessions after the baseline (${comparable.length} so far).`)
    return finish(ctx, baseline, usable.length, alerts, notes, cfg)
  }

  const recent = comparable.slice(-cfg.recentSessions)
  const now = {
    depth: median(recent.map((m) => m.depthDeg)),
    concentric: median(recent.map((m) => m.concentricS)),
    asymmetry: median(recent.map((m) => m.asymmetryDeg)),
    variability: median(recent.map((m) => m.variabilityDeg)),
  }
  const lastDay = (recent[recent.length - 1] as SessionMetrics).day
  ctx.latestDay = Math.max(ctx.latestDay, lastDay)

  const depthDelta = now.depth - baseline.depthDeg // positive = shallower
  const depthLevel = levelFor(depthDelta, cfg.depth)
  if (depthLevel) {
    alerts.push(makeAlert(ctx, 'depth', depthLevel, {
      baseline: baseline.depthDeg, now: now.depth, delta: depthDelta,
      summary: `Bottom knee angle ${f1(baseline.depthDeg)}° at baseline → ${f1(now.depth)}° now (${f1(depthDelta)}° shallower).`,
      series: series(usable, (m) => m.depthDeg),
    }))
  }

  const conPct = baseline.concentricS > 0 ? ((now.concentric - baseline.concentricS) / baseline.concentricS) * 100 : NaN
  const conLevel = levelFor(conPct, cfg.concentric)
  if (conLevel) {
    alerts.push(makeAlert(ctx, 'concentric', conLevel, {
      baseline: baseline.concentricS, now: now.concentric, delta: now.concentric - baseline.concentricS,
      summary: `Lifting phase ${f1(baseline.concentricS)} s at baseline → ${f1(now.concentric)} s now (${f1(conPct)}% slower).`,
      series: series(usable, (m) => m.concentricS),
    }))
  }

  const asymDelta = now.asymmetry - baseline.asymmetryDeg
  const asymLevel = levelFor(asymDelta, cfg.asymmetry)
  if (asymLevel) {
    alerts.push(makeAlert(ctx, 'asymmetry', asymLevel, {
      baseline: baseline.asymmetryDeg, now: now.asymmetry, delta: asymDelta,
      summary: `Left/right difference ${f1(baseline.asymmetryDeg)}° at baseline → ${f1(now.asymmetry)}° now (+${f1(asymDelta)}°).`,
      series: series(usable, (m) => m.asymmetryDeg),
    }))
  }

  const varDelta = now.variability - baseline.variabilityDeg
  const varLevel = levelFor(varDelta, cfg.variability)
  if (varLevel) {
    alerts.push(makeAlert(ctx, 'variability', varLevel, {
      baseline: baseline.variabilityDeg, now: now.variability, delta: varDelta,
      summary: `Rep-to-rep depth variability ${f1(baseline.variabilityDeg)}° at baseline → ${f1(now.variability)}° now (+${f1(varDelta)}°).`,
      series: series(usable, (m) => m.variabilityDeg),
    }))
  }

  return finish(ctx, baseline, usable.length, alerts, notes, cfg)
}

/** Derives the status and applies the escalation rule (several WATCH rules together = ACT). */
function finish(
  ctx: Ctx, baseline: Baseline | null, usableSessions: number, alerts: Alert[], notes: string[], cfg: HealthRulesConfig,
): ExerciseAssessment {
  let status = worstStatus('NOMINAL', ...alerts.map((a) => a.level))
  const watchCount = alerts.filter((a) => a.level === 'WATCH').length
  if (status === 'WATCH' && watchCount >= cfg.escalateWatchCount) {
    status = 'ACT'
    notes.push(`${watchCount} rules are at WATCH together, which escalates to ACT.`)
  }
  return { crewId: ctx.crewId, exercise: ctx.exercise, status, baseline, usableSessions, alerts, notes }
}

/** Assess every exercise that a crew member has sessions for. */
export function assessCrew(
  records: SessionRecord[], crewId: string, cfg: HealthRulesConfig = HEALTH_RULES,
): CrewAssessment {
  const exercises = [...new Set(records.filter((r) => r.crewId === crewId).map((r) => r.exercise))]
  const per = exercises.map((e) => assessExercise(records, crewId, e, cfg))
  return {
    crewId,
    status: worstStatus('NOMINAL', ...per.map((p) => p.status)),
    exercises: per,
    alerts: per.flatMap((p) => p.alerts),
  }
}
