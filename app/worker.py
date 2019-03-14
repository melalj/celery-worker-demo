# Gevent Patches
import gevent
import gevent.monkey
gevent.monkey.patch_all() # noqa

import psycogreen.gevent
psycogreen.gevent.patch_psycopg() # noqa

# Imports
import requests
import sqlalchemy as sa
from bs4 import BeautifulSoup
from sqlalchemy.dialects.postgresql import insert
from celery import Celery, Task
from datetime import datetime
from sqlalchemy.orm import sessionmaker, scoped_session
from requests.exceptions import RequestException

# Init SQLAlchemy
db_engine = sa.create_engine(
    'postgres://postgres@pgbouncer:6432/celery-worker-demo',
    pool_recycle=3600, pool_size=10
)
db_metadata = sa.MetaData()

table_domains = sa.Table('domains', db_metadata,
                         autoload=True, autoload_with=db_engine)
table_result = sa.Table('result', db_metadata,
                        autoload=True, autoload_with=db_engine)


def db_new_session():
    return scoped_session(sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=db_engine
    ))

# Init Celery
#  ./app/entrypoint.sh to see the starting command


app = Celery(broker=f'redis://redis:6379/0', backend=None)
app.conf.update(
    worker_prefetch_multiplier=1,
    task_ignore_result=True,
    task_store_errors_even_if_ignored=True,
    broker_pool_limit=10,
    broker_transport_options={
        'visibility_timeout': 3600,
        'fanout_prefix': True,
        'fanout_patterns': True
    }
)


class BaseTask(Task):
    abstract = True

    def after_return(self, status, retval, task_id, args, kwargs, einfo):
        if hasattr(self, 'db_session'):
            self.db_session.remove()


# Tasks


@app.task(base=BaseTask, bind=True, name='pull_domains')
def pull_domains(self):
    # Start a db session
    self.db_session = db_new_session()
    # Pull top 10K Alexa
    with open('top10k.csv', 'r') as f:
        for line in f:
            row = line.split(',')
            insert_data = {
                'domain': row[1].replace('\n', ''),
                'alexa_rank': row[0]
            }
            self.db_session.execute(
                insert(table_domains).values(
                    insert_data
                ).on_conflict_do_update(
                    index_elements=['domain'],
                    set_={
                        **insert_data,
                        **{'updated_at': datetime.utcnow()}
                    }
                )
            )
            self.db_session.commit()

            # Trigger get_search_result
            # definitely this need to be improved, ideas?
            get_search_result.s(insert_data['domain']).apply_async()


@app.task(base=BaseTask, bind=True, name='get_search_result',
          auto_retry=[RequestException], max_retries=3)
def get_search_result(self, domain):
    print(f'Pulling result for {domain}...')
    # Start a db session
    self.db_session = db_new_session()
    # Pull from Bing
    res = requests.get(f'https://www.bing.com/search?q={domain}&setlang=en-us',
                       verify=False)
    soup = BeautifulSoup(res.text, 'html.parser')
    result = soup.select('.b_algo')

    if len(result) > 0:
        try:
            for i, row in enumerate(result):
                id = f'{domain}-{i}'
                insert_data = {
                    'id': id,
                    'domain': domain,
                    'position': i,
                    'title': row.find('a').text,
                    'url': row.find('a')['href'],
                }
                self.db_session.execute(
                    insert(table_result).values(
                        insert_data
                    ).on_conflict_do_update(
                        index_elements=['id'],
                        set_={
                            **insert_data,
                            **{'updated_at': datetime.utcnow()}
                        }
                    )
                )
                self.db_session.commit()

                # Another task can be triggered here
                #   for example to work on url
            return True
        except Exception as e:
            print(e)
            return False
