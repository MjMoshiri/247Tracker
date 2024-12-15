import asyncio

import time
import logging
from selenium_driverless import webdriver

# from src.producer.crawlers.apple import get_job_links as apple
# from src.producer.crawlers.microsoft import get_job_links as microsoft
from src.producer.crawlers.linkedin import get_job_links as linkedin
from src.producer.crawlers.indeed import get_job_links as indeed
import random
from dotenv import load_dotenv
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()


async def run_crawler(crawler, interval_range, queue: asyncio.Queue, semaphore):
    async with semaphore:
        try:
            options = webdriver.ChromeOptions()
            options.add_argument("--force-device-scale-factor=0.6")
            options.add_argument("--high-dpi-support=0.6")
            async with webdriver.Chrome(options=options) as driver:
                await driver.minimize_window()
                result = await crawler(driver)
                logger.info(f"{crawler.__module__.split('.')[-1].capitalize()} returned: {result} at {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}")
        except Exception as e:
            logger.error(f"Task {crawler.__name__} failed with error: {e}")
        finally:
            next_run = time.time() + random.randint(*interval_range)
            await queue.put((next_run, crawler, interval_range))


async def schedule_crawlers(queue: asyncio.Queue, semaphore):
    while True:
        if not queue.empty():
            next_run, crawler, interval_range = await queue.get()
            now = time.time()
            if next_run <= now:
                asyncio.create_task(
                    run_crawler(crawler, interval_range, queue, semaphore)
                )
            else:
                await queue.put((next_run, crawler, interval_range))
                sleep_time = min(next_run - now, 1)
                await asyncio.sleep(sleep_time)
        else:
            await asyncio.sleep(1)


async def autopilot(crawlers_with_intervals, num_instances=5):
    queue = asyncio.Queue()
    current_time = time.time()
    for crawler, interval_range in crawlers_with_intervals:
        await queue.put((current_time, crawler, interval_range))

    semaphore = asyncio.Semaphore(num_instances)
    await schedule_crawlers(queue, semaphore)


async def main():
    crawlers_with_intervals = [(indeed, (120, 180)), (linkedin, (120, 180))]
    num_instances = int(os.getenv("PRODUCER_CONCURRENT_DRIVERS", 5))
    await autopilot(crawlers_with_intervals, num_instances)


if __name__ == "__main__":
    asyncio.run(main())
