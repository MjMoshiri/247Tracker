import requests
import json
from dotenv import load_dotenv
import os
import asyncio
from selenium_driverless import webdriver

load_dotenv()

API_BASE_URL = "http://localhost:" + str(os.getenv("QUEUE_API_PORT"))


def not_cached(key):
    url = f"{API_BASE_URL}/check"
    params = {"key": key}
    response = requests.get(url, params=params)
    return response.status_code


def add_to_cache(key):
    url = f"{API_BASE_URL}/checked"
    headers = {"Content-Type": "application/json"}
    response = requests.post(url, headers=headers, data=json.dumps({"id": key}))
    return response.status_code


def send_job_to_queue(job):
    url = f"{API_BASE_URL}/submit"
    headers = {"Content-Type": "application/json"}
    response = requests.post(url, headers=headers, data=json.dumps(job))
    return response.status_code


async def try_attempts(coroutine, delay=0.1, max_attempts=2, exception=None):
    for attempt in range(max_attempts):
        try:
            return await coroutine()
        except:
            if attempt == max_attempts - 1:
                if exception:
                    raise exception
                return None
            await asyncio.sleep(delay)


async def load_cookies(driver: webdriver.Chrome, file_address: str):
    with open(file_address, "r") as file:
        cookies = json.load(file)

    await driver.execute_cdp_cmd("Network.enable", {})

    for cookie in cookies:
        cookie_data = {
            "name": cookie.get("name"),
            "value": cookie.get("value"),
            "domain": cookie.get("domain"),
            "path": cookie.get("path"),
            "secure": cookie.get("secure"),
            "httpOnly": cookie.get("httpOnly"),
            "sameSite": cookie.get("sameSite"),
        }
        if "expirationDate" in cookie:
            cookie_data["expires"] = cookie["expirationDate"]
        await driver.execute_cdp_cmd("Network.setCookie", cookie_data)

    await driver.execute_cdp_cmd("Network.disable", {})


async def update_cookies(driver: webdriver.Chrome, file_address: str):
    with open(file_address, "r") as file:
        existing_cookies = json.load(file)

    current_cookies = await driver.get_cookies()
    existing_cookie_dict = {
        (cookie["name"], cookie["domain"], cookie["path"]): cookie
        for cookie in existing_cookies
    }

    for cookie in current_cookies:
        key = (cookie["name"], cookie["domain"], cookie["path"])
        if key in existing_cookie_dict:
            existing_cookie_dict[key].update(cookie)

    updated_cookies = list(existing_cookie_dict.values())
    with open(file_address, "w") as file:
        json.dump(updated_cookies, file, indent=4)
