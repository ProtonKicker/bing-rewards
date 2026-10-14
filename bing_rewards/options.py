# SPDX-FileCopyrightText: 2026 jack-mil
# SPDX-License-Identifier: MIT

"""Command line options for the closed-loop Firefox Bing Rewards collector."""

import argparse
import dataclasses
import sys
from pathlib import Path

import bing_rewards

# Fallback search counts per round, used only when live quota can't be read.
DESKTOP_COUNT = 30
MOBILE_COUNT = 10

# Randomized delay range between searches (seconds).
MIN_DELAY = 4.0
MAX_DELAY = 9.0

# Verify (re-read rewards status) after this many searches.
BATCH_SIZE = 5

# Searches to re-attempt with fresh queries/longer delays when a batch
# registers nothing, before declaring the round stalled.
RETRY_ROUNDS = 1

BING_SEARCH_URL = 'https://www.bing.com/search?form=QBRE&q='

# User agent used for the mobile round (general.useragent.override on Firefox).
# Makes the session look like an Edge-on-Android phone so mobile points count.
MOBILE_AGENT = (
    'Mozilla/5.0 (Linux; Android 14; Pixel 6 Build/AP2A.240605.024) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/121.0.0.0 Mobile Safari/537.36 Edge/121.0.2277.138'
)

# Known Microsoft authentication cookie names (carried over from the old fork's
# session_checker; used for diagnostics when the signed-in gate fails).
# On bing.com, presence of WLS/_U/RPSSecAuth means an account is signed in.
MS_AUTH_COOKIES = (
    'RPSSecAuth',
    'RPSAuth',
    'WLSSecure',
    'WLS',
    '_U',
    'MSPReauth',
    'ESTSAUTHPERSISTENT',
)


@dataclasses.dataclass
class Options:
    """All tunables for one collector run."""

    desktop: bool = True
    mobile: bool = True
    desktop_count: int = DESKTOP_COUNT
    mobile_count: int = MOBILE_COUNT
    max_searches: int | None = None  # hard cap per round (testing)
    batch_size: int = BATCH_SIZE
    min_delay: float = MIN_DELAY
    max_delay: float = MAX_DELAY
    retry_rounds: int = RETRY_ROUNDS
    profile_name: str = 'default-release'
    firefox_binary: Path | None = None
    geckodriver: Path | None = None
    headless: bool = False
    dry_run: bool = False
    mock_stall_after: int | None = None  # dry-run: simulate stall after N searches
    runs_dir: Path = Path('runs')
    screenshots_dir: Path | None = Path('docs/screenshots')
    force: bool = False  # ignore today's run log
    verbose: bool = False


def parse_args(argv: list[str] | None = None) -> Options:
    """Parse command line arguments into an Options object."""
    p = argparse.ArgumentParser(
        prog=Path(sys.argv[0]).name,
        description=bing_rewards.__doc__.strip().splitlines()[0]
        + '\n\nOne command collects the full daily Bing Rewards search points '
        'and verifies every step actually registered.',
    )
    p.add_argument('--version', action='version', version='%(prog)s 4.0.0-closed-loop')

    rounds = p.add_mutually_exclusive_group()
    rounds.add_argument('-d', '--desktop', action='store_true', help='desktop searches only')
    rounds.add_argument('-m', '--mobile', action='store_true', help='mobile searches only')

    p.add_argument(
        '--desktop-count',
        type=int,
        default=DESKTOP_COUNT,
        help='fallback desktop target when live quota is unreadable (default: %(default)s)',
    )
    p.add_argument(
        '--mobile-count',
        type=int,
        default=MOBILE_COUNT,
        help='fallback mobile target when live quota is unreadable (default: %(default)s)',
    )
    p.add_argument(
        '--max-searches',
        type=int,
        metavar='N',
        help='hard cap of searches per round (for limited/test runs)',
    )
    p.add_argument(
        '--batch-size',
        type=int,
        default=BATCH_SIZE,
        help='searches per verification batch (default: %(default)s)',
    )
    p.add_argument(
        '--delay',
        type=float_range,
        metavar='MIN[,MAX]',
        default=(MIN_DELAY, MAX_DELAY),
        help='random delay range between searches in seconds (default: 4,9)',
    )
    p.add_argument(
        '--profile',
        default='default-release',
        help='Firefox profile name holding the Bing login (default: %(default)s)',
    )
    p.add_argument('--firefox', type=Path, metavar='PATH', help='path to the Firefox binary')
    p.add_argument(
        '--geckodriver',
        type=Path,
        metavar='PATH',
        help='path to geckodriver (default: Selenium Manager resolves it)',
    )
    p.add_argument('--headless', action='store_true', help='run Firefox headless')
    p.add_argument(
        '-n',
        '--dry-run',
        action='store_true',
        help='exercise the full loop against a mock rewards account (no real searches)',
    )
    p.add_argument(
        '--mock-stall-after',
        type=int,
        metavar='N',
        help='with --dry-run: simulate point stall after N searches',
    )
    p.add_argument(
        '--runs-dir',
        type=Path,
        default=Path('runs'),
        help='directory for daily JSON run logs (default: %(default)s)',
    )
    p.add_argument(
        '--screenshots-dir',
        type=Path,
        default=Path('docs/screenshots'),
        help='directory for stage screenshots; use --no-screenshots to disable',
    )
    p.add_argument('--no-screenshots', action='store_true', dest='screenshots_off')
    p.add_argument(
        '--force',
        action='store_true',
        help="redo rounds even if today's run log says they are complete",
    )
    p.add_argument('-v', '--verbose', action='store_true')

    args = p.parse_args(argv)
    opts = Options()
    if args.desktop:
        opts.desktop, opts.mobile = True, False
    if args.mobile:
        opts.desktop, opts.mobile = False, True
    opts.desktop_count = args.desktop_count
    opts.mobile_count = args.mobile_count
    opts.max_searches = args.max_searches
    opts.batch_size = max(1, args.batch_size)
    opts.min_delay, opts.max_delay = args.delay
    opts.profile_name = args.profile
    opts.firefox_binary = args.firefox
    opts.geckodriver = args.geckodriver
    opts.headless = args.headless
    opts.dry_run = args.dry_run
    opts.mock_stall_after = args.mock_stall_after
    opts.runs_dir = args.runs_dir
    opts.screenshots_dir = None if args.screenshots_off else args.screenshots_dir
    opts.force = args.force
    opts.verbose = args.verbose
    return opts


def float_range(value: str) -> tuple[float, float]:
    """Parse 'MIN' or 'MIN,MAX' into a delay range."""
    max_delay_parts = 2
    try:
        nums = [float(part) for part in value.split(',')]
    except ValueError:
        raise argparse.ArgumentTypeError('use numeric values, e.g. 6 or 4,12') from None
    if len(nums) > max_delay_parts or nums[-1] < nums[0]:
        raise argparse.ArgumentTypeError('use MIN or MIN,MAX with MAX >= MIN')
    return nums[0], nums[-1]
