# Fork Analysis: ProtonKicker/bing-rewards vs jack-mil/bing-rewards

Generated as part of the closed-loop rewrite quest (see `QUEST.md`).
Diff basis: `git diff upstream/master...HEAD` (fork HEAD after last upstream merge, `cc61ef2`).

**Totals: 45 files changed, +13,635 / −70 lines.** The overwhelming majority is
AI-session artifacts and a "concurrent multi-instance" feature layered on the
unchanged pynput-types-into-Chromium core.

## Verdict summary

| Category | Files | Verdict |
|---|---|---|
| AI-generated debug/status docs | 24 root `.md` files (below) | **Delete** |
| GUI + concurrency code | `bing_rewards/gui/`, 5 modules, `launch-gui.bat`, 4 `test_*.py` | **Delete** |
| Modified upstream code | `bing_rewards/app.py`, `options.py`, `pyproject.toml`, `README.md` | **Superseded by rewrite** |
| Quest docs | `QUEST.md` | **Keep** |

## 1. Documentation cruft — delete all

These are session logs / prompt dumps / status notes from AI-assisted coding
sessions, not project documentation. They describe the GUI/concurrent feature
set, which itself is being deleted.

- `ARCHITECTURE_ISOLATED_INSTANCES.md`, `AUTOMATION_DEBUG_PROGRESS.md`,
  `AUTOMATION_DEBUG_STEPS.md`, `BUG_FIXES_SUMMARY.md`, `CHANGES_SUMMARY.md`,
  `COMPLETE_PROMPT_DUMP.md`, `COMPLETE_SUMMARY.md`, `CONCURRENT_MODE.md`,
  `CRITICAL_FIXES_IN_PROGRESS.md`, `GETTING_STARTED_GUI.md`, `GUI_README.md`,
  `GUI_TROUBLESHOOTING.md`, `GUI_UPDATES.md`, `IMPLEMENTATION_ISOLATED_INSTANCES.md`,
  `IMPLEMENTATION_SUMMARY.md`, `ISOLATED_INSTANCES.md`,
  `PROJECT_SUMMARY_FOR_CONTINUATION.md`, `QUICKSTART_CONCURRENT.md`,
  `QUICKSTART_ISOLATED_INSTANCES.md`, `QUICK_REFERENCE.md`,
  `RESTART_GUI_REQUIRED.md`, `SUMMARY_CHANGES.md`, `TODO_DEBUG_AUTOMATION.md`
- Plus 10 added README lines pointing at the same deleted docs.

`QUEST.md` is the only fork-added document worth keeping.

## 2. Code added by the fork — delete, with two ideas carried over

| File | What it is | Verdict |
|---|---|---|
| `bing_rewards/gui/` (`__main__.py`, `app.py`, `requirements.txt`, `templates/gui.html`) | Flask/web GUI control panel (~1,300 lines + template) | Delete — quest explicitly excludes a web GUI |
| `bing_rewards/browser_manager.py` | Launches 10+ isolated Chromium instances with cleanup | Delete — Chromium-only, quest excludes concurrent/isolated modes |
| `bing_rewards/concurrency_controller.py` | Throttling/eco-mode for parallel instances | Delete |
| `bing_rewards/event_bus.py` | Pub/sub for GUI progress updates | Delete |
| `bing_rewards/resource_monitor.py` | CPU/memory thresholds via `psutil` | Delete |
| `bing_rewards/profile_config.py` | Chrome profile discovery/listing | Delete — Chrome-specific; Firefox profile handling is rewritten in `firefox.py` |
| `bing_rewards/utils/chrome_finder.py` | Chrome binary/user-data-dir lookup | Delete — Chrome-specific |
| `bing_rewards/utils/session_checker.py` | Checks if a Chrome profile has Microsoft auth by grepping Cookies DB / leveldb for MS strings | Delete implementation, **carry over the idea**: the auth-cookie name list (`RPSSecAuth`, `ESTSAUTHPERSISTENT`, `MSPReauth`, …) is reused as one signal in the new signed-in gate (DOM check primary, cookie names as a diagnostic) |
| `test_automation_quick.py`, `test_concurrent.py`, `test_direct_search.py`, `test_isolated_instances.py` | Manual scripts for the concurrent/GUI features | Delete — they test deleted features |
| `launch-gui.bat` | Windows GUI launcher | Delete |

## 3. Upstream files modified by the fork

- `bing_rewards/app.py` (+351/−~60): added `run_concurrent_mode`,
  `execute_searches_for_instance`, `run_manual_login_mode`, and indented the
  existing `desktop/mobile/both` routines per-profile. Still **open-loop**: it
  types searches and never verifies points. Superseded by the rewrite.
- `bing_rewards/options.py` (+73): `ConcurrencyConfig` dataclass and CLI flags
  (`--concurrent`, `--max-instances`, `--eco-mode`, …). Superseded.
- `pyproject.toml`: added `psutil`/`rich` deps for the deleted features.
  Superseded — rewrite swaps to `selenium`.
- `README.md`: feature bullets/links for GUI + concurrency. Superseded.

## 4. What is genuinely "mine" in the fork

Nothing functional survives. The fork's only durable contributions are:
`QUEST.md` (the spec) and the auth-cookie-names idea noted above. The correct
modernization path is therefore **a clean branch from `upstream/master`** with
the closed-loop Firefox collector written fresh, rather than unwinding the
fork's additions.
