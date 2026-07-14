# Animation Plans: Rect-Crab

Design briefs for rect-crab animations. Each plan uses the four-part template
from `plans-template.md` (Action / Body Mechanics / Eyes / Effects). The tools
in `animation-studio/tools/` automatically attach the matching section here to
the AI prompt when the animation name matches a heading.

The first two plans are BUILT — see `examples/`. The rest are seed ideas
waiting for a director.

## 1. Dance Groove (built → examples/clawd-dance-groove.svg)

* **Action:** Clawd is grooving to music, swaying side to side like he's
  wearing invisible headphones.
* **Body Mechanics:** The upper body sways left and right with a slight lean
  (rotate) at each end. The claws bob up and down alternately, snapping to the
  beat. Legs stay planted.
* **Eyes:** Relaxed. A slow, contented blink every couple of beats.
* **Effects:** Two pixel-art music notes take turns floating up from behind
  him, drifting slightly sideways and fading out.

## 2. Dance Party (built → examples/clawd-dance-party.svg)

* **Action:** Full party mode — Clawd is jumping to the beat with both claws
  in the air while confetti rains down.
* **Body Mechanics:** The whole crab jumps in a fast rhythm: squash on
  landing, stretch at the top. Claws raised high, waving fast. The ground
  shadow pulses wider when he lands, thinner when he's airborne.
* **Eyes:** Wide open with excitement, darting a quick blink at the top of
  a jump.
* **Effects:** Colorful confetti squares fall continuously from above, each on
  its own timing, tumbling as they drop.

## 3. Robot Dance

* **Action:** Clawd does the robot — stiff, mechanical poses.
* **Body Mechanics:** Movement happens in sudden steps (use `step-end`
  timing), holding each pose: lean left, claws at right angles, lean right.
* **Eyes:** Blinking in alternation, like indicator lights.
* **Effects:** Tiny grey gear rectangles clicking in rotation above his head.

## 4. Moonwalk

* **Action:** Clawd slides sideways across the ground like a smooth moonwalk.
* **Body Mechanics:** Body glides left while the legs shuffle the other way;
  then a snap turn and glide back to loop seamlessly.
* **Eyes:** Cool and half-closed (half-height rectangles).
* **Effects:** A little white pixel sparkle pops at his feet on each direction
  change.

## 5. Rain Dance

* **Action:** Clawd hops in a circle-ish pattern asking the sky for rain.
* **Body Mechanics:** Rhythmic two-beat hops, body tilting left on one hop and
  right on the next.
* **Eyes:** Looking up at the sky.
* **Effects:** Blue pixel raindrops begin to fall halfway through the loop,
  and a tiny grey cloud made of rects fades in above.

## 6. Sleepy Shuffle

* **Action:** Clawd is dancing but can barely stay awake.
* **Body Mechanics:** A very slow, drooping sway; every few beats he startles
  upright, then droops again.
* **Eyes:** Heavy — mostly half-closed, briefly wide when he startles.
* **Effects:** A pixel "Z" (built from three small rects) drifts up, then
  shatters when he startles.

## 7. Victory Wiggle

* **Action:** Clawd just won something — pure celebration wiggle.
* **Body Mechanics:** Fast alternating hip-tilts (rotate ±8° at the feet),
  claws punching the air one at a time.
* **Eyes:** Squeezed shut with joy (flat 1×1 rectangles).
* **Effects:** Yellow starburst sparkles popping frame-by-frame around him,
  like the classic celebration sparkle.

## 8. Crab Rave

* **Action:** The legendary crab rave bounce.
* **Body Mechanics:** Quick side-to-side hops, whole body translating left and
  right, claws raised and pulsing to the beat.
* **Eyes:** Normal, locked forward, dead serious. That's the joke.
* **Effects:** Two beams of "laser light" (long thin rects, low opacity)
  sweeping behind him in alternating colors.
