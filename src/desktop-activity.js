"use strict";

// src/desktop-activity.js — Desktop activity dancing monitor.
//
// Maps recent keyboard/mouse activity to a 0/1/2 "dance tier" using ONLY
// Electron's powerMonitor.getSystemIdleTime() — no native modules, no global
// input hooks, no keystroke/mouse capture. The idle timer is the sole signal:
// we never know or care whether the input was a key or a click.
//
// Dependency-injected (powerMonitor, timers, clock, RNG-free) like
// system-wake-recovery.js so it is unit-testable without a live app.
//
// Reporting only: this module never touches the state machine directly. It
// calls onTier(tier) when the committed tier changes; state.js decides whether
// a dance is actually shown (it is strictly the lowest-priority display state,
// so any live agent state / permission / DND / drag always wins).

// ── Tunable constants (env-overridable for testing) ──
const IDLE_POLL_MS = 500;            // how often we sample the idle timer
const ACTIVITY_WINDOW_MS = 10000;    // rolling window length (~last 10s)

// A poll counts as "active" when the idle timer dropped since the previous
// sample OR currently reads 0s (sustained input pins it at 0). Tiers compare
// the active-poll count within the rolling window. Separate enter/exit values
// give hysteresis so the tier can't chatter at a boundary.
const TIER1_ENTER = 4;
const TIER1_EXIT = 2;
const TIER2_ENTER = 14;
const TIER2_EXIT = 10;

// A candidate tier must hold this long before it is committed + reported, so a
// brief spike/dip does not flip the animation. DND / feature-off (gate closed)
// forces tier 0 immediately, bypassing this debounce.
const TIER_STABLE_MS = 2000;

function readEnvInt(env, name, fallback, min, max) {
  const raw = env && env[name];
  if (typeof raw !== "string" || !raw.trim()) return fallback;
  const n = Number.parseInt(raw.trim(), 10);
  if (!Number.isFinite(n) || n < min || n > max) return fallback;
  return n;
}

function clampTier(tier) {
  return tier === 2 ? 2 : tier === 1 ? 1 : 0;
}

function requiredDependency(value, name) {
  if (!value) throw new Error(`createDesktopActivityMonitor requires ${name}`);
  return value;
}

// Pure tier mapping with hysteresis. `current` is the committed tier; enter
// thresholds lift the tier, the lower exit thresholds must be crossed to drop.
function computeTier(count, current, thresholds) {
  const { tier1Enter, tier1Exit, tier2Enter, tier2Exit } = thresholds;
  if (current >= 2) {
    if (count >= tier2Exit) return 2;
    return count >= tier1Exit ? 1 : 0;
  }
  if (current >= 1) {
    if (count >= tier2Enter) return 2;
    return count >= tier1Exit ? 1 : 0;
  }
  if (count >= tier2Enter) return 2;
  return count >= tier1Enter ? 1 : 0;
}

function createDesktopActivityMonitor(options = {}) {
  const powerMonitor = requiredDependency(options.powerMonitor, "powerMonitor");
  const onTier = typeof options.onTier === "function" ? options.onTier : () => {};
  // Gate closed (returns false) when the feature is off or DND is on — the
  // monitor keeps sampling but reports tier 0 immediately.
  const isGateOpen = typeof options.isGateOpen === "function" ? options.isGateOpen : () => true;
  const now = options.now || Date.now;
  const setTimer = options.setTimeout || setTimeout;
  const clearTimer = options.clearTimeout || clearTimeout;
  const log = options.log || (() => {});
  const env = options.env || process.env;

  const pollMs = readEnvInt(env, "CLAWD_ACTIVITY_DANCE_POLL_MS", IDLE_POLL_MS, 50, 10000);
  const windowMs = readEnvInt(env, "CLAWD_ACTIVITY_DANCE_WINDOW_MS", ACTIVITY_WINDOW_MS, pollMs, 120000);
  const windowSamples = Math.max(1, Math.round(windowMs / pollMs));
  const stableMs = readEnvInt(env, "CLAWD_ACTIVITY_DANCE_STABLE_MS", TIER_STABLE_MS, 0, 60000);
  const thresholds = {
    tier1Enter: readEnvInt(env, "CLAWD_ACTIVITY_DANCE_T1_ENTER", TIER1_ENTER, 1, windowSamples),
    tier1Exit: readEnvInt(env, "CLAWD_ACTIVITY_DANCE_T1_EXIT", TIER1_EXIT, 0, windowSamples),
    tier2Enter: readEnvInt(env, "CLAWD_ACTIVITY_DANCE_T2_ENTER", TIER2_ENTER, 1, windowSamples),
    tier2Exit: readEnvInt(env, "CLAWD_ACTIVITY_DANCE_T2_EXIT", TIER2_EXIT, 0, windowSamples),
  };
  // Test/QA seam: pin the reported tier regardless of real activity (still
  // subject to the gate). Unset/invalid → normal behavior.
  const forcedTierRaw = env && env.CLAWD_ACTIVITY_DANCE_FORCE_TIER;
  const forcedTier = /^[012]$/.test(String(forcedTierRaw || "").trim())
    ? Number(String(forcedTierRaw).trim())
    : null;

  let started = false;
  let timer = null;
  // Ring buffer of the last `windowSamples` polls (true = active poll).
  const ring = new Array(windowSamples).fill(false);
  let ringPos = 0;
  let activeCount = 0;
  let lastIdle = null;

  let committedTier = 0;
  let pendingTier = 0;
  let pendingSince = 0;

  function recordSample(active) {
    if (ring[ringPos] && !active) activeCount -= 1;
    else if (!ring[ringPos] && active) activeCount += 1;
    ring[ringPos] = active;
    ringPos = (ringPos + 1) % windowSamples;
  }

  function report(tier) {
    if (tier === committedTier) return;
    committedTier = tier;
    try { onTier(tier); } catch (err) { log(`activity-dance onTier failed: ${err && err.message}`); }
  }

  function evaluate() {
    let idleSec = 0;
    try { idleSec = Number(powerMonitor.getSystemIdleTime()); }
    catch { idleSec = lastIdle == null ? 0 : lastIdle; }
    if (!Number.isFinite(idleSec) || idleSec < 0) idleSec = 0;

    // Active poll: idle dropped since last sample (fresh input) OR pinned at 0
    // (sustained input). getSystemIdleTime() is integer seconds, so continuous
    // use keeps it at 0 — the `=== 0` clause is what captures sustained typing.
    const active = lastIdle != null ? (idleSec < lastIdle || idleSec === 0) : (idleSec === 0);
    lastIdle = idleSec;
    recordSample(active);

    const gateOpen = safeGate();
    if (!gateOpen) {
      pendingTier = 0;
      pendingSince = 0;
      report(0);
      return;
    }

    if (forcedTier != null) {
      report(forcedTier);
      return;
    }

    const candidate = computeTier(activeCount, committedTier, thresholds);
    if (candidate === committedTier) {
      pendingTier = candidate;
      pendingSince = 0;
      return;
    }
    if (candidate !== pendingTier) {
      pendingTier = candidate;
      pendingSince = now();
    }
    if (now() - pendingSince >= stableMs) {
      pendingSince = 0;
      report(candidate);
    }
  }

  function safeGate() {
    try { return isGateOpen() !== false; }
    catch { return true; }
  }

  function tick() {
    timer = null;
    if (!started) return;
    evaluate();
    schedule();
  }

  function schedule() {
    if (!started || timer) return;
    timer = setTimer(tick, pollMs);
  }

  function start() {
    if (started) return;
    started = true;
    lastIdle = null;
    schedule();
  }

  function stop() {
    started = false;
    if (timer) { clearTimer(timer); timer = null; }
  }

  return {
    start,
    stop,
    // Test hooks.
    tick: () => { if (started) { if (timer) { clearTimer(timer); timer = null; } tick(); } else evaluate(); },
    getTier: () => committedTier,
    getActiveCount: () => activeCount,
    getWindowSamples: () => windowSamples,
  };
}

module.exports = {
  IDLE_POLL_MS,
  ACTIVITY_WINDOW_MS,
  TIER1_ENTER,
  TIER1_EXIT,
  TIER2_ENTER,
  TIER2_EXIT,
  TIER_STABLE_MS,
  computeTier,
  createDesktopActivityMonitor,
};
