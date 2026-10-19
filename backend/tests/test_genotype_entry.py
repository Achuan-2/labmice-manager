import datetime
import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.database import Base
from backend.app.models.models import Cage, GenotypeRecord, Mouse, TransferLog, User
from backend.app.routers.genotypes import (
    create_genotype_records,
    delete_genotype_record,
    update_genotype_record,
)
from backend.app.routers.mice import create_mouse, get_mouse_by_code
from backend.app.schemas.schemas import GenotypeRecordCreate, GenotypeRecordUpdate, MouseCreate


class GenotypeEntryTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.admin = User(username='test', display_name='Test')
        self.db.add_all([
            Mouse(mouse_code='A1', strain='Strain A', parents='P1M+P2F', gender='M'),
            Mouse(mouse_code='A10', strain='Strain B', parents='P3M+P4F', gender='F'),
        ])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def save(self, *items):
        return create_genotype_records(
            [GenotypeRecordCreate(**item) for item in items], self.db, self.admin
        )

    def test_batch_inherits_each_mouse_and_allows_empty_genotype(self):
        records = self.save({'mouse_code': ' A1 '}, {'mouse_code': 'A10'}, {'mouse_code': 'A'})
        self.assertEqual([r.mouse_code for r in records], ['A1', 'A10', 'A'])
        self.assertEqual([r.strain for r in records], ['Strain A', 'Strain B', ''])
        self.assertEqual([r.parents for r in records], ['P1M+P2F', 'P3M+P4F', None])
        self.assertEqual([r.gender for r in records], ['M', 'F', '未知'])
        self.assertTrue(all(r.genotype_1 is None for r in records))
        self.assertIsNotNone(records[-1].mouse_id)
        self.assertEqual([r.mouse_created for r in records], [False, False, True])
        self.assertEqual(self.db.query(TransferLog).one().mouse_codes, 'A')

    def test_custom_values_override_archive(self):
        record, = self.save({'mouse_code': 'A1', 'strain': 'Custom', 'parents': 'New parents'})
        self.assertEqual((record.strain, record.parents), ('Custom', 'New parents'))

    def test_edit_and_delete_keep_mouse_genotype_summary_linked(self):
        older, = self.save({
            'mouse_code': 'A1', 'test_date': '2026-09-01', 'genotype_1': 'WT'
        })
        latest, = self.save({
            'mouse_code': 'A1', 'test_date': '2026-09-02', 'genotype_1': 'HET',
            'dob': '2026-07-01', 'op_record': 'Operator A', 'notes': 'first note', 'confirm_existing': True,
        })
        mouse = self.db.query(Mouse).filter_by(mouse_code='A1').one()
        self.assertEqual(
            (mouse.genotype_1, mouse.test_date, mouse.dob),
            ('HET', '2026-09-02', '2026-07-01'),
        )

        update_genotype_record(latest.id, GenotypeRecordUpdate(
            test_date='2026-08-31', dob='2026-07-02',
            op_record='Operator B', notes='updated note'
        ), self.db, self.admin)
        self.db.refresh(mouse)
        self.assertEqual(
            (mouse.genotype_1, mouse.test_date, mouse.dob),
            ('WT', '2026-09-01', '2026-07-02'),
        )
        updated = self.db.get(GenotypeRecord, latest.id)
        self.assertEqual((updated.op_record, updated.notes), ('Operator B', 'updated note'))

        delete_genotype_record(older.id, self.db, self.admin)
        self.db.refresh(mouse)
        self.assertEqual((mouse.genotype_1, mouse.test_date), ('HET', '2026-08-31'))

    def test_invalid_batch_rolls_back_records_and_mouse_sync(self):
        with self.assertRaises(HTTPException):
            self.save({'mouse_code': 'A1', 'genotype_1': 'HET'}, {'mouse_code': 'A2,A3'})
        self.assertEqual(self.db.query(GenotypeRecord).count(), 0)
        self.assertIsNone(self.db.query(Mouse).filter_by(mouse_code='A1').one().genotype_1)

    def test_duplicate_codes_rejected(self):
        with self.assertRaises(HTTPException):
            self.save({'mouse_code': 'A1'}, {'mouse_code': ' A1 '})
        self.assertEqual(self.db.query(GenotypeRecord).count(), 0)

    def test_genotype_only_mouse_can_create_archive_and_enter_existing_cage(self):
        # Legacy records created before genotype entry also created mouse archives.
        self.db.add_all([
            GenotypeRecord(mouse_code='New1', genotype_1='HET'),
            GenotypeRecord(mouse_code='New10'),
            GenotypeRecord(mouse_code='New1', genotype_2='WT'),
        ])
        self.db.commit()
        virtual = get_mouse_by_code('New1', self.db, self.admin)
        self.assertIsNone(virtual['id'])
        cage = Cage(room='Room A', cage_code='C1')
        self.db.add(cage)
        self.db.commit()
        result = create_mouse(MouseCreate(
            mouse_code='New1', source_room='Room A', cage_code='C1', status='在笼'
        ), self.db, self.admin)
        self.assertEqual(result['cage_id'], cage.id)
        self.assertEqual(result['status'], '在笼')
        self.assertEqual(len(result['genotypes']), 2)
        self.assertTrue(all(record.mouse_id == result['id'] for record in
                            self.db.query(GenotypeRecord).filter_by(mouse_code='New1').all()))
        self.assertIsNone(self.db.query(GenotypeRecord).filter_by(mouse_code='New10').one().mouse_id)
        self.assertEqual(self.db.query(Cage).count(), 1)

    def test_new_genotype_creates_archive_and_visible_creation_log(self):
        record, = self.save({
            'mouse_code': 'New1', 'strain': '5fad', 'gender': 'F', 'genotype_3': '阳性',
            'dob': '2026-07-01', 'notes': 'new animal',
        })
        mouse = self.db.get(Mouse, record.mouse_id)
        self.assertEqual((mouse.mouse_code, mouse.strain, record.strain), ('New1', '5xFAD', '5xFAD'))
        self.assertEqual((mouse.gender, mouse.dob, mouse.status, mouse.cage_id), ('F', '2026-07-01', '出笼', None))
        self.assertEqual((mouse.test_date, record.test_date), (datetime.date.today().isoformat(),) * 2)
        self.assertTrue(record.mouse_created)
        self.assertIsNone(record.renamed_from)
        log = self.db.query(TransferLog).one()
        self.assertEqual((log.action_type, log.mouse_codes, log.mouse_count, log.operator), ('新增小鼠', 'New1', 1, 'Test'))
        self.assertEqual(get_mouse_by_code('New1', self.db, self.admin)['transfer_logs'][0]['id'], log.id)

    def test_existing_mouse_is_reused_and_retest_requires_confirmation(self):
        first, = self.save({'mouse_code': 'A1', 'genotype_1': 'WT'})
        with self.assertRaises(HTTPException) as error:
            self.save({'mouse_code': 'A1', 'genotype_1': 'HET'})
        self.assertEqual(error.exception.status_code, 409)
        repeated, = self.save({'mouse_code': 'A1', 'genotype_1': 'HET', 'confirm_existing': True})
        self.assertEqual(first.mouse_id, repeated.mouse_id)
        self.assertFalse(repeated.mouse_created)
        self.assertEqual(self.db.query(Mouse).count(), 2)
        self.assertEqual(self.db.query(TransferLog).count(), 0)

    def test_new_mouse_mode_resolves_conflicts_and_keeps_original_results(self):
        original, = self.save({'mouse_code': 'A1', 'genotype_1': 'WT'})
        self.db.add(Mouse(mouse_code='A1_2'))
        self.db.add(GenotypeRecord(mouse_code='A1_3', genotype_1='Legacy result'))
        self.db.commit()
        new, = self.save({'mouse_code': 'A1', 'genotype_1': 'HET', 'create_new_mouse': True})
        self.assertEqual((new.mouse_code, new.renamed_from, new.mouse_created), ('A1_4', 'A1', True))
        self.assertNotEqual(new.mouse_id, original.mouse_id)
        self.assertEqual(self.db.get(Mouse, original.mouse_id).genotype_1, 'WT')
        self.assertEqual(self.db.get(Mouse, new.mouse_id).genotype_1, 'HET')
        self.assertIsNone(self.db.query(GenotypeRecord).filter_by(mouse_code='A1_3').one().mouse_id)
        self.assertEqual(self.db.query(TransferLog).one().mouse_codes, 'A1_4')

    def test_confirmed_legacy_entry_links_all_history_to_new_archive(self):
        self.db.add(GenotypeRecord(mouse_code='Legacy1', genotype_1='WT', strain='5fad'))
        self.db.commit()
        new, = self.save({'mouse_code': 'Legacy1', 'confirm_existing': True})
        self.assertTrue(new.mouse_created)
        self.assertIsNone(new.renamed_from)
        self.assertEqual(self.db.get(Mouse, new.mouse_id).genotype_1, 'WT')
        self.assertEqual({record.mouse_id for record in self.db.query(GenotypeRecord).all()}, {new.mouse_id})
        self.assertEqual(self.db.query(TransferLog).one().mouse_codes, 'Legacy1')

    def test_invalid_batch_rolls_back_new_archives_logs_and_links(self):
        self.db.add(GenotypeRecord(mouse_code='Legacy1', genotype_1='WT'))
        self.db.commit()
        with self.assertRaises(HTTPException):
            self.save({'mouse_code': 'Legacy1', 'confirm_existing': True}, {'mouse_code': 'New2,New3'})
        self.assertEqual(self.db.query(Mouse).count(), 2)
        self.assertEqual(self.db.query(TransferLog).count(), 0)
        self.assertIsNone(self.db.query(GenotypeRecord).one().mouse_id)

    def test_new_archive_creates_cage_or_stays_uncaged(self):
        result = create_mouse(MouseCreate(
            mouse_code='New2', source_room='Room B', cage_code=' C2 '
        ), self.db, self.admin)
        self.assertEqual((result['cage_room'], result['cage_code'], result['status']),
                         ('Room B', 'C2', '在笼'))
        uncaged = create_mouse(MouseCreate(mouse_code='New3'), self.db, self.admin)
        self.assertIsNone(uncaged['cage_id'])
        self.assertEqual(uncaged['status'], '出笼')


if __name__ == '__main__':
    unittest.main()
