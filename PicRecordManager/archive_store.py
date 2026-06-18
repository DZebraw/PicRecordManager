from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from contextlib import contextmanager
from math import ceil
from pathlib import Path
import shutil
import sqlite3
import uuid


@dataclass(frozen=True)
class Album:
    id: int
    name: str
    sort_order: int


@dataclass(frozen=True)
class Photo:
    id: int
    album_id: int
    album_name: str
    title: str
    description: str
    original_name: str
    stored_path: Path
    created_at: str
    display_date: str
    image_count: int = 0


@dataclass(frozen=True)
class PhotoImage:
    id: int
    photo_id: int
    original_name: str
    stored_path: Path
    sort_order: int
    record: str = ""


@dataclass(frozen=True)
class PhotoPage:
    items: list[Photo]
    page: int
    per_page: int
    total: int
    total_pages: int


class ArchiveStore:
    def __init__(self, database_path: Path | str, media_dir: Path | str):
        self.database_path = Path(database_path)
        self.media_dir = Path(media_dir)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.media_dir.mkdir(parents=True, exist_ok=True)
        self._migrate()
        self._ensure_default_albums()

    def list_albums(self) -> list[Album]:
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT id, name, sort_order FROM albums ORDER BY sort_order, id"
            ).fetchall()
        return [Album(row["id"], row["name"], row["sort_order"]) for row in rows]

    def create_album(self, name: str) -> Album:
        clean_name = name.strip() or "新书签"
        with self._connection() as conn:
            sort_order = conn.execute("SELECT COALESCE(MAX(sort_order), 0) + 1 FROM albums").fetchone()[0]
            cursor = conn.execute(
                "INSERT INTO albums (name, sort_order) VALUES (?, ?)",
                (clean_name, sort_order),
            )
            album_id = int(cursor.lastrowid)
        return Album(album_id, clean_name, sort_order)

    def rename_album(self, album_id: int, name: str) -> Album:
        clean_name = name.strip() or "未命名书签"
        with self._connection() as conn:
            conn.execute("UPDATE albums SET name = ? WHERE id = ?", (clean_name, album_id))
            row = conn.execute(
                "SELECT id, name, sort_order FROM albums WHERE id = ?",
                (album_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Album not found: {album_id}")
        return Album(row["id"], row["name"], row["sort_order"])

    def import_photo(
        self,
        album_id: int,
        source_path: Path | str,
        *,
        title: str | None = None,
        description: str = "",
    ) -> Photo:
        source = Path(source_path)
        if not source.exists() or not source.is_file():
            raise FileNotFoundError(source)

        extension = source.suffix.lower()
        stored_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:10]}{extension}"
        stored_path = self.media_dir / stored_name
        shutil.copy2(source, stored_path)

        clean_title = (title or source.stem).strip() or source.stem
        created_at = datetime.now().isoformat(timespec="seconds")
        with self._connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO photos
                    (album_id, title, description, original_name, stored_name, created_at, display_date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (album_id, clean_title, description.strip(), source.name, stored_name, created_at, created_at),
            )
            photo_id = int(cursor.lastrowid)
            conn.execute(
                """
                INSERT INTO photo_images (photo_id, original_name, stored_name, sort_order, record)
                VALUES (?, ?, ?, 1, ?)
                """,
                (photo_id, source.name, stored_name, description.strip()),
            )
        return self.get_photo(photo_id)

    def create_empty_photo(self, album_id: int, *, title: str = "未命名档案", description: str = "") -> Photo:
        clean_title = title.strip() or "未命名档案"
        created_at = datetime.now().isoformat(timespec="seconds")
        stored_name = f"__empty__-{uuid.uuid4().hex}"
        with self._connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO photos
                    (album_id, title, description, original_name, stored_name, created_at, display_date)
                VALUES (?, ?, ?, '', ?, ?, ?)
                """,
                (album_id, clean_title, description.strip(), stored_name, created_at, created_at),
            )
            photo_id = int(cursor.lastrowid)
        return self.get_photo(photo_id)

    def add_photo_images(self, photo_id: int, source_paths: list[Path | str]) -> list[PhotoImage]:
        if not source_paths:
            return self.list_photo_images(photo_id)
        self.get_photo(photo_id)
        copied: list[tuple[str, str]] = []
        for source_path in source_paths:
            source = Path(source_path)
            if not source.exists() or not source.is_file():
                raise FileNotFoundError(source)
            stored_name = self._copy_media_file(source)
            copied.append((source.name, stored_name))

        with self._connection() as conn:
            start_order = conn.execute(
                "SELECT COALESCE(MAX(sort_order), 0) FROM photo_images WHERE photo_id = ?",
                (photo_id,),
            ).fetchone()[0]
            for offset, (original_name, stored_name) in enumerate(copied, start=1):
                conn.execute(
                    """
                    INSERT INTO photo_images (photo_id, original_name, stored_name, sort_order)
                    VALUES (?, ?, ?, ?)
                    """,
                    (photo_id, original_name, stored_name, start_order + offset),
                )
            first_image = conn.execute(
                """
                SELECT original_name, stored_name FROM photo_images
                WHERE photo_id = ?
                ORDER BY sort_order, id
                LIMIT 1
                """,
                (photo_id,),
            ).fetchone()
            if first_image is not None:
                conn.execute(
                    "UPDATE photos SET original_name = ?, stored_name = ? WHERE id = ?",
                    (first_image["original_name"], first_image["stored_name"], photo_id),
                )
        return self.list_photo_images(photo_id)

    def update_photo(
        self,
        photo_id: int,
        *,
        title: str,
        description: str,
        album_id: int,
        display_date: str | None = None,
    ) -> Photo:
        clean_title = title.strip() or "未命名档案"
        with self._connection() as conn:
            if display_date is None:
                conn.execute(
                    "UPDATE photos SET title = ?, description = ?, album_id = ? WHERE id = ?",
                    (clean_title, description.strip(), album_id, photo_id),
                )
            else:
                conn.execute(
                    "UPDATE photos SET title = ?, description = ?, album_id = ?, display_date = ? WHERE id = ?",
                    (clean_title, description.strip(), album_id, display_date.strip(), photo_id),
                )
        return self.get_photo(photo_id)

    def update_photo_image_record(self, image_id: int, record: str) -> PhotoImage:
        with self._connection() as conn:
            conn.execute(
                "UPDATE photo_images SET record = ? WHERE id = ?",
                (record.strip(), image_id),
            )
            row = conn.execute(
                """
                SELECT id, photo_id, original_name, stored_name, sort_order, record
                FROM photo_images
                WHERE id = ?
                """,
                (image_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Photo image not found: {image_id}")
        return self._row_to_photo_image(row)

    def delete_photo(self, photo_id: int) -> None:
        photo = self.get_photo(photo_id)
        images = self.list_photo_images(photo_id)
        with self._connection() as conn:
            conn.execute("DELETE FROM photos WHERE id = ?", (photo_id,))
        self._unlink_media_paths([image.stored_path for image in images] + [photo.stored_path])

    def delete_album(self, album_id: int) -> None:
        photos = self.list_photos(album_id=album_id)
        media_paths: list[Path] = []
        for photo in photos:
            media_paths.extend(image.stored_path for image in self.list_photo_images(photo.id))
            media_paths.append(photo.stored_path)
        with self._connection() as conn:
            conn.execute("DELETE FROM albums WHERE id = ?", (album_id,))
        self._unlink_media_paths(media_paths)

    def get_photo(self, photo_id: int) -> Photo:
        with self._connection() as conn:
            row = conn.execute(
                self._photo_select_sql() + " WHERE photos.id = ?",
                (photo_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Photo not found: {photo_id}")
        return self._row_to_photo(row)

    def list_photos(self, *, album_id: int | None = None) -> list[Photo]:
        sql = self._photo_select_sql()
        params: tuple[object, ...] = ()
        if album_id is not None:
            sql += " WHERE photos.album_id = ?"
            params = (album_id,)
        sql += " ORDER BY photos.id"
        with self._connection() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_photo(row) for row in rows]

    def list_photo_images(self, photo_id: int) -> list[PhotoImage]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT id, photo_id, original_name, stored_name, sort_order, record
                FROM photo_images
                WHERE photo_id = ?
                ORDER BY sort_order, id
                """,
                (photo_id,),
            ).fetchall()
        return [self._row_to_photo_image(row) for row in rows]

    def search_photos(self, query: str) -> list[Photo]:
        needle = f"%{query.strip()}%"
        if needle == "%%":
            return self.list_photos()
        with self._connection() as conn:
            rows = conn.execute(
                self._photo_select_sql()
                + """
                WHERE photos.title LIKE ?
                   OR photos.description LIKE ?
                   OR albums.name LIKE ?
                   OR EXISTS (
                       SELECT 1 FROM photo_images
                       WHERE photo_images.photo_id = photos.id
                         AND photo_images.record LIKE ?
                   )
                ORDER BY photos.id
                """,
                (needle, needle, needle, needle),
            ).fetchall()
        return [self._row_to_photo(row) for row in rows]

    def paginate_photos(
        self,
        *,
        album_id: int | None = None,
        query: str = "",
        page: int = 1,
        per_page: int = 4,
    ) -> PhotoPage:
        page = max(1, page)
        per_page = max(1, per_page)
        where, params = self._photo_filters(album_id=album_id, query=query)
        with self._connection() as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM photos JOIN albums ON albums.id = photos.album_id" + where,
                params,
            ).fetchone()[0]
            total_pages = max(1, ceil(total / per_page))
            page = min(page, total_pages)
            rows = conn.execute(
                self._photo_select_sql()
                + where
                + " ORDER BY photos.id LIMIT ? OFFSET ?",
                (*params, per_page, (page - 1) * per_page),
            ).fetchall()
        return PhotoPage([self._row_to_photo(row) for row in rows], page, per_page, total, total_pages)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @contextmanager
    def _connection(self):
        conn = self._connect()
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _migrate(self) -> None:
        with self._connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS albums (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    sort_order INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS photos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    album_id INTEGER NOT NULL REFERENCES albums(id) ON DELETE CASCADE,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    original_name TEXT NOT NULL,
                    stored_name TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL,
                    display_date TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS photo_images (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    photo_id INTEGER NOT NULL REFERENCES photos(id) ON DELETE CASCADE,
                    original_name TEXT NOT NULL,
                    stored_name TEXT NOT NULL UNIQUE,
                    sort_order INTEGER NOT NULL,
                    record TEXT NOT NULL DEFAULT ''
                );
                """
            )
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(photos)").fetchall()}
            if "display_date" not in columns:
                conn.execute("ALTER TABLE photos ADD COLUMN display_date TEXT NOT NULL DEFAULT ''")
            conn.execute("UPDATE photos SET display_date = created_at WHERE display_date = ''")
            image_columns = {row["name"] for row in conn.execute("PRAGMA table_info(photo_images)").fetchall()}
            if "record" not in image_columns:
                conn.execute("ALTER TABLE photo_images ADD COLUMN record TEXT NOT NULL DEFAULT ''")
            conn.execute(
                """
                INSERT INTO photo_images (photo_id, original_name, stored_name, sort_order, record)
                SELECT photos.id, photos.original_name, photos.stored_name, 1, photos.description
                FROM photos
                WHERE photos.stored_name NOT LIKE '__empty__-%'
                  AND NOT EXISTS (
                      SELECT 1 FROM photo_images WHERE photo_images.photo_id = photos.id
                  )
                """
            )
            conn.execute(
                """
                UPDATE photo_images
                SET record = (
                    SELECT photos.description
                    FROM photos
                    WHERE photos.id = photo_images.photo_id
                )
                WHERE record = ''
                  AND sort_order = 1
                  AND EXISTS (
                      SELECT 1
                      FROM photos
                      WHERE photos.id = photo_images.photo_id
                        AND photos.description <> ''
                  )
                """
            )

    def _ensure_default_albums(self) -> None:
        with self._connection() as conn:
            count = conn.execute("SELECT COUNT(*) FROM albums").fetchone()[0]
            if count:
                return
            conn.executemany(
                "INSERT INTO albums (name, sort_order) VALUES (?, ?)",
                [(f"书签 {index}", index) for index in range(1, 5)],
            )

    def _photo_filters(self, *, album_id: int | None, query: str) -> tuple[str, tuple[object, ...]]:
        clauses: list[str] = []
        params: list[object] = []
        if album_id is not None:
            clauses.append("photos.album_id = ?")
            params.append(album_id)
        if query.strip():
            clauses.append(
                """(
                    photos.title LIKE ?
                    OR photos.description LIKE ?
                    OR albums.name LIKE ?
                    OR EXISTS (
                        SELECT 1 FROM photo_images
                        WHERE photo_images.photo_id = photos.id
                          AND photo_images.record LIKE ?
                    )
                )"""
            )
            needle = f"%{query.strip()}%"
            params.extend([needle, needle, needle, needle])
        if not clauses:
            return "", ()
        return " WHERE " + " AND ".join(clauses), tuple(params)

    def _row_to_photo(self, row: sqlite3.Row) -> Photo:
        return Photo(
            id=row["id"],
            album_id=row["album_id"],
            album_name=row["album_name"],
            title=row["title"],
            description=row["description"],
            original_name=row["original_name"],
            stored_path=self.media_dir / row["stored_name"],
            created_at=row["created_at"],
            display_date=row["display_date"],
            image_count=row["image_count"],
        )

    def _row_to_photo_image(self, row: sqlite3.Row) -> PhotoImage:
        return PhotoImage(
            id=row["id"],
            photo_id=row["photo_id"],
            original_name=row["original_name"],
            stored_path=self.media_dir / row["stored_name"],
            sort_order=row["sort_order"],
            record=row["record"],
        )

    def _copy_media_file(self, source: Path) -> str:
        extension = source.suffix.lower()
        stored_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:10]}{extension}"
        shutil.copy2(source, self.media_dir / stored_name)
        return stored_name

    @staticmethod
    def _unlink_media_paths(paths: list[Path]) -> None:
        seen: set[Path] = set()
        for path in paths:
            if path in seen:
                continue
            seen.add(path)
            if path.exists() and path.is_file():
                path.unlink()

    @staticmethod
    def _photo_select_sql() -> str:
        return """
            SELECT
                photos.id,
                photos.album_id,
                albums.name AS album_name,
                photos.title,
                photos.description,
                photos.original_name,
                photos.stored_name,
                photos.created_at,
                photos.display_date,
                (
                    SELECT COUNT(*)
                    FROM photo_images
                    WHERE photo_images.photo_id = photos.id
                ) AS image_count
            FROM photos
            JOIN albums ON albums.id = photos.album_id
        """
