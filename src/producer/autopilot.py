import asyncio

import time
import logging
from selenium_driverless import webdriver

# from src.producer.crawlers.apple import get_job_links as apple
# from src.producer.crawlers.microsoft import get_job_links as microsoft
from src.producer.crawlers.linkedin import get_job_links as linkedin
import random
from dotenv import load_dotenv
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()


async def run_crawler(crawler, queue: asyncio.Queue, semaphore, interval_range):
    async with semaphore:
        try:
            options = webdriver.ChromeOptions()
            options.add_argument("--force-device-scale-factor=0.6")
            options.add_argument("--high-dpi-support=0.6")
            async with webdriver.Chrome(options=options) as driver:
                await driver.minimize_window()
                result = await crawler(driver)
                logger.info(f"Task {crawler.__name__} returned: {result}")
        except Exception as e:
            logger.error(f"Task {crawler.__name__} failed with error: {e}")
        finally:
            next_run = time.time() + random.randint(*interval_range)
            await queue.put((next_run, crawler))


async def schedule_crawlers(queue: asyncio.Queue, semaphore, interval_range=(60, 80)):
    while True:
        if not queue.empty():
            next_run, crawler = await queue.get()
            now = time.time()
            if next_run <= now:
                asyncio.create_task(
                    run_crawler(crawler, queue, semaphore, interval_range)
                )
            else:
                await queue.put((next_run, crawler))
                sleep_time = min(next_run - now, 1)
                await asyncio.sleep(sleep_time)
        else:
            await asyncio.sleep(1)


async def autopilot(crawlers, num_instances=5, interval_range=(60, 80)):
    queue = asyncio.Queue()
    current_time = time.time()
    for crawler in crawlers:
        await queue.put((current_time, crawler))

    semaphore = asyncio.Semaphore(num_instances)
    await schedule_crawlers(queue, semaphore, interval_range)


async def main():
    crawlers = [linkedin]
    num_instances = int(os.getenv("PRODUCER_CONCURRENT_DRIVERS", 5))
    await autopilot(crawlers, num_instances, interval_range=(90, 120))


if __name__ == "__main__":
    asyncio.run(main())
