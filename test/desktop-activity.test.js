"use strict";

const { describe, it } = require("node:test");
const assert = require("node:assert");
const { computeTier, createDesktopActivityMonitor } = require("../src/desktop-activity");

// Deterministic env: window = 10000 / 500 = 20 samples. The enter thresholds
// are spaced wide enough (2 vs 8) relative to the 1000ms stability window that
// a steady ramp commits tier 1 before the candidate climbs to tier 2 — so the
// escalation is observable one step at a time.
const ENV = {
  CLAWD_ACTIVITY_DANCE_POLL_MS: "500",
  CLAWD_ACTIVITY_DANCE_WINDOW_MS: "10000",
  CLAWD_ACTIVITY_DANCE_STABLE_MS: "1000",
  CLAWD_ACTIVITY_DANCE_T1_ENTER: "2",
  CLAWD_ACTIVITY_DANCE_T1_EXIT: "1",
  CLAWD_ACTIVITY_DANCE_T2_ENTER: "8",
  CLAWD_ACTIVITY_DANCE_T2_EXIT: "6",
};

// A monitor harness driven one poll at a time. `idle` is the mutable value the
// fake powerMonitor returns; the clock advances by pollMs before every tick so
// the stability debounce sees real elapsed time.
function makeHarness(overrides = {}) {
  const state = { idle: 0, now: 1000, gateOpen: true };
  const tiers = [];
  const monitor = createDesktopActivityMonitor({
    powerMonitor: { getSystemIdleTime: () => state.idle },
    onTier: (t) => tiers.push(t),
    isGateOpen: () => state.gateOpen,
    now: () => state.now,
    env: { ...ENV, ...overrides },
  });
  function poll(idle) {
    if (idle !== undefined) state.idle = idle;
    state.now += 500;
    monitor.tick();
  }
  return { state, tiers, monitor, poll };
}

describe("computeTier (hysteresis)", () => {
  const th = { tier1Enter: 4, tier1Exit: 2, tier2Enter: 14, tier2Exit: 10 };

  it("rises through the enter thresholds from rest", () => {
    assert.strictEqual(computeTier(3, 0, th), 0);
    assert.strictEqual(computeTier(4, 0, th), 1);
    assert.strictEqual(computeTier(13, 0, th), 1);
    assert.strictEqual(computeTier(14, 0, th), 2);
  });

  it("holds tier via the lower exit thresholds (no chatter)", () => {
    // At tier 2, a dip to 11 (< enter 14 but >= exit 10) stays at 2.
    assert.strictEqual(computeTier(11, 2, th), 2);
    assert.strictEqual(computeTier(9, 2, th), 1);   // below tier2 exit → drop to 1
    assert.strictEqual(computeTier(1, 2, th), 0);   // below tier1 exit → drop to 0
    // At tier 1, a dip to 3 (< enter 4 but >= exit 2) stays at 1.
    assert.strictEqual(computeTier(3, 1, th), 1);
    assert.strictEqual(computeTier(1, 1, th), 0);
  });
});

describe("createDesktopActivityMonitor", () => {
  it("escalates to tier 2 under sustained activity", () => {
    const h = makeHarness();
    for (let i = 0; i < 20; i++) h.poll(0); // idle pinned at 0 = sustained input
    assert.strictEqual(h.monitor.getTier(), 2);
    // Monotonic escalation 0 → 1 → 2, each committed once.
    assert.deepStrictEqual(h.tiers, [1, 2]);
  });

  it("debounces: no tier change before the stability window elapses", () => {
    const h = makeHarness();
    // The tier-1 candidate appears at the 2nd active poll, but the 1000ms
    // stability window has not elapsed yet, so nothing is committed.
    h.poll(0);
    h.poll(0);
    assert.strictEqual(h.monitor.getTier(), 0);
    assert.deepStrictEqual(h.tiers, []);
    // Two more polls cross the stability threshold → tier 1 commits.
    h.poll(0);
    h.poll(0);
    assert.strictEqual(h.monitor.getTier(), 1);
  });

  it("de-escalates back to 0 when activity stops", () => {
    const h = makeHarness();
    for (let i = 0; i < 20; i++) h.poll(0);
    assert.strictEqual(h.monitor.getTier(), 2);
    // Idle climbs steadily (no fresh input): active-poll count decays out of the
    // window and the tier falls back through the exit thresholds to 0.
    let idle = 1;
    for (let i = 0; i < 40; i++) h.poll(idle++);
    assert.strictEqual(h.monitor.getTier(), 0);
  });

  it("reports tier 0 immediately while the gate is closed (DND / feature off)", () => {
    const h = makeHarness();
    for (let i = 0; i < 20; i++) h.poll(0);
    assert.strictEqual(h.monitor.getTier(), 2);
    h.state.gateOpen = false;
    h.poll(0); // still active, but gate closed
    assert.strictEqual(h.monitor.getTier(), 0);
  });

  it("honors the force-tier test override (subject to the gate)", () => {
    const h = makeHarness({ CLAWD_ACTIVITY_DANCE_FORCE_TIER: "2" });
    h.poll(9999); // no real activity at all
    assert.strictEqual(h.monitor.getTier(), 2);
    h.state.gateOpen = false;
    h.poll(9999);
    assert.strictEqual(h.monitor.getTier(), 0);
  });

  it("start()/stop() schedule and cancel via injected timers", () => {
    let scheduled = 0;
    let cleared = 0;
    const monitor = createDesktopActivityMonitor({
      powerMonitor: { getSystemIdleTime: () => 0 },
      onTier: () => {},
      now: () => 1000,
      setTimeout: () => { scheduled++; return { id: scheduled }; },
      clearTimeout: () => { cleared++; },
      env: ENV,
    });
    monitor.start();
    assert.strictEqual(scheduled, 1);
    monitor.stop();
    assert.strictEqual(cleared, 1);
  });
});
