import requests
import json
from dotenv import load_dotenv
import os
import asyncio

load_dotenv()

API_BASE_URL = "http://localhost:" + str(os.getenv('QUEUE_API_PORT'))

def not_cached(key):
    url = f"{API_BASE_URL}/check"
    params = {'key': key}
    response = requests.get(url, params=params)
    return response.status_code

def send_job_to_queue(job):
    url = f"{API_BASE_URL}/submit"
    headers = {'Content-Type': 'application/json'}
    response = requests.post(url, headers=headers, data=json.dumps(job))
    return response.status_code

async def try_attempts(coroutine, delay =0.1, max_attempts=2, exception = None):
    for attempt in range(max_attempts):
        try:
            return await coroutine()
        except:
            if attempt == max_attempts - 1:
                if exception:
                    raise exception
                return None
            await asyncio.sleep(delay)