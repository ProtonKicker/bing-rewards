# SPDX-FileCopyrightText: 2026 jack-mil
# SPDX-License-Identifier: MIT

"""Closed-loop Bing Rewards collector for Firefox on macOS.

One command performs the daily desktop + mobile searches and *verifies* they
registered: signed-in gate, live points before/after, per-batch progress
checks with retry on stall, quota detection, a per-day JSON run log, and a
final SUCCESS / PARTIAL / FAIL verdict.

Examples
--------
    $ bing-rewards                 # full daily collection
    $ bing-rewards -n              # dry run against a mock account
    $ bing-rewards --max-searches 3 -d   # small live test, desktop only
"""

# This package does not export any programmatic API
# Run as an installed application or as a module
