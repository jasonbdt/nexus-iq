"""In-memory transactional ports for dependency-free application tests."""
from copy import deepcopy


class MemoryRepository:
    """Store independent application entities without SQL or framework types."""

    def __init__(self, entities, key='id'):
        self.entities = entities
        self.key = key

    def get(self, identity):
        return self.entities.get(identity)

    def by_email(self, email):
        return next((item for item in self.entities.values() if item.emailAddress == email), None)

    def by_name(self, name, tag):
        return next((item for item in self.entities.values()
                     if (item.summoner_name, item.tag_line) == (name, tag)), None)

    def save(self, entity):
        if entity.id is None:
            entity.id = len(self.entities) + 1
        for index, message in enumerate(getattr(entity, 'messages', []), 1):
            message.id = message.id or index
        self.entities[getattr(entity, self.key)] = entity
        return entity

    def delete(self, entity):
        del self.entities[getattr(entity, self.key)]


class MemoryStore:
    """Factory creating transaction snapshots with explicit commit visibility."""

    def __init__(self):
        self.data = {'users': {}, 'summoners': {}, 'matches': {}, 'coaching': {}}
        self.active = 0
        self.commits = 0

    def __call__(self):
        return MemoryUnitOfWork(self)


class MemoryUnitOfWork:
    """Discard uncommitted snapshots on context exit."""

    def __init__(self, store):
        self.store = store

    def __enter__(self):
        self.store.active += 1
        self.data = deepcopy(self.store.data)
        for name, key in [('users', 'id'), ('summoners', 'puuid'), ('matches', 'match_id'),
                          ('coaching', 'id')]:
            setattr(self, name, MemoryRepository(self.data[name], key))
        return self

    def __exit__(self, *_args):
        self.store.active -= 1

    def commit(self):
        self.store.data = deepcopy(self.data)
        self.store.commits += 1

    def rollback(self):
        self.data = deepcopy(self.store.data)
