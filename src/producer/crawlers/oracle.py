import time
import random

from selenium_driverless import webdriver
from selenium_driverless.types.by import By
from src.producer.crawlers.util import (
    try_attempts,
    send_job_to_queue,
    not_cached,
    setup_logger,
)


url = "https://careers.oracle.com/jobs/#en/sites/jobsearch/requisitions?lastSelectedFacet=AttributeChar29&location=United+States&locationId=300000000149325&mode=location&selectedCategoriesFacet=300000001917356%3B300000001917346&selectedFlexFieldsFacets=%22AttributeChar12%7CLess+than+10+applicants%7C%7CAttributeChar6%7CSee+Job+Description%3B0+to+2%2B+years%3BNot+Applicable%7C%7CAttributeChar29%7CIndividual+Contributor%22&sortBy=POSTING_DATES_DESC"

logger = setup_logger("oracle_crawler", "oracle_crawler.log")
logger.error("Oracle crawler started")


async def get_job_links(driver: webdriver.Chrome):
    try:
        await driver.get(url)
        time.sleep(10)

        job_elements = await try_attempts(
            lambda: driver.find_elements(By.CSS_SELECTOR, "div.job-grid-item__link"),
            0.5,
            20,
            Exception("Could not find job-grid-item__link elements"),
        )

        jobs = []
        for job_element in job_elements:
            try:
                job_id = await job_element.get_attribute("id")
                job_id = f"{job_id}_oracle"
                if not_cached(job_id) == 200:
                    company = "Oracle"

                    job_title_elem = await try_attempts(
                        lambda: job_element.find_element(
                            By.CSS_SELECTOR, "span.job-tile__title"
                        ),
                        0.5,
                        10,
                        Exception(f"Could not find job title element for job {job_id}"),
                    )
                    job_title = await job_title_elem.text
                    job_title = job_title.strip()

                    job_link = f"https://careers.oracle.com/jobs/#en/sites/jobsearch/job/{job_id.split('_')[0]}/"

                    job_data = {
                        "id": job_id,
                        "title": job_title,
                        "link": job_link,
                        "company": company,
                    }
                    jobs.append(job_data)
            except Exception as e:
                logger.error(f"Error processing job element: {e}", exc_info=True)

        for job in jobs:
            await process_job(driver, job)

        if len(jobs) > 0:
            await driver.get(url)
        return len(job_elements)
    except Exception as e:
        logger.error(f"Error in get_job_links: {e}", exc_info=True)


async def process_job(driver: webdriver.Chrome, job):
    try:
        await driver.get(job["link"])
        description_container = await try_attempts(
            lambda: driver.find_element(
                By.CSS_SELECTOR, "div.job-details__description-content.basic-formatter"
            ),
            0.5,
            15,
            Exception("Job description container not found"),
        )

        elements = await description_container.find_elements(By.XPATH, ".//*")
        texts = []
        for elem in elements:
            if not await elem.find_elements(By.XPATH, "./*"):
                text = (await elem.text).strip()
                if text:
                    texts.append(text)

        description = "\n".join(texts)
        job["description"] = description
        send_job_to_queue(job)
        time.sleep(random.randint(3, 6))
    except Exception as e:
        logger.error(f"Error processing job: {e}", exc_info=True)
