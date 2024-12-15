import json
from selenium_driverless import webdriver
from selenium_driverless.types.by import By
from src.producer.crawlers.util import (
    not_cached,
    send_job_to_queue,
    try_attempts,
    load_cookies,
    update_cookies,
    add_to_cache,
)
import time
import random

with open("src/producer/crawlers/blocked.json", "r") as f:
    company_blacklist = set(company.lower() for company in json.load(f))

url = "https://www.indeed.com/jobs?q=%28%28%22Software%22+OR+%22Backend%22+OR+%22DevOps%22+OR+%22Site+Reliability%22+OR+%22Infrastructure%22+OR+%22AI%22+OR+%22Machine+Learning%22+OR+%22Data%22+OR+%22Platform%22%29+AND+%28%22Engineer%22+OR+%22Developer%22+OR+%22Specialist%22+OR+%22Technologist%22%29%29+NOT+%28%22Senior%22+OR+%22Sr.%22+OR+%22Staff%22+OR+%22Lead%22+OR+%22Principal%22+OR+%22Manager%22+OR+%22Director%22%29&l=San+Francisco+Bay+Area%2C+CA&sort=date&radius=50&from=searchOnHP&rq=1&rsIdx=0&fromage=last"


async def get_job_links(driver: webdriver.Chrome):
    await load_cookies(driver, "src/producer/crawlers/cookies/indeed.json")
    await driver.get(url)
    time.sleep(10)
    job_elements = await try_attempts(
        lambda: driver.find_elements(By.CSS_SELECTOR, "div.job_seen_beacon"),
        0.5,
        20,
        Exception("Could not find job elements"),
    )
    jobs = []
    for job_element in job_elements[:15]:
        job_id = (
            (
                (await job_element.get_attribute("outerHTML"))
                .split('data-jk="')[1]
                .split('"')[0]
            )
            + "_indeed"
        )
        try:
            company = await job_element.find_element(
                By.CSS_SELECTOR, "[data-testid='company-name']"
            )
            company = await company.text
        except Exception:
            company = "Unknown"
        if not_cached(job_id) == 200:
            if company.lower() in company_blacklist:
                add_to_cache(job_id)
                continue
            clickable = await job_element.find_element(By.CSS_SELECTOR, "a[data-jk]")
            await clickable.click()
            description_container = await try_attempts(
                lambda: driver.find_element(By.ID, "jobDescriptionText"),
                0.5,
                10,
                Exception("Description container not found"),
            )
            elements = await description_container.find_elements(By.XPATH, ".//*")
            texts = []
            for elem in elements:
                if not await elem.find_elements(By.XPATH, "./*"):
                    text = (await elem.text).strip()
                    if text:
                        texts.append(text)
            description = "\n".join(texts)
            job_title = await job_element.find_element(By.CSS_SELECTOR, ".jobTitle")
            job_title = await job_title.text
            job_title = job_title.strip()
            job_link = "https://www.indeed.com/applystart?jk=" + job_id.split("_")[0]
            job = {
                "id": job_id,
                "title": job_title,
                "link": job_link,
                "description": description,
                "company": company,
            }
            jobs.append(job)
            send_job_to_queue(job)
            time.sleep(random.randint(1, 4))
    await update_cookies(driver, "src/producer/crawlers/cookies/indeed.json")
    return len(jobs)
