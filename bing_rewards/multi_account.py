"""Multi-account Microsoft Rewards check-in with before/after point verification.

Each account gets its own Firefox profile (created by logging in once in
Firefox). For every configured account we:

1. read points BEFORE  (fresh clone + launch, rewards.bing.com)
2. run the daily activities (Daily Set cards — the daily claim)
3. wait for Bing's 30–90s credit lag
4. read points AFTER
5. verdict = delta > 0 (or the day's activities were already complete/claimed)

This is deliberately more robust than button-state checks: the balance delta is
the server-authoritative proof that the check-in actually recorded.

Usage:
    python -m bing_rewards.multi_account --config accounts.json [--dry-run]

accounts.json:
    [
      {"profile": "acc01", "name": "Account 1"},
      {"profile": "acc02", "name": "Account 2"}
    ]
    (profile = the Firefox profile directory name holding that account)
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

from bing_rewards import daily_set, firefox, options as opts_mod, rewards


# Bing credits balance changes lazily; give it a beat before the AFTER read.
CREDIT_LAG_SECONDS = 60.0
READ_SETTLE_SECONDS = 8.0


def read_balance(driver) -> int | None:
    """Fresh balance read (force-refresh medallion)."""
    try:
        st = rewards.read_status(driver, force_refresh=True)
        return st.points
    except Exception:
        return None


def run_account(name: str, profile_name: str, *, dry_run: bool) -> dict:
    out: dict[str, object] = {"name": name, "profile": profile_name, "status": "unknown"}

    try:
        src = firefox.find_profile_directory(profile_name)
    except FileNotFoundError as e:
        out.update(status="profile_missing", error=str(e))
        return out

    cloned = None
    driver = None
    try:
        cloned = firefox.clone_profile(src)
        opts = opts_mod.parse_args(["--profile", profile_name])
        driver = firefox.start_driver(cloned, options=opts)
        driver.set_page_load_timeout(120)

        # --- BEFORE ---
        driver.get("https://rewards.bing.com/earn")
        time.sleep(READ_SETTLE_SECONDS)
        before = read_balance(driver)
        out["points_before"] = before
        if before is None:
            out.update(status="read_failed", error="could not read balance before")
            return out

        if dry_run:
            out.update(status="dry_run", points_after=before, delta=0)
            return out

        # --- ACTIVITIES: Daily Set cards (the daily claim) ---
        cards = daily_set._find_cards(driver)
        uncompleted = [c for c in cards if not daily_set._is_card_completed(c)]
        actions: list[str] = []
        done = 0
        for c in uncompleted:
            try:
                c.click()
                done += 1
                actions.append(daily_set._card_label(c)[:40])
                time.sleep(3)
            except Exception:
                pass
        out["daily_set"] = {"cards_found": len(uncompleted), "cards_clicked": done}

        # --- WAIT FOR CREDIT ---
        time.sleep(CREDIT_LAG_SECONDS)

        # --- AFTER ---
        driver.get("https://rewards.bing.com/earn")
        time.sleep(READ_SETTLE_SECONDS)
        after = read_balance(driver)
        out["points_after"] = after
        if after is None:
            out.update(status="read_failed_after", error="could not read balance after")
            return out

        delta = after - before
        out["delta"] = delta
        out["actions"] = actions

        if delta > 0:
            out["status"] = "success"
        elif not actions and not uncompleted:
            # nothing was claimable (already done today) — legitimate
            out["status"] = "already_complete"
        else:
            out["status"] = "delta_zero"
            out["error"] = "actions ran but balance did not change"
        return out
    except Exception as e:  # noqa: BLE001
        out.update(status="error", error=str(e))
        return out
    finally:
        if driver:
            try:
                firefox.quit_driver(driver)
            except Exception:
                pass
        if cloned is not None:
            try:
                shutil.rmtree(cloned.parent, ignore_errors=True)
            except Exception:
                pass


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=(__doc__ or "Multi-account check-in").splitlines()[0])
    p.add_argument("--config", required=True, type=Path, help="accounts.json")
    p.add_argument("--dry-run", action="store_true", help="read balance only")
    args = p.parse_args(argv)

    accounts = json.loads(Path(args.config).read_text())
    results = []
    for cfg in accounts:
        name = cfg.get("name", cfg.get("profile", "?"))
        profile_name = cfg.get("profile") or name
        r = run_account(name, profile_name, dry_run=args.dry_run)
        results.append(r)
        line = (
            f"[{r.get('status')}] {name}: "
            f"{r.get('points_before')} -> {r.get('points_after')} "
            f"(delta {r.get('delta')})"
        )
        if r.get("error"):
            line += f" | {r['error']}"
        print(line)

    print("\n=== SUMMARY ===")
    ok = sum(1 for r in results if r.get("status") in ("success", "already_complete", "dry_run"))
    print(f"  ok: {ok}/{len(results)}")
    for r in results:
        print(f"  - {r.get('status')}: {r.get('name')} (delta {r.get('delta')})")

    if any(r.get("status") in ("error", "read_failed", "read_failed_after", "delta_zero", "profile_missing") for r in results):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
