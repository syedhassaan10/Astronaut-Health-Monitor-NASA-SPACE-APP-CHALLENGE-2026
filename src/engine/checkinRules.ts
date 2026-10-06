import { HEALTH_RULES, type HealthRulesConfig } from '../config/healthRules'
import type { Alert, BodyLocation, CheckIn, ExerciseAssessment, RuleId, SeriesPoint, Status } from './healthTypes'

type Level = Exclude<Status, 'NOMINAL'>
type CheckinRule = Extract<RuleId, 'pain' | 'recovery' | 'stress' | 'pain-asymmetry'>

export const LOCATION_LABEL: Record<BodyLocation, string> = {
  knee: 'knee',
  hip: 'hip',
  'ankle-foot': 'ankle / foot',
  'lower-back': 'lower back',
  'upper-back-neck': 'upper back / neck',
  shoulder: 'shoulder',
  other: 'other area',
}

/** The latest `window` check-ins for one crew member, oldest first. */
export function recentCheckins(checkins: CheckIn[], crewId: string, window: number): CheckIn[] {
  return checkins.filter((c) => c.crewId === crewId).sort((a, b) => a.day - b.day).slice(-window)
}

const count = (xs: CheckIn[], pred: (c: CheckIn) => boolean) => xs.filter(pred).length

interface Text {
  title: string
  metric: string
  why: string
  sourceId: string
  actions: Record<Level, string[]>
}

// Wording rules: "estimate", "trend", "decision support"; never "diagnosis".
const TEXT: Record<CheckinRule, Text> = {
  pain: {
    title: 'Reported pain',
    metric: 'Self-reported pain (0-10)',
    why: 'Pain during or after resistive exercise is an early signal worth acting on before it limits training or becomes an injury, and crews are far from a hospital.',
    sourceId: 'hrp-muscle-bone',
    actions: {
      WATCH: [
        'Keep the load and range of motion in the pain-free zone and log pain again tomorrow.',
        'Tell the Crew Medical Officer if it persists or increases.',
      ],
      ACT: [
        'Consult the Crew Medical Officer before the next loaded session.',
        'Pause the movement that provokes the pain and use a lighter, pain-free alternative.',
      ],
    },
  },
  recovery: {
    title: 'Poor sleep and high fatigue',
    metric: 'Self-reported fatigue (0-10)',
    why: 'Sleep loss and fatigue are common on missions and reduce performance and recovery. They can also make exercise measurements look worse than they really are.',
    sourceId: 'hrp-sleep',
    actions: {
      WATCH: [
        'Prioritise sleep and recovery; consider a lighter session today.',
        'Repeat measurements when rested before reading much into a trend.',
      ],
      ACT: ['Consult the Crew Medical Officer about sustained poor recovery.'],
    },
  },
  stress: {
    title: 'High stress reported',
    metric: 'Self-reported stress (0-10)',
    why: 'Isolation, confinement and workload can raise stress. Spotting a sustained rise early lets the crew and flight surgeon respond before it affects health and performance.',
    sourceId: 'hrp-behavioral',
    actions: {
      WATCH: [
        'Take a break, talk with a crewmate, or schedule a private call if comms allow.',
        'Mention it to the Crew Medical Officer if it continues.',
      ],
      ACT: ['Consult the Crew Medical Officer about sustained high stress.'],
    },
  },
  'pain-asymmetry': {
    title: 'Knee pain with rising left/right asymmetry',
    metric: 'Left/right knee-angle difference',
    why: 'Pain plus a growing left/right difference can mean you are unconsciously favouring one side. Together these two signals are more meaningful than either alone, so this is raised early.',
    sourceId: 'hrp-muscle-bone',
    actions: {
      WATCH: [
        'Repeat the measurement with the camera centred and watch weight shift and foot placement.',
        'Reduce the simulated load and keep the knee pain-free; log pain again tomorrow.',
      ],
      ACT: [
        'Consult the Crew Medical Officer before the next loaded session.',
        'Stop loaded squatting until the knee has been reviewed.',
      ],
    },
  },
}

const f1 = (n: number) => n.toFixed(1)

function build(
  crewId: string, rule: CheckinRule, level: Level, exercise: Alert['exercise'], day: number, title: string,
  what: Alert['what'],
): Alert {
  const t = TEXT[rule]
  return {
    id: `${crewId}:${exercise ?? 'checkin'}:${rule}`,
    crewId, exercise, rule, level, title,
    what,
    why: { text: t.why, sourceId: t.sourceId },
    actions: t.actions[level],
    day,
  }
}

const seriesOf = (all: CheckIn[], pick: (c: CheckIn) => number): SeriesPoint[] =>
  all.map((c) => ({ day: c.day, value: pick(c) }))

/**
 * Alerts from the daily check-ins, alone and combined with the exercise trend.
 * `exercises` are the already-computed exercise assessments for the same crew member.
 */
export function assessCheckins(
  checkins: CheckIn[], crewId: string, exercises: ExerciseAssessment[], cfg: HealthRulesConfig = HEALTH_RULES,
): Alert[] {
  const k = cfg.checkin
  const all = checkins.filter((c) => c.crewId === crewId).sort((a, b) => a.day - b.day)
  const recent = all.slice(-k.window)
  const last = recent[recent.length - 1]
  if (!last) return []
  const alerts: Alert[] = []

  // 1. Pain: sustained at WATCH/ACT level, or a single acute report.
  const sustainedAct = count(recent, (c) => c.pain >= k.pain.act) >= k.minSustained
  const sustainedWatch = count(recent, (c) => c.pain >= k.pain.watch) >= k.minSustained
  const acute = recent.some((c) => c.pain >= k.acutePain)
  const painLevel: Level | null = sustainedAct ? 'ACT' : sustainedWatch || acute ? 'WATCH' : null
  if (painLevel) {
    const where = [...recent].reverse().find((c) => c.pain > 0)?.painLocation ?? null
    const loc = where ? LOCATION_LABEL[where] : 'unspecified area'
    const n = count(recent, (c) => c.pain >= k.pain.watch)
    alerts.push(build(crewId, 'pain', painLevel, null, last.day, `Pain reported: ${loc}`, {
      metric: TEXT.pain.metric, unit: '/10', baseline: null, now: last.pain, delta: last.pain,
      summary: `Pain ${last.pain}/10 (${loc}) on day ${last.day}; ${n} of the last ${recent.length} check-ins at ${k.pain.watch}/10 or higher.`,
      series: seriesOf(all, (c) => c.pain),
    }))
  }

  // 2. Recovery: low sleep AND high fatigue, sustained.
  const poorRecovery = (c: CheckIn) => c.sleep <= k.sleepLow && c.fatigue >= k.fatigueHigh
  if (count(recent, poorRecovery) >= k.minSustained) {
    alerts.push(build(crewId, 'recovery', 'WATCH', null, last.day, TEXT.recovery.title, {
      metric: TEXT.recovery.metric, unit: '/10', baseline: null, now: last.fatigue, delta: last.fatigue,
      summary: `Sleep ${last.sleep}/10 and fatigue ${last.fatigue}/10 on day ${last.day}; poor recovery in ${count(recent, poorRecovery)} of the last ${recent.length} check-ins.`,
      series: seriesOf(all, (c) => c.fatigue),
    }))
  }

  // 3. Stress: sustained high.
  if (count(recent, (c) => c.stress >= k.stressHigh) >= k.minSustained) {
    alerts.push(build(crewId, 'stress', 'WATCH', null, last.day, TEXT.stress.title, {
      metric: TEXT.stress.metric, unit: '/10', baseline: null, now: last.stress, delta: last.stress,
      summary: `Stress ${last.stress}/10 on day ${last.day}; ${count(recent, (c) => c.stress >= k.stressHigh)} of the last ${recent.length} check-ins at ${k.stressHigh}/10 or higher.`,
      series: seriesOf(all, (c) => c.stress),
    }))
  }

  // 4. Combined: knee pain + rising asymmetry -> WATCH (ACT if it is severe).
  const kneePain = recent.some((c) => c.painLocation === 'knee' && c.pain >= k.kneePainMin)
  if (kneePain) {
    const rising = exercises
      .filter((e) => e.deltas && e.deltas.asymmetryDeg >= k.combinedAsymmetryDeg)
      .sort((a, b) => (b.deltas?.asymmetryDeg ?? 0) - (a.deltas?.asymmetryDeg ?? 0))[0]
    if (rising?.deltas) {
      const severe =
        count(recent, (c) => c.painLocation === 'knee' && c.pain >= k.pain.act) >= k.minSustained ||
        rising.alerts.some((a) => a.rule === 'asymmetry' && a.level === 'ACT')
      const worstKnee = Math.max(...recent.filter((c) => c.painLocation === 'knee').map((c) => c.pain))
      alerts.push(build(crewId, 'pain-asymmetry', severe ? 'ACT' : 'WATCH', rising.exercise, last.day, TEXT['pain-asymmetry'].title, {
        metric: TEXT['pain-asymmetry'].metric, unit: '°', baseline: rising.baseline?.asymmetryDeg ?? null,
        now: (rising.baseline?.asymmetryDeg ?? 0) + rising.deltas.asymmetryDeg, delta: rising.deltas.asymmetryDeg,
        summary: `Knee pain up to ${worstKnee}/10 reported, while left/right difference is +${f1(rising.deltas.asymmetryDeg)}° above your baseline.`,
        series: rising.asymmetrySeries,
      }))
    }
  }
  return alerts
}

/** Notes explaining that self-reported state may account for part of an exercise trend. */
export function contextFor(
  rule: RuleId, checkins: CheckIn[], crewId: string, cfg: HealthRulesConfig = HEALTH_RULES,
): string[] {
  const k = cfg.checkin
  const recent = recentCheckins(checkins, crewId, k.window)
  const out: string[] = []
  if (!['depth', 'concentric', 'variability'].includes(rule)) return out
  if (recent.some((c) => c.fatigue >= k.fatigueHigh)) {
    out.push('Recent check-ins report high fatigue, which can slow and loosen reps. Repeat the measurement when rested before acting on this trend.')
  }
  if (recent.some((c) => c.sleep <= k.sleepLow)) {
    out.push('Recent check-ins report poor sleep, which can affect performance.')
  }
  if (rule === 'depth' && recent.some((c) => c.painLocation === 'knee' && c.pain >= k.kneePainMin)) {
    out.push('Reported knee pain may be limiting depth.')
  }
  return out
}
