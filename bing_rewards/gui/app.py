#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2020 jack-mil
#
# SPDX-License-Identifier: MIT

"""Web-based GUI for Bing Rewards concurrent multi-instance control."""

import json
import logging
import os
import sys
import threading
import time
from pathlib import Path
from typing import Dict, List

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify, render_template, request
from flask_cors import CORS

from bing_rewards.browser_manager import BrowserInstance, BrowserManager, BrowserState
from bing_rewards.concurrency_controller import ConcurrencyConfig, ConcurrencyController
from bing_rewards.event_bus import EventBus, EventType
from bing_rewards.profile_config import ProfileConfig, ProfileManager
from bing_rewards.utils.chrome_finder import find_chrome_profiles

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Global state
gui_state = {
    "controller": None,
    "event_bus": None,
    "profile_manager": None,
    "is_running": False,
    "instances": {},
    "statistics": {
        "total_searches": 0,
        "successful_instances": 0,
        "failed_instances": 0,
        "start_time": None,
    },
    "events": [],
}


def init_state():
    """Initialize GUI state."""
    gui_state["event_bus"] = EventBus()
    gui_state["profile_manager"] = ProfileManager()

    # Subscribe to events
    def on_event(event):
        # Store recent events (keep last 100)
        gui_state["events"].append(
            {
                "type": event.event_type.name,
                "timestamp": event.timestamp.isoformat(),
                "profile": event.profile_name,
                "data": event.data,
            }
        )
        if len(gui_state["events"]) > 100:
            gui_state["events"].pop(0)

    gui_state["event_bus"].subscribe(EventType.INSTANCE_LAUNCHED, on_event)
    gui_state["event_bus"].subscribe(EventType.INSTANCE_TERMINATED, on_event)
    gui_state["event_bus"].subscribe(EventType.SEARCH_COMPLETED, on_event)
    gui_state["event_bus"].subscribe(EventType.PROGRESS_UPDATE, on_event)
    gui_state["event_bus"].subscribe(EventType.INSTANCE_ERROR, on_event)


@app.route("/")
def index():
    """Serve the main GUI page."""
    return render_template("gui.html")


@app.route("/api/status")
def get_status():
    """Get current system status."""
    return jsonify(
        {
            "is_running": gui_state["is_running"],
            "instances": [
                {
                    "id": inst.instance_id,
                    "profile": inst.profile.profile_name,
                    "state": inst.state.name,
                    "search_count": inst.search_count,
                    "pid": inst.get_pid(),
                }
                for inst in gui_state["controller"].get_active_instances()
            ]
            if gui_state["controller"]
            else [],
            "statistics": gui_state["statistics"],
        }
    )


@app.route("/api/profiles")
def get_profiles():
    """Get available Chrome profiles."""
    # Get ALL saved profiles (including isolated ones)
    all_saved_profiles = gui_state["profile_manager"].get_active_profiles()
    saved_names = {p.profile_name for p in all_saved_profiles}

    # Discover Chrome profiles
    chrome_profiles = find_chrome_profiles()

    # Merge information
    profiles = []

    # Only add isolated profiles (hide regular Chrome profiles)
    for profile in all_saved_profiles:
        if profile.is_isolated:
            profile_data = {
                "name": profile.profile_name,
                "display_name": f"{profile.profile_name} (Isolated)",
                "path": str(profile.user_data_dir) if profile.user_data_dir else "Temporary",
                "is_default": False,
                "is_saved": True,
                "is_isolated": profile.is_isolated,
                "is_temporary": profile.is_temporary,
            }
            profiles.append(profile_data)

    return jsonify(profiles)


@app.route("/api/delete-profile", methods=["POST"])
def delete_profile():
    """Delete an isolated profile."""
    data = request.json
    profile_name = data.get("profile_name")

    if not profile_name:
        return jsonify({"error": "Profile name required"}), 400

    try:
        # Get the profile
        profile = gui_state["profile_manager"].get_profile(profile_name)
        if not profile:
            return jsonify({"error": "Profile not found"}), 404

        if not profile.is_isolated:
            return jsonify({"error": "Can only delete isolated profiles"}), 400

        # Delete the profile (this also removes temp directory)
        gui_state["profile_manager"].remove_profile(profile_name)

        logger.info(f"Deleted profile: {profile_name}")

        return jsonify({"status": "success", "message": f"Profile '{profile_name}' deleted"})

    except Exception as e:
        logger.error(f"Error deleting profile: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/config", methods=["GET"])
def get_config():
    """Get current configuration."""
    return jsonify(
        {
            "max_instances": 10,
            "eco_mode": False,
            "throttling": True,
            "desktop_count": 33,
            "mobile_count": 23,
        }
    )


@app.route("/api/config", methods=["POST"])
def update_config():
    """Update configuration."""
    data = request.json
    logger.info(f"Updating config: {data}")
    # Store config for next run
    return jsonify({"status": "success"})


@app.route("/api/start", methods=["POST"])
def start_automation():
    """Start concurrent automation."""
    if gui_state["is_running"]:
        return jsonify({"error": "Already running"}), 400

    data = request.json
    profiles = data.get("profiles", [])
    max_instances = data.get("max_instances", 10)
    eco_mode = data.get("eco_mode", False)
    desktop_count = data.get("desktop_count", 33)
    mobile_count = data.get("mobile_count", 23)

    if not profiles:
        return jsonify({"error": "No profiles selected"}), 400

    logger.info(f"Starting automation with {len(profiles)} profiles")

    # Create controller
    config = ConcurrencyConfig(
        max_instances=max_instances,
        enable_throttling=not data.get("no_throttle", False),
        eco_mode=eco_mode,
    )

    gui_state["controller"] = ConcurrencyController(config=config, event_bus=gui_state["event_bus"])
    gui_state["is_running"] = True
    gui_state["statistics"]["start_time"] = time.time()

    # Start in background thread
    def run_automation():
        logger.info("📍 run_automation() called")
        try:
            logger.info("📦 Importing modules...")
            from bing_rewards.app import execute_searches_for_instance, word_generator
            from bing_rewards.options import get_options
            logger.info("✓ Imports successful")

            # Load profiles
            logger.info(f"📂 Loading {len(profiles)} profiles...")
            profile_configs = []
            for profile_name in profiles:
                profile = gui_state["profile_manager"].get_profile(profile_name)
                if not profile:
                    logger.warning(f"  Profile '{profile_name}' not found, creating...")
                    profile = ProfileConfig(profile_name=profile_name)
                    gui_state["profile_manager"].add_profile(profile)
                profile_configs.append(profile)
                logger.info(f"  ✓ Loaded: {profile.profile_name}")

            logger.info(f"✓ Loaded {len(profile_configs)} profiles")

            # Get options
            logger.info("⚙️ Getting options...")
            options = get_options()
            options.desktop_count = desktop_count
            options.mobile_count = mobile_count
            logger.info(f"✓ Options: desktop={desktop_count}, mobile={mobile_count}")

            # Word generator factory
            logger.info("📝 Creating word generator factory...")
            def words_gen_factory():
                return word_generator()
            logger.info("✓ Word generator factory ready")

            # Execute searches
            logger.info("🚀 Starting concurrent searches...")
            logger.info(f"   Profiles: {[p.profile_name for p in profile_configs]}")
            logger.info(f"   Options: browser_path={getattr(options, 'browser_path', 'NOT SET')}")

            try:
                results = gui_state["controller"].run_concurrent_searches(
                    profiles=profile_configs,
                    words_gen_factory=words_gen_factory,
                    search_executor=lambda inst, wg: execute_searches_for_instance(
                        inst, wg, options, desktop_count, mobile_count
                    ),
                    options=options,
                )
                logger.info(f"✓ Concurrent searches completed: {len(results)} results")
            except Exception as controller_error:
                logger.error(f"❌ Controller error: {controller_error}", exc_info=True)
                raise

            # Update statistics
            successful = sum(1 for r in results if r.success)
            failed = len(results) - successful
            total_searches = sum(r.searches_completed for r in results)

            gui_state["statistics"]["successful_instances"] = successful
            gui_state["statistics"]["failed_instances"] = failed
            gui_state["statistics"]["total_searches"] = total_searches

            logger.info(f"✅ Automation completed: {successful} successful, {failed} failed")
            logger.info(f"   - Total searches: {total_searches}")

        except Exception as e:
            logger.error(f"❌ Automation error: {e}", exc_info=True)
            gui_state["event_bus"].emit(
                EventType.INSTANCE_ERROR,
                source="GUI",
                profile_name="SYSTEM",
                data={"error": str(e)},
            )
        finally:
            logger.info("🏁 Cleaning up...")
            gui_state["is_running"] = False
            gui_state["controller"] = None
            logger.info("✓ Cleanup complete")

    thread = threading.Thread(target=run_automation, daemon=True)
    thread.start()
    logger.info(f"🧵 Thread started: {thread.name}")

    return jsonify({"status": "started", "profiles": profiles})


@app.route("/api/stop", methods=["POST"])
def stop_automation():
    """Stop concurrent automation."""
    if not gui_state["is_running"]:
        return jsonify({"error": "Not running"}), 400

    logger.info("Stopping automation")

    if gui_state["controller"]:
        gui_state["controller"].request_shutdown()
        time.sleep(2)
        gui_state["controller"].shutdown()

    gui_state["is_running"] = False
    gui_state["controller"] = None

    return jsonify({"status": "stopped"})


@app.route("/api/manual-login", methods=["POST"])
def manual_login():
    """Launch browsers for manual authentication."""
    data = request.json
    profiles = data.get("profiles", [])

    logger.info(f"Launching {len(profiles)} browsers for manual login")

    launched = []
    for profile_name in profiles:
        try:
            # Launch browser without automation
            from bing_rewards.app import browser_cmd, open_browser
            from bing_rewards.options import get_options

            options = get_options()
            cmd = browser_cmd(options.browser_path, options.desktop_agent, profile_name)
            chrome = open_browser(cmd)
            launched.append(
                {
                    "profile": profile_name,
                    "pid": chrome.pid,
                    "status": "launched",
                }
            )
        except Exception as e:
            launched.append(
                {
                    "profile": profile_name,
                    "error": str(e),
                    "status": "failed",
                }
            )

    return jsonify({"launched": launched})


@app.route("/api/events")
def get_events():
    """Get recent events."""
    return jsonify(gui_state["events"][-50:])


@app.route("/api/instances/<instance_id>")
def get_instance(instance_id):
    """Get specific instance details."""
    if gui_state["controller"]:
        inst = gui_state["controller"].get_instance(instance_id)
        if inst:
            return jsonify(
                {
                    "id": inst.instance_id,
                    "profile": inst.profile.profile_name,
                    "state": inst.state.name,
                    "search_count": inst.search_count,
                    "error": inst.error_message,
                }
            )

    return jsonify({"error": "Instance not found"}), 404


@app.route("/api/instances/<instance_id>/close", methods=["POST"])
def close_instance(instance_id):
    """Close a specific browser instance."""
    if gui_state["controller"]:
        controller = gui_state["controller"]
        inst = controller.get_instance(instance_id)
        if inst:
            inst.close()
            return jsonify({"status": "closed"})

    return jsonify({"error": "Instance not found"}), 404


@app.route("/api/create-isolated-profile", methods=["POST"])
def create_isolated_profile():
    """Create a new isolated browser profile."""
    data = request.json
    name = data.get("name", "")

    if not name:
        return jsonify({"error": "Profile name required"}), 400

    try:
        # Create isolated profile
        profile = ProfileManager.create_isolated_profile(
            name=name,
            temporary=True  # Use temporary directory
        )

        # Save to profile manager
        gui_state["profile_manager"].add_profile(profile)

        logger.info(f"Created isolated profile: {name} at {profile.user_data_dir}")

        return jsonify({
            "status": "success",
            "profile": {
                "name": profile.profile_name,
                "path": str(profile.user_data_dir),
                "is_temporary": profile.is_temporary,
                "is_isolated": profile.is_isolated,
            }
        })

    except Exception as e:
        logger.error(f"Failed to create isolated profile: {e}")
        return jsonify({"error": str(e)}), 500


def main():
    """Start the GUI server."""
    print("=" * 70)
    print("Bing Rewards Web GUI")
    print("=" * 70)
    print()
    print("Starting web server...")
    print()
    print("Open your browser to: http://localhost:5000")
    print()
    print("Press CTRL+C to quit")
    print("=" * 70)

    # Initialize state
    init_state()

    # Run Flask app
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)


if __name__ == "__main__":
    main()
