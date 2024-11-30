import asyncio
import heapq
import time
from selenium_driverless import webdriver
from src.producer.crawlers.apple import get_job_links as get_apple_job_links
from src.producer.crawlers.microsoft import get_job_links as get_microsoft_job_links
import random

class PriorityQueue:
    def __init__(self):
        self.queue = []
        self.counter = 0

    def put(self, priority, item):
        heapq.heappush(self.queue, (priority, self.counter, item))
        self.counter += 1

    def get(self):
        return heapq.heappop(self.queue)[2]

    def empty(self):
        return len(self.queue) == 0

    def peek_priority(self):
        if not self.empty():
            return self.queue[0][0]
        return None


async def run_crawler(crawler, queue, interval_range):
    try:
        await crawler()
    except Exception as e:
        print(f"Task {crawler.__name__} failed with error: {e}")
    finally:
        next_run = time.time() + random.randint(*interval_range)
        queue.put(next_run, crawler)

async def schedule_crawlers(queue, semaphore, interval_range=(60, 100)):
    while True:
        if not queue.empty():
            next_run = queue.peek_priority()
            now = time.time()
            if next_run <= now:
                crawler = queue.get()
                await semaphore.acquire()
                asyncio.create_task(
                    handle_crawler(crawler, queue, semaphore, interval_range)
                )
            else:
                sleep_time = min(next_run - now, 1) 
                await asyncio.sleep(sleep_time)
        else:

            await asyncio.sleep(1)

async def handle_crawler(crawler, queue, semaphore, interval_range):
    try:
        await run_crawler(crawler, queue, interval_range)
    finally:
        semaphore.release()

async def autopilot(crawlers, num_instances=5, interval_range=(60, 100)):
    queue = PriorityQueue()
    current_time = time.time()
    for crawler in crawlers:
        queue.put(current_time, crawler)

    semaphore = asyncio.Semaphore(num_instances)
    await schedule_crawlers(queue, semaphore, interval_range)

async def apple_crawler():
    async with webdriver.Chrome() as driver:
        await get_apple_job_links(driver)

async def microsoft_crawler():
    async with webdriver.Chrome() as driver:
        await get_microsoft_job_links(driver)

async def main():
    crawlers = [apple_crawler, microsoft_crawler] 
    await autopilot(crawlers)

if __name__ == "__main__":
    asyncio.run(main())
