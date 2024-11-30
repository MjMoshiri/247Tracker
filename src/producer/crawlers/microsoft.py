from selenium_driverless import webdriver
from selenium_driverless.types.by import By
from src.producer.crawlers.util import not_cached, send_job_to_queue
import asyncio
import time

url = "https://jobs.careers.microsoft.com/global/en/search?lc=California%2C%20United%20States&lc=Washington%2C%20United%20States&p=Software%20Engineering&l=en_us&pg=1&pgSz=20&o=Recent&flt=true"


async def get_job_links(driver: webdriver.Chrome):
    await driver.get(url, wait_load=True)
    while True:
        try:
            list_element = await driver.find_element(
                By.CSS_SELECTOR, 'div.ms-List[role="list"]'
            )
            break
        except:
            await asyncio.sleep(0.5)
    job_elements = await list_element.find_elements(
        By.CSS_SELECTOR, 'div[role="listitem"]'
    )
    jobs = []

    for job_element, _ in zip(job_elements, range(20)):
        job_title_element = await job_element.find_element(By.CSS_SELECTOR, "h2")
        job_title = await job_title_element.text

        job_location_element = await job_element.find_element(
            By.XPATH, "//span[contains(text(), 'United States')]"
        )
        job_location = await job_location_element.text

        job_id_element = await job_element.find_element(
            By.CSS_SELECTOR, 'div[aria-label^="Job item"]'
        )
        text = await job_id_element.get_attribute("outerHTML")
        job_id = text.split("Job item ")[1].split('"')[0]

        job_link = f"https://jobs.careers.microsoft.com/global/en/job/{job_id}"
        if not_cached(job_id + "_microsoft") == 200:
            jobs.append(
                {
                    "id": job_id + "_microsoft",
                    "title": job_title,
                    "location": job_location,
                    "link": job_link,
                    "description": "",
                    "company": "Microsoft",
                }
            )

    for job in jobs:
        job["description"] = await get_job_description(driver, job["link"])
        send_job_to_queue(job)
        time.sleep(2)


async def get_job_description(driver: webdriver.Chrome, job_link: str):
    await driver.get(job_link)
    while True:
        try:
            qualifications_element = await driver.find_element(
                By.XPATH, "//h3[contains(text(), 'Qualifications')]"
            )
            break
        except:
            await asyncio.sleep(0.5)
    parent_element = await qualifications_element.find_element(By.XPATH, "..")
    description_elements = await parent_element.find_elements(By.XPATH, "./*")
    description = ""
    for element in description_elements:
        text = await element.text
        if text:
            description += text + "\n"
    return description

