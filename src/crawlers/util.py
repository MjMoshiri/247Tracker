import requests
import json
from dotenv import load_dotenv
import os

load_dotenv()

API_BASE_URL = "http://localhost:" + str(os.getenv('QUEUE_API_PORT'))

def check_item_in_queue(key):
    url = f"{API_BASE_URL}/check"
    params = {'key': key}
    response = requests.get(url, params=params)
    return response.status_code

def send_job_to_queue(job):
    url = f"{API_BASE_URL}/submit"
    headers = {'Content-Type': 'application/json'}
    response = requests.post(url, headers=headers, data=json.dumps(job))
    return response.status_code