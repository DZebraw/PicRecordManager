import tempfile
import unittest
from pathlib import Path

from endfielddoc.archive_store import ArchiveStore


class ArchiveStoreTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.store = ArchiveStore(self.root / "archive.db", self.root / "media")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_bootstrap_creates_default_albums(self):
        albums = self.store.list_albums()

        self.assertEqual(["书签 1", "书签 2", "书签 3", "书签 4"], [a.name for a in albums])

    def test_rename_album_updates_existing_bookmark_name(self):
        album = self.store.list_albums()[0]

        updated = self.store.rename_album(album.id, "  旅行照片  ")

        self.assertEqual(album.id, updated.id)
        self.assertEqual("旅行照片", updated.name)
        self.assertEqual("旅行照片", self.store.list_albums()[0].name)

    def test_import_photo_copies_file_and_lists_it_in_album(self):
        source = self.root / "source.png"
        source.write_bytes(b"fake image bytes")
        album_id = self.store.list_albums()[0].id

        photo = self.store.import_photo(album_id, source, title="入职档案")

        self.assertTrue(photo.stored_path.exists())
        self.assertNotEqual(source, photo.stored_path)
        photos = self.store.list_photos(album_id=album_id)
        self.assertEqual(1, len(photos))
        self.assertEqual("入职档案", photos[0].title)
        self.assertEqual(photos[0].created_at, photos[0].display_date)
        self.assertEqual([photo.stored_path], [image.stored_path for image in self.store.list_photo_images(photo.id)])

    def test_create_empty_photo_and_add_multiple_images(self):
        album_id = self.store.list_albums()[0].id
        first = self.root / "first.jpg"
        second = self.root / "second.jpg"
        first.write_bytes(b"first")
        second.write_bytes(b"second")

        photo = self.store.create_empty_photo(album_id, title="空档案")

        self.assertEqual("空档案", photo.title)
        self.assertEqual([], self.store.list_photo_images(photo.id))
        self.assertFalse(photo.stored_path.exists())

        images = self.store.add_photo_images(photo.id, [first, second])
        updated = self.store.get_photo(photo.id)

        self.assertEqual(2, len(images))
        self.assertTrue(all(image.stored_path.exists() for image in images))
        self.assertEqual([first.name, second.name], [image.original_name for image in self.store.list_photo_images(photo.id)])
        self.assertEqual(images[0].stored_path, updated.stored_path)

    def test_photo_images_have_independent_records(self):
        album_id = self.store.list_albums()[0].id
        first = self.root / "first.jpg"
        second = self.root / "second.jpg"
        first.write_bytes(b"first")
        second.write_bytes(b"second")
        photo = self.store.create_empty_photo(album_id, title="multi image archive")
        images = self.store.add_photo_images(photo.id, [first, second])

        self.store.update_photo_image_record(images[0].id, "first page record")
        self.store.update_photo_image_record(images[1].id, "second page record")

        updated_images = self.store.list_photo_images(photo.id)
        self.assertEqual(["first page record", "second page record"], [image.record for image in updated_images])
        self.assertEqual(["multi image archive"], [item.title for item in self.store.search_photos("second page")])

    def test_update_photo_saves_editable_display_date(self):
        source = self.root / "date-source.png"
        source.write_bytes(b"fake image bytes")
        album_id = self.store.list_albums()[0].id
        photo = self.store.import_photo(album_id, source, title="日期档案")

        updated = self.store.update_photo(
            photo.id,
            title="日期档案",
            description="备注",
            album_id=album_id,
            display_date="2026-06-17",
        )

        self.assertEqual("2026-06-17", updated.display_date)
        self.assertEqual("2026-06-17", self.store.get_photo(photo.id).display_date)

    def test_delete_album_removes_album_photos_and_media_files(self):
        source = self.root / "album-source.png"
        source.write_bytes(b"album image bytes")
        album = self.store.create_album("可删除书签")
        photo = self.store.import_photo(album.id, source, title="待删除照片")

        self.store.delete_album(album.id)

        self.assertNotIn(album.id, [item.id for item in self.store.list_albums()])
        self.assertEqual([], self.store.list_photos(album_id=album.id))
        self.assertFalse(photo.stored_path.exists())

    def test_search_matches_title_description_and_album(self):
        albums = self.store.list_albums()
        alpha = self.root / "alpha.png"
        beta = self.root / "beta.png"
        alpha.write_bytes(b"alpha")
        beta.write_bytes(b"beta")
        self.store.import_photo(albums[0].id, alpha, title="合同扫描", description="张三资料")
        self.store.import_photo(albums[1].id, beta, title="巡检照片", description="设备验收")

        title_matches = self.store.search_photos("合同")
        album_matches = self.store.search_photos("书签 2")
        description_matches = self.store.search_photos("验收")

        self.assertEqual(["合同扫描"], [p.title for p in title_matches])
        self.assertEqual(["巡检照片"], [p.title for p in album_matches])
        self.assertEqual(["巡检照片"], [p.title for p in description_matches])

    def test_pagination_reports_total_and_slice(self):
        album_id = self.store.list_albums()[0].id
        for index in range(6):
            source = self.root / f"photo-{index}.png"
            source.write_bytes(str(index).encode("ascii"))
            self.store.import_photo(album_id, source, title=f"照片 {index}")

        page = self.store.paginate_photos(album_id=album_id, page=2, per_page=4)

        self.assertEqual(6, page.total)
        self.assertEqual(2, page.page)
        self.assertEqual(2, page.total_pages)
        self.assertEqual(["照片 4", "照片 5"], [p.title for p in page.items])


if __name__ == "__main__":
    unittest.main()
