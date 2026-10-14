# SPDX-FileCopyrightText: 2026 jack-mil
# SPDX-License-Identifier: MIT

"""Unit tests for the rewards status parser (stdlib unittest, no network)."""

import json
import unittest

from bing_rewards import rewards

EXPECTED_POINTS = 1337
DESKTOP_CURRENT = 4
DESKTOP_MAX = 30
MOBILE_CURRENT = 2
MOBILE_MAX = 10

USERSTATUS_FIXTURE = {
    'userStatus': {
        'availablePoints': EXPECTED_POINTS,
        'dailySetProgress': [
            {
                'dailyProgress': [
                    {
                        'activityType': 'BingSearchDesktopPC',
                        'attributes': {
                            'currentProgress': DESKTOP_CURRENT,
                            'maxProgress': DESKTOP_MAX,
                        },
                    },
                    {
                        'activityType': 'BingSearchNarrowMobilePC',
                        'attributes': {
                            'currentProgress': MOBILE_CURRENT,
                            'maxProgress': MOBILE_MAX,
                        },
                    },
                ]
            }
        ],
    }
}


class ParseUserStatusTest(unittest.TestCase):
    def test_parses_points_and_progress(self):
        status = rewards.parse_userstatus(USERSTATUS_FIXTURE)
        self.assertEqual(status.points, EXPECTED_POINTS)
        self.assertEqual(status.desktop.current, DESKTOP_CURRENT)
        self.assertEqual(status.desktop.maximum, DESKTOP_MAX)
        self.assertEqual(status.mobile.current, MOBILE_CURRENT)
        self.assertEqual(status.mobile.maximum, MOBILE_MAX)
        self.assertFalse(status.desktop.complete)

    def test_complete_card_detected(self):
        fixture = {
            'userStatus': {
                'availablePoints': 0,
                'dailySetProgress': [
                    {
                        'dailyProgress': [
                            {
                                'activityType': 'BingSearchDesktopPC',
                                'attributes': {'currentProgress': 30, 'maxProgress': 30},
                            }
                        ]
                    }
                ],
            }
        }
        self.assertTrue(rewards.parse_userstatus(fixture).desktop.complete)

    def test_unknown_schema_degrades_to_points(self):
        status = rewards.parse_userstatus({'userStatus': {'availablePoints': 99}})
        self.assertEqual(status.points, 99)
        self.assertIsNone(status.desktop.current)
        self.assertFalse(status.desktop.complete)

    def test_accepts_json_string(self):
        status = rewards.parse_userstatus(json.dumps(USERSTATUS_FIXTURE))
        self.assertEqual(status.points, EXPECTED_POINTS)


if __name__ == '__main__':
    unittest.main()
