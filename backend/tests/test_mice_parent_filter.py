import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.database import Base
from backend.app.models.models import Mouse, User
from backend.app.routers.mice import get_all_parents, list_mice


class MouseParentFilterTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.user = User(username="parent-filter", display_name="Parent Filter")
        self.db.add_all([
            Mouse(mouse_code="CHILD-1", parents="SIRE-1M+DAM-1F", status="在笼"),
            Mouse(mouse_code="CHILD-2", parents="SIRE-1M、DAM-2F", status="在笼"),
            Mouse(mouse_code="CHILD-3", parents="SIRE-10M+DAM-3F", status="在笼"),
        ])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def list_with_parents(self, parents):
        return list_mice(
            page=1,
            page_size=50,
            keyword=None,
            mouse_code=None,
            room=None,
            cage_code=None,
            strain=None,
            parents=parents,
            gender=None,
            owner_name=None,
            status=None,
            has_owner=None,
            in_cage=None,
            db=self.db,
            current_user=self.user,
        )

    def test_parent_options_are_split_and_deduplicated(self):
        self.assertEqual(
            get_all_parents(self.db, self.user),
            ["DAM-1F", "DAM-2F", "DAM-3F", "SIRE-1M", "SIRE-10M"],
        )

    def test_multiple_parents_match_any_exact_parent_token(self):
        result = self.list_with_parents("SIRE-1M,DAM-3F")
        self.assertEqual(result["total"], 3)
        self.assertEqual({mouse["mouse_code"] for mouse in result["items"]}, {"CHILD-1", "CHILD-2", "CHILD-3"})

        exact = self.list_with_parents("SIRE-1M")
        self.assertEqual(exact["total"], 2)
        self.assertNotIn("CHILD-3", {mouse["mouse_code"] for mouse in exact["items"]})


if __name__ == "__main__":
    unittest.main()
