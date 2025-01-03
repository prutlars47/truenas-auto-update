import logging
import os
import time
import requests
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_URL = os.getenv("BASE_URL")
API_KEY = os.getenv("API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

if not BASE_URL or not API_KEY:
    logger.error("BASE_URL or API_KEY is not set")
    exit(1)

BASE_URL = BASE_URL + "/api/v2.0"


def send_discord_notification(message: str):
    """
    Sends a simple text message to Discord using the configured webhook URL.
    """
    if not DISCORD_WEBHOOK_URL:
        logger.warning("DISCORD_WEBHOOK_URL is not set. Discord notification skipped.")
        return

    try:
        payload = {"content": message}
        resp = requests.post(
            DISCORD_WEBHOOK_URL,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )
        if resp.status_code != 204 and resp.status_code != 200:
            logger.warning(
                f"Discord webhook returned status {resp.status_code}: {resp.text}"
            )
    except Exception as e:
        logger.error(f"Failed to send Discord notification: {e}")


# 1) List all available apps
response = requests.get(
    f"{BASE_URL}/app",
    headers={"Authorization": f"Bearer {API_KEY}"},
    verify=False,
)

if response.status_code != 200:
    logger.error(f"Failed to fetch apps. Status: {response.status_code}, Body: {response.text}")
    send_discord_notification(
        f"**TrueNAS App Upgrade**: Unable to fetch apps (status {response.status_code})"
    )
    exit(1)

apps = response.json()
apps_with_upgrade = [app for app in apps if app["upgrade_available"]]

logger.info(f"Found {len(apps_with_upgrade)} apps with upgrade available")
send_discord_notification(
    f"**TrueNAS App Upgrade**: Found {len(apps_with_upgrade)} apps with an upgrade available."
)


def await_job(job_id):
    logger.info(f"Waiting for job {job_id} to complete...")
    return requests.post(
        f"{BASE_URL}/core/job_wait",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json=job_id,
        verify=False,
    )


# 2) Iterate over apps that need an upgrade
for app in apps_with_upgrade:
    app_name = app["name"]
    logger.info(f"Upgrading {app_name}...")
    send_discord_notification(f"**Upgrading**: {app_name}...")

    response = requests.post(
        f"{BASE_URL}/app/upgrade",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={"app_name": app["id"]},
        verify=False,
    )

    if response.status_code != 200:
        logger.error(
            f"Failed to initiate upgrade for {app_name}. Status: {response.status_code}, Body: {response.text}"
        )
        send_discord_notification(
            f"**Upgrade FAILED** for {app_name}. (Status {response.status_code})"
        )
        continue

    job_id = response.text
    job_response = await_job(job_id)

    if job_response.status_code == 200:
        logger.info(f"Upgrade of {app_name} triggered successfully")
        send_discord_notification(f"**Upgrade triggered successfully** for {app_name}.")
    else:
        logger.error(
            f"Failed to await job for {app_name}. Status: {job_response.status_code}, Body: {job_response.text}"
        )
        send_discord_notification(
            f"**Upgrade FAILED** for {app_name}. (Status {job_response.status_code})"
        )

    # Sleep briefly between upgrades to avoid rapid-fire requests
    time.sleep(1)

logger.info("Done with all upgrades.")
send_discord_notification("**TrueNAS App Upgrade**: Done with all upgrades.")
