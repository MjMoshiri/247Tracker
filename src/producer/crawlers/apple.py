from selenium_driverless import webdriver
from selenium_driverless.types.by import By
from src.producer.crawlers.util import not_cached, send_job_to_queue, try_attempts
import time

url = "https://jobs.apple.com/en-us/search?location=united-states-USA&team=apps-and-frameworks-SFTWR-AF+cloud-and-infrastructure-SFTWR-CLD+core-operating-systems-SFTWR-COS+devops-and-site-reliability-SFTWR-DSR+engineering-project-management-SFTWR-EPM+information-systems-and-technology-SFTWR-ISTECH+machine-learning-and-ai-SFTWR-MCHLN+security-and-privacy-SFTWR-SEC+software-quality-automation-and-tools-SFTWR-SQAT+wireless-software-SFTWR-WSFT"


async def get_job_links(driver: webdriver.Chrome):
    await driver.get(url)
    job_elements = await try_attempts(
        lambda: driver.find_elements(By.CSS_SELECTOR, 'tbody[id^="accordion_"]'),
        0.5,
        20,
        Exception("Could not find job elements"),
    )
    jobs = []
    for job_element, _ in zip(job_elements, range(20)):
        job_link_element = await job_element.find_element(
            By.CSS_SELECTOR, "a.table--advanced-search__title"
        )
        job_id = (await job_link_element.get_attribute("id")).split("_")[1] + "_apple"
        job_title = await job_link_element.text
        job_link = await job_link_element.get_attribute("href")
        if not_cached(job_id) == 200:
            job = {
                "id": job_id,
                "title": job_title,
                "link": job_link,
                "description": "",
                "company": "Apple",
            }
            jobs.append(job)
    for job in jobs:
        job["description"] = await get_job_description(driver, job["link"])
        send_job_to_queue(job)
        time.sleep(2)
    return len(job_elements)


async def get_job_description(driver: webdriver.Chrome, job_link: str):
    await driver.get(job_link)
    summary = await try_attempts(
        lambda: driver.find_element(By.ID, "jd-job-summary"),
        0.5,
        2,
    )
    if summary:
        summary = await summary.text
    description = await try_attempts(
        lambda: driver.find_element(By.ID, "jd-description")
    )
    if description:
        description = await description.text
    minimum_qualifications = await try_attempts(
        lambda: driver.find_elements(By.ID, "jd-minimum-qualifications")
    )
    minimum_qualifications_text = ""
    for item in minimum_qualifications:
        minimum_qualifications_text += "-" + await item.text
    preferred_qualifications = await try_attempts(
        lambda: driver.find_elements(By.ID, "jd-preferred-qualifications"),
    )
    preferred_qualifications_text = ""
    for item in preferred_qualifications:
        preferred_qualifications_text += "-" + await item.text

    if (
        not summary
        and not description
        and not minimum_qualifications_text
        and not preferred_qualifications_text
    ):
        raise Exception("All job description fields are None")

    return (
        "SUMMARY: " + summary + "\n"
        "DESCRIPTION: " + description + "\n"
        "MINIMUM QUALIFICATIONS: " + minimum_qualifications_text + "\n"
        "PREFERRED QUALIFICATIONS: " + preferred_qualifications_text
    )
