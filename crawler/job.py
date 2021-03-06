# -*- Encoding: utf-8 -*-
import re
import os
import json

from os.path import join


class JobPool:
    def __init__(self, db, cache_root, job_name,
                 pagination=True, subfix='.html', timeout=10):
        self.cache_dir = join(cache_root, job_name)
        self.job_file = join(cache_root, 'job_{}.json'.format(job_name))

        self.subfix = subfix
        self.timeout = timeout
        self.key = lambda fn: fn[:fn.find('_')] if pagination \
            else lambda fn: fn[:-5]

        self.data = self._load()

        self.db = db
        self.total_tbl = '{}:total'.format(job_name)
        self.todo_tbl = '{}:todo'.format(job_name)

        done = self._done()
        if done:
            self.db.sadd(self.total_tbl, *done)

    def scan(self, path, ptn, find_job, save_period=2000):
        total = set(os.listdir(path))
        todo = total - set(self.data.keys())
        print '{}/{} to parse.'.format(len(todo), len(total))

        for i, filename in enumerate(todo):
            with open(join(path, filename)) as f:
                c = ''.join(f.readlines())
            self.data[filename] = ptn.findall(c)

            if i % save_period == 0:
                print 'saving. {} done.'.format(i+1)
                self._save(find_job)
        else:
            print 'saving. {} done.'.format(len(todo))
            self._save(find_job)

    def count(self):
        return self.db.llen(self.todo_tbl)

    def next(self):
        key = self.db.blpop(self.todo_tbl, self.timeout)
        return key and key[1]

    def add(self, *keys):
        existed = self.db.smembers(self.total_tbl)
        _todo = set(keys) - set(existed)
        if _todo:
            self.db.sadd(self.total_tbl, *_todo)
            self.db.rpush(self.todo_tbl, *_todo)
        return len(_todo)

    def add_force(self, *keys):
        self.db.rpush(self.todo_tbl, *key)
        return self.db.sadd(self.total_tbl, *key)

    def _load(self):
        data = dict()
        if os.path.exists(self.job_file):
            with open(self.job_file, 'r') as fr:
                data = json.load(fr)
        return data

    def _save(self, find_job):
        self.add(*find_job(self.data))
        with open(self.job_file, 'wb') as fw:
            json.dump(self.data, fw, indent=4)

    def _done(self):
        return {self.key(fn)
                for fn in os.listdir(self.cache_dir)
                if fn.endswith(self.subfix)}


if __name__ == '__main__':

    import redis
    r = redis.StrictRedis(db=1)
    r.flushdb()
    cache_root = '../dianping/cache'
    job_name = 'shop_review'
    job = JobPool(r, cache_root, job_name, pagination=True)

    shop_prof_dir = '../dianping/cache/shop_prof'
    ptn = re.compile(r'<li[^>]+id="rev_(\d+)"')

    find_job = lambda data: {key[:-5] for key, vs in data.items() if len(vs) > 9}

    job.scan(shop_prof_dir, ptn, find_job)

    print 'TODO: {}'.format(job.count())
