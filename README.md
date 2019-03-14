# Question: Optimal configuration for a python worker (crawler + save db) on celery

I have multiple python workers that crawl certain websites, parse the data and store them on a Postgres database.

It's unclear for me how to architect the code to optimize the server resources (deployed on microservices multiple pods on kubernetes). Let's assume that there's no rate limit for the request.

For demo purpose, I created a sample code that gets the top 10k websites, store them on the db - and then crawl search results from Bing (and store them as well). This can be extended to 1M websites.

`Celery` is using the pool `gevent` since the worker have many network I/O. 
I added `psycogreen` to patch postgres as well to avoid bottlenecks.
To avoid reaching Postgres max connections, I added `pgbouncer` as database proxy.

The code is located on:
https://github.com/melalj/celery-worker-demo/

The entry point is `./app/entrypoint.sh` and main code logic in `./app/worker.py`

## There are 3 sub-questions regarding this implementation:

### How to size/tweak the variables?
  - Worker concurrency
  - SQLAlchemy pool_size (normally pgbouncer would take over)
  - worker_prefetch_multiplier
  - broker_pool_limit
  - Number of replica of the python worker (how it will affect the database load)

### How to optimize the code?
It seems that there's room to improve the code, how can I trace bottlenecks (I suspect it's the db or beautifulsoup, it seems like a dark mystery while using gevent) - and how to optimize it?

### The database closes unexpectly something, why?
When I run the code and trigger with +10K pulls. It hangs the whole process and occasionally throws:
`(psycopg2.OperationalError) server closed the connection unexpectedly`
Any recommendations on how to size resources of the db to support such tasks?


## Development enviroment

Import database schema: `docker-compose exec -T postgres psql -U postgres celery-worker-demo < ./celery-worker-demo.sql`
Start the worker locally: `docker-compose up worker`
Scale the worker to 10: `docker-compose scale worker=10`
Trigger pulling: `docker-compose run --rm worker python -c "from worker import pull_domains; pull_domains.s().apply_async();"`

For linting, use `virtualenv -p python3 env; source env/bin/activate; pip install -r requirements.txt`

## Production enviroment

`worker` deployment specification on kubernetes is available on `./worker-k8s.yml`