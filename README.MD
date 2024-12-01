# Live Tracker

This project is a job crawler and queue system designed to scrape job listings from various company websites and process them through a queue system as soon as they are published (2 minutes delay max).The project is divided into three main components: producer, consumer, and queue API.

## Components

### Producer
The producer component is responsible for crawling job listings from company websites. It includes crawlers for different companies such as Microsoft and Apple.

- **Crawlers**: Located in `src/producer/crawlers/`, these scripts use Selenium to scrape job listings.
- **Autopilot**: Located in `src/producer/autopilot.py`, this script schedules and runs the crawlers at specified intervals.

### Consumer
The consumer component processes the job listings from the queue.

- **Consumer Script**: Located in `src/consumer/consumer.py`, this script consumes messages from a RabbitMQ queue and processes job listings.

### Queue API
The queue API component provides endpoints to interact with the queue system.

- **API**: Located in `src/queue_api/`, this Go application provides endpoints to check and submit jobs to the queue.

## Setup (WIP)

1. **Environment Variables**: Configure the environment variables in the `.env` file as needed.
   ```sh
   cp .env.example .env
   ```
2. **Docker**: Use `docker-compose` to build and run the services.
   ```sh
   docker-compose up --build
    ```
3. **Run Producer**: Run the producer service to start crawling job listings.
    ```sh
    python -m src.producer.autopilot
    ```

