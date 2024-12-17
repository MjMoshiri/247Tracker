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

url = "https://www.linkedin.com/jobs/search/?distance=100&f_TPR=r86400&geoId=90000084&keywords=((%22Software%22%20OR%20%22Backend%22%20OR%20%22DevOps%22%20OR%20%22Site%20Reliability%22%20OR%20%22Infrastructure%22%20OR%20%22AI%22%20OR%20%22Machine%20Learning%22%20OR%20%22Data%22%20OR%20%22Platform%22)%20AND%20(%22Engineer%22%20OR%20%22Developer%22%20OR%20%22Specialist%22%20OR%20%22Technologist%22))%20NOT%20(%22Senior%22%20OR%20%22Sr.%22%20OR%20%22Staff%22%20OR%20%22Lead%22%20OR%20%22Principal%22%20OR%20%22Manager%22%20OR%20%22Director%22)&origin=JOB_SEARCH_PAGE_SEARCH_BUTTON&refresh=true&sortBy=DD"


async def get_job_links(driver: webdriver.Chrome):
    await load_cookies(driver, "src/producer/crawlers/cookies/linkedin.json")
    await driver.get(url)
    time.sleep(10)
    job_elements = await try_attempts(
        lambda: driver.find_elements(By.CSS_SELECTOR, "[data-occludable-job-id]"),
        0.5,
        20,
        Exception("Could not find job elements"),
    )
    jobs = []
    for job_element in job_elements[:15]:
        job_id = (
            (await job_element.get_attribute("outerHTML"))
            .split('data-occludable-job-id="')[1]
            .split('"')[0]
        )
        job_id = job_id + "_linkedin"
        company = await job_element.find_element(
            By.CSS_SELECTOR, ".artdeco-entity-lockup__subtitle"
        )
        company = await company.text
        company = company.split(" · ")[0].strip()
        if not_cached(job_id) == 200:
            if company.lower() in company_blacklist:
                add_to_cache(job_id)
                continue
            await job_element.click()
            description_container = await try_attempts(
                lambda: driver.find_element(
                    By.CSS_SELECTOR, ".jobs-description__container"
                ),
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
            job_title = (
                await (await job_element.find_element(By.TAG_NAME, "strong")).text
            ).strip()
            job_link = "https://www.linkedin.com/jobs/view/" + job_id.split("_")[0]
            job = {
                "id": job_id,
                "title": job_title,
                "link": job_link,
                "description": description,
                "company": company,
            }
            jobs.append(job)
            send_job_to_queue(job)
            time.sleep(random.randint(3, 6))
    await update_cookies(driver, "src/producer/crawlers/cookies/linkedin.json")
    return len(jobs)
