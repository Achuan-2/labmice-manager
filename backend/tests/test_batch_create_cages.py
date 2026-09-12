import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.database import Base
from backend.app.models.models import Cage, User
from backend.app.routers.cages import batch_create_cages
from backend.app.schemas.schemas import CageBatchCreate


class BatchCreateCagesTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.admin = User(username="test-admin", display_name="Test Admin")

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_creates_multiple_cages_with_shared_fields_and_deduplicates_codes(self):
        result = batch_create_cages(
            CageBatchCreate(
                cage_codes=[" 8A ", "10A", "20A", "8A"],
                room="测试鼠房",
                strain="5xFAD",
                gender="F",
                capacity=6,
            ),
            self.db,
            self.admin,
        )

        self.assertEqual(result["created_count"], 3)
        self.assertEqual(result["cage_codes"], ["8A", "10A", "20A"])
        cages = self.db.query(Cage).order_by(Cage.id).all()
        self.assertEqual([cage.cage_code for cage in cages], ["8A", "10A", "20A"])
        self.assertTrue(all(cage.room == "测试鼠房" for cage in cages))
        self.assertTrue(all(cage.strain == "5xFAD" and cage.gender == "F" and cage.capacity == 6 for cage in cages))

    def test_existing_code_rejects_entire_batch(self):
        self.db.add(Cage(cage_code="10A", room="测试鼠房"))
        self.db.commit()

        with self.assertRaises(HTTPException) as context:
            batch_create_cages(
                CageBatchCreate(cage_codes=["8A", "10A", "20A"], room="测试鼠房"),
                self.db,
                self.admin,
            )

        self.assertEqual(context.exception.status_code, 400)
        self.assertIn("10A", context.exception.detail)
        self.assertEqual(
            [cage.cage_code for cage in self.db.query(Cage).all()],
            ["10A"],
        )


if __name__ == "__main__":
    unittest.main()
