import unittest
from pathlib import Path

from pic_record_manager.media_types import MEDIA_FILE_FILTER, is_image_file, is_video_file


class MediaTypesTest(unittest.TestCase):
    def test_identifies_supported_image_and_video_files(self):
        self.assertTrue(is_image_file(Path("cover.JPG")))
        self.assertTrue(is_video_file(Path("clip.MP4")))
        self.assertFalse(is_video_file(Path("cover.jpg")))
        self.assertFalse(is_image_file(Path("clip.mp4")))
        self.assertIn("*.mp4", MEDIA_FILE_FILTER)


if __name__ == "__main__":
    unittest.main()
