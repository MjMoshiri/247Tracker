import time
from selenium_driverless import webdriver
from selenium_driverless.types.by import By
from src.producer.crawlers.util import (
    not_cached,
    send_job_to_queue,
    try_attempts,
    setup_logger,
)

url = "https://www.ibm.com/careers/search?field_keyword_08[0]=Software%20Engineering&field_keyword_08[1]=Infrastructure%20%26%20Technology&field_keyword_08[2]=Cloud&field_keyword_08[3]=Data%20%26%20Analytics&field_keyword_18[0]=Professional&field_keyword_18[1]=Entry%20Level&field_keyword_05[0]=United%20States&q=software%20engineer&sort=dcdate_desc"

logger = setup_logger("ibm_crawler", "ibm_crawler.log")
logger.error("IBM crawler started")


async def get_job_links(driver: webdriver.Chrome):
    try:
        await driver.get(url)
        time.sleep(5)
        job_containers = await try_attempts(
            lambda: driver.find_elements(
                By.CSS_SELECTOR, "div.bx--card-group__cards__col"
            ),
            0.5,
            20,
            Exception("Could not find IBM job containers"),
        )
        jobs = []
        for job_container in job_containers:
            try:
                link_element = await job_container.find_element(By.CSS_SELECTOR, "a")
                job_link = await link_element.get_attribute("href")
                job_id = (
                    job_link.split("jobId=")[1].split("&")[0] + "_ibm"
                    if "jobId=" in job_link
                    else job_link.split("job/")[1].split("/")[0] + "_ibm"
                )
                title_element = await job_container.find_element(
                    By.CSS_SELECTOR, "div.bx--card__heading"
                )
                job_title = await title_element.text

                if not_cached(job_id) == 200:
                    jobs.append(
                        {
                            "id": job_id,
                            "title": job_title,
                            "location": "",
                            "link": job_link,
                            "description": "",
                            "company": "IBM",
                        }
                    )
            except Exception as e:
                logger.error(f"Error processing IBM job container: {e}", exc_info=True)

        for job in jobs:
            try:
                job["description"] = await get_job_description(driver, job["link"])
                send_job_to_queue(job)
                print(job)
                time.sleep(4)
            except Exception as e:
                logger.error(f"Error processing IBM job: {e}", exc_info=True)

        return len(job_containers)
    except Exception as e:
        logger.error(f"Error in get_job_links: {e}", exc_info=True)


async def get_job_description(driver: webdriver.Chrome, job_link: str):
    try:
        await driver.get(job_link)
        desc_container = await try_attempts(
            lambda: driver.find_element(
                By.CSS_SELECTOR, 'div[data-field="description"]'
            ),
            0.5,
            20,
            Exception("Could not find description element on IBM job page"),
        )
        return await desc_container.text
    except Exception as e:
        logger.error(f"Error in get_job_description: {e}", exc_info=True)
        return ""
