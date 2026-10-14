# Quest: Closed-Loop Bing Rewards Collector (macOS, Firefox)

## Goal
Modernize and rewrite my Bing Rewards automation so it reliably collects the
maximum daily search reward points, and — critically — is CLOSED-LOOP: it must
verify whether each step and each run actually succeeded, and self-correct or
retry instead of blindly running open-loop.

## Background
- Upstream project: https://github.com/jack-mil/bing-rewards (Python CLI, uses
  pynput to type searches into a Chromium browser; open-loop: it types N
  searches and hopes for the best).
- My fork: https://github.com/ProtonKicker/bing-rewards — I no longer remember
  what I changed. It has accumulated a lot of cruft: a web GUI, "concurrent
  mode", "isolated instances", and many AI-generated debug/status markdown
  files (AUTOMATION_DEBUG_*.md, COMPLETE_*.md, etc.).
- First task: diff my fork against upstream and summarize in a file
  `FORK_ANALYSIS.md` what my fork actually changed vs upstream, and what is
  worth keeping vs deleting. I suspect most of it is cruft and should go.
- Upstream is actively maintained (recent commits in 2026) — rebase or start
  fresh from upstream if that's cleaner.

## Requirements
1. **Firefox support.** The original targets Chrome. I log into Bing with my
   Microsoft account in Firefox on this Mac. The tool must drive Firefox using
   my real logged-in profile (cookies), so searches count toward my account.
   Firefox supports remote automation via `--marionette` / geckodriver
   (Selenium) or via Firefox's `-juggler` (Playwright). Choose the most robust
   approach for macOS and document why.
2. **Closed-loop verification (the core of this quest):**
   - After loading, verify the Bing session is actually signed in (detect the
     account avatar / rewards counter element). If not signed in, STOP and
     report clearly instead of wasting searches.
   - Read the live rewards points counter / progress bar from the Bing Rewards
     page (rewards.bing.com) before and after the run.
   - After each search (or each batch), confirm the search registered: points
     increased or progress advanced. If a search didn't register (points
     stalled), detect it and retry, possibly with different query/delay/UA.
   - Detect daily quota completion (desktop + mobile) and stop early — no
     wasted searches past the cap.
   - End-of-run report: points before → after, per-quest points earned,
     searches attempted/registered/wasted, and a clear SUCCESS / PARTIAL /
     FAIL verdict with reasons.
   - Persist a small JSON run log per day so repeated runs are idempotent
     (don't redo what already succeeded today).
3. **Maximize rewards:** cover desktop points AND mobile points (mobile via
   user-agent switch), plus the daily "activities"/quiz if feasible (stretch
   goal — mark as optional).
4. **Simple and fast.** A clean, small Python CLI. One command runs the whole
   daily collection. No web GUI, no concurrent mode, no isolated instances —
   delete that cruft from the fork. Keep dependencies minimal
   (selenium/playwright + stdlib).
5. **macOS 13 Ventura, Intel Mac.** Verify everything works here. Use
   AppleScript `osascript` only if it makes things simpler, not as a
   requirement.
6. Human-like behavior: randomized realistic search queries, randomized
   delays, natural typing where applicable (low priority since closed-loop
   verification matters more than stealth).

## Definition of Done
- `bing-rewards` (or a fresh clean repo) runs end-to-end on my Mac with Firefox
  and my logged-in profile, collecting desktop + mobile daily points.
- Run output shows the closed-loop report (before/after points, verdict).
- A dry-run / mock mode exists for testing without burning real searches.
- Fork is cleaned up, README rewritten to match reality.
- Commit the work and push to my fork https://github.com/ProtonKicker/bing-rewards
  on a branch, then open it for my review.

## Agent workflow expectations
- Take SCREENSHOTS (macOS `screencapture`) at key stages: browser launched,
  signed-in state detected, points counter before/after, final rewards page.
  Save them under `docs/screenshots/` and reference them in the README/PR.
- TEST the app from the USER's perspective: actually run it, watch what
  happens, click through the report, and fix papercuts you notice. Don't just
  trust that the code compiles.
- Think from the user's perspective: the user wants to run one command each
  morning and know it either worked (and how many points) or exactly why it
  failed.
