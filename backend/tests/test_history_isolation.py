from __future__ import annotations

import unittest

from app.services import database


class FakeAcquire:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakePool:
    def __init__(self, conn):
        self.conn = conn

    def acquire(self):
        return FakeAcquire(self.conn)


class FakeConn:
    def __init__(self):
        self.calls = []

    async def fetch(self, sql, *args):
        self.calls.append(("fetch", sql, args))
        return []

    async def fetchrow(self, sql, *args):
        self.calls.append(("fetchrow", sql, args))
        return None

    async def execute(self, sql, *args):
        self.calls.append(("execute", sql, args))
        return "DELETE 1"


class HistoryIsolationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.previous_pool = database._pool
        self.conn = FakeConn()
        database._pool = FakePool(self.conn)

    async def asyncTearDown(self):
        database._pool = self.previous_pool

    async def test_list_history_filters_by_user_id(self):
        await database.list_history("user-a", 20, 5)

        method, sql, args = self.conn.calls[-1]
        self.assertEqual(method, "fetch")
        self.assertIn("WHERE user_id = $1", sql)
        self.assertEqual(args, ("user-a", 20, 5))

    async def test_get_history_filters_by_user_id_and_record_id(self):
        await database.get_history("user-a", "record-1")

        method, sql, args = self.conn.calls[-1]
        self.assertEqual(method, "fetchrow")
        self.assertIn("WHERE user_id = $1 AND id = $2", sql)
        self.assertEqual(args, ("user-a", "record-1"))

    async def test_save_history_writes_owner_fields(self):
        await database.save_history(
            "user-a",
            {"user_id": "user-a", "account": "a@example.test"},
            {
                "id": "record-1",
                "product_name": "Product A",
                "category": "Category A",
                "style_id": "style-a",
                "style_name": "Style A",
                "platform_id": "tmall",
                "thumbnail": "https://example.test/a.png",
                "image_count": 2,
                "state": {"selectedStyleId": "style-a"},
            },
        )

        method, sql, args = self.conn.calls[-1]
        self.assertEqual(method, "execute")
        self.assertIn("user_id", sql)
        self.assertIn("user_snapshot_json", sql)
        self.assertIn("WHERE project_history.user_id = EXCLUDED.user_id", sql)
        self.assertEqual(args[1], "user-a")
        self.assertIn('"user_id": "user-a"', args[2])

    async def test_delete_history_filters_by_user_id_and_record_id(self):
        deleted = await database.delete_history("user-a", "record-1")

        method, sql, args = self.conn.calls[-1]
        self.assertTrue(deleted)
        self.assertEqual(method, "execute")
        self.assertIn("DELETE FROM project_history WHERE user_id = $1 AND id = $2", sql)
        self.assertEqual(args, ("user-a", "record-1"))

    async def test_list_saved_styles_filters_by_user_id(self):
        await database.list_saved_styles("user-a", 20, 5)

        method, sql, args = self.conn.calls[-1]
        self.assertEqual(method, "fetch")
        self.assertIn("FROM saved_styles", sql)
        self.assertIn("WHERE user_id = $1", sql)
        self.assertEqual(args, ("user-a", 20, 5))

    async def test_save_style_writes_owner_fields(self):
        await database.save_style(
            "user-a",
            {"user_id": "user-a", "account": "a@example.test"},
            {
                "id": "style-1",
                "name": "冷萃晶透风",
                "style": {
                    "id": "style_reference",
                    "name": "冷萃晶透风",
                    "keywords": ["冷感"],
                    "primary_color": "#A8DDE8",
                },
            },
        )

        method, sql, args = self.conn.calls[-1]
        self.assertEqual(method, "execute")
        self.assertIn("INSERT INTO saved_styles", sql)
        self.assertIn("user_id", sql)
        self.assertIn("user_snapshot_json", sql)
        self.assertIn("WHERE saved_styles.user_id = EXCLUDED.user_id", sql)
        self.assertEqual(args[1], "user-a")
        self.assertIn('"user_id": "user-a"', args[2])
        self.assertEqual(args[3], "冷萃晶透风")
        self.assertIn('"primary_color": "#A8DDE8"', args[4])

    async def test_delete_saved_style_filters_by_user_id_and_record_id(self):
        deleted = await database.delete_saved_style("user-a", "style-1")

        method, sql, args = self.conn.calls[-1]
        self.assertTrue(deleted)
        self.assertEqual(method, "execute")
        self.assertIn("DELETE FROM saved_styles WHERE user_id = $1 AND id = $2", sql)
        self.assertEqual(args, ("user-a", "style-1"))


if __name__ == "__main__":
    unittest.main()
