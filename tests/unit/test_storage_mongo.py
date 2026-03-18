import asyncio
from datetime import UTC, datetime

from storage.mongo import list_configs, list_configs_range, save_config
from storage.schema import MapConfigDocument, MapConfigMetadata


class FakeCursor:
    def __init__(self, docs):
        self.docs = docs
        self.sort_args = None
        self.skip_value = None
        self.limit_value = None
        self.length = None

    def sort(self, key, direction):
        self.sort_args = (key, direction)
        return self

    def skip(self, value):
        self.skip_value = value
        return self

    def limit(self, value):
        self.limit_value = value
        return self

    async def to_list(self, length):
        self.length = length
        return self.docs[:length]


class FakeCollection:
    def __init__(self):
        self.create_index_calls = []
        self.update_one_calls = []
        self.find_calls = []

    async def create_index(self, spec, unique=False):
        self.create_index_calls.append((spec, unique))

    async def update_one(self, query, update, upsert=False):
        self.update_one_calls.append((query, update, upsert))

    def find(self, query, projection):
        cursor = FakeCursor([{"year": 800}, {"year": 900}, {"year": 1000}])
        self.find_calls.append((query, projection, cursor))
        return cursor


def test_save_config_uses_year_region_upsert_and_indexes(monkeypatch):
    fake_collection = FakeCollection()
    monkeypatch.setattr("storage.mongo.get_collection", lambda: fake_collection)
    monkeypatch.setattr("storage.mongo._indexes_initialized", False)

    doc = MapConfigDocument(
        id="800_europe",
        year=800,
        region="europe",
        config={"year": 800},
        metadata=MapConfigMetadata(
            generator_model="generator",
            reviewer_model="reviewer",
            confidence_scores={"frankish_empire": 0.9},
            polygon_count=1,
            polity_count=1,
            retry_count=0,
            review_decision="approved",
        ),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    asyncio.run(save_config(doc))

    assert fake_collection.create_index_calls == [
        ([("year", 1), ("region", 1)], True),
        ([("region", 1), ("year", 1)], False),
    ]
    query, update, upsert = fake_collection.update_one_calls[0]
    assert query == {"year": 800, "region": "europe"}
    assert upsert is True
    assert update["$set"]["id"] == "800_europe"
    assert "$setOnInsert" in update


def test_list_configs_sorts_and_paginates(monkeypatch):
    fake_collection = FakeCollection()
    monkeypatch.setattr("storage.mongo.get_collection", lambda: fake_collection)
    monkeypatch.setattr("storage.mongo._indexes_initialized", True)

    results = asyncio.run(list_configs("europe", page=2, limit=2))

    query, _projection, cursor = fake_collection.find_calls[0]
    assert query == {"region": "europe"}
    assert cursor.sort_args == ("year", 1)
    assert cursor.skip_value == 2
    assert cursor.limit_value == 2
    assert cursor.length == 2
    assert results == [{"year": 800}, {"year": 900}]


def test_list_configs_range_sorts_and_limits(monkeypatch):
    fake_collection = FakeCollection()
    monkeypatch.setattr("storage.mongo.get_collection", lambda: fake_collection)
    monkeypatch.setattr("storage.mongo._indexes_initialized", True)

    results = asyncio.run(list_configs_range(800, 1200, "europe", limit=2))

    query, _projection, cursor = fake_collection.find_calls[0]
    assert query == {"year": {"$gte": 800, "$lte": 1200}, "region": "europe"}
    assert cursor.sort_args == ("year", 1)
    assert cursor.limit_value == 2
    assert cursor.length == 2
    assert results == [{"year": 800}, {"year": 900}]
