# src/app/services/postgre_db/postgre_files_repository.py

import psycopg

from src.dom.entities.file import File


class PostgreFilesRepository:
    """
    Repository chịu trách nhiệm thao tác metadata của file trong PostgreSQL.

    Lưu ý:
    - Repository này KHÔNG đọc/ghi file vật lý.
    - Nội dung file thật vẫn nằm trong workspace trên filesystem.
    - Bảng `files` chỉ lưu metadata như:
        + tên file
        + đường dẫn
        + loại file
        + kích thước
        + conversation sở hữu file
        + quan hệ thư mục cha/con
    """

    def __init__(
            self,
            connection: psycopg.Connection
    ):
        # Connection được truyền từ bên ngoài vào,
        # giống với các Postgre repository khác trong project.
        self.connection = connection

    @staticmethod
    def _row_to_file(row) -> File:
        """
        Chuyển một row lấy từ PostgreSQL thành entity File.

        Việc gom logic mapping vào một chỗ giúp:
        - tránh lặp File(...) ở tất cả các method;
        - tránh sai index khi bảng có nhiều cột;
        - sau này thay đổi entity sẽ dễ sửa hơn.
        """

        return File(
            id=row[0],
            conversation_id=row[1],
            parent_id=row[2],
            name=row[3],
            path=row[4],
            is_directory=row[5],
            file_type=row[6],
            mime_type=row[7],
            size=row[8],
            source=row[9],
            created_at=row[10],
            updated_at=row[11],
        )

    def get_by_id(
            self,
            file_id: int
    ) -> File | None:
        """
        Lấy một file theo ID.

        Trả về:
        - File nếu tìm thấy.
        - None nếu file không tồn tại.
        """

        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    conversation_id,
                    parent_id,
                    name,
                    path,
                    is_directory,
                    file_type,
                    mime_type,
                    size,
                    source,
                    created_at,
                    updated_at
                FROM files
                WHERE id = %s
                """,
                (
                    file_id,
                )
            )

            row = cursor.fetchone()

        if row is None:
            return None

        return self._row_to_file(row)

    def get_by_conversation_id(
            self,
            conversation_id: int
    ) -> list[File]:
        """
        Lấy toàn bộ file và thư mục thuộc một conversation.

        Method này hữu ích khi cần:
        - lấy toàn bộ workspace;
        - đồng bộ workspace;
        - thực hiện xử lý backend trên toàn bộ cây file.

        Nếu chỉ render từng cấp thư mục trên UI thì nên ưu tiên
        get_children() thay vì load toàn bộ.
        """

        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    conversation_id,
                    parent_id,
                    name,
                    path,
                    is_directory,
                    file_type,
                    mime_type,
                    size,
                    source,
                    created_at,
                    updated_at
                FROM files
                WHERE conversation_id = %s
                ORDER BY
                    is_directory DESC,
                    name ASC
                """,
                (
                    conversation_id,
                )
            )

            rows = cursor.fetchall()

        return [
            self._row_to_file(row)
            for row in rows
        ]

    def get_children(
            self,
            conversation_id: int,
            parent_id: int | None = None
    ) -> list[File]:
        """
        Lấy các file/thư mục con trực tiếp của một thư mục.

        parent_id = None:
            -> lấy các item ở thư mục gốc của workspace.

        parent_id = 10:
            -> lấy các item có parent_id = 10.

        Ví dụ:

            workspace/
                report.md
                research/
                    source.json

        report.md và research/ có parent_id = NULL.

        source.json có parent_id = ID của research/.
        """

        with self.connection.cursor() as cursor:

            # NULL trong SQL không thể so sánh bằng "= NULL",
            # vì vậy root directory phải dùng "IS NULL".
            if parent_id is None:
                cursor.execute(
                    """
                    SELECT
                        id,
                        conversation_id,
                        parent_id,
                        name,
                        path,
                        is_directory,
                        file_type,
                        mime_type,
                        size,
                        source,
                        created_at,
                        updated_at
                    FROM files
                    WHERE conversation_id = %s
                      AND parent_id IS NULL
                    ORDER BY
                        is_directory DESC,
                        name ASC
                    """,
                    (
                        conversation_id,
                    )
                )

            else:
                cursor.execute(
                    """
                    SELECT
                        id,
                        conversation_id,
                        parent_id,
                        name,
                        path,
                        is_directory,
                        file_type,
                        mime_type,
                        size,
                        source,
                        created_at,
                        updated_at
                    FROM files
                    WHERE conversation_id = %s
                      AND parent_id = %s
                    ORDER BY
                        is_directory DESC,
                        name ASC
                    """,
                    (
                        conversation_id,
                        parent_id,
                    )
                )

            rows = cursor.fetchall()

        return [
            self._row_to_file(row)
            for row in rows
        ]

    def get_by_path(
            self,
            conversation_id: int,
            path: str
    ) -> File | None:
        """
        Tìm file dựa trên path bên trong workspace của conversation.

        Phải truyền cả conversation_id vì cùng một path có thể tồn tại
        ở nhiều conversation khác nhau.

        Ví dụ:

            conversation 10 -> reports/result.md
            conversation 20 -> reports/result.md

        Hai file trên hoàn toàn độc lập.
        """

        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    conversation_id,
                    parent_id,
                    name,
                    path,
                    is_directory,
                    file_type,
                    mime_type,
                    size,
                    source,
                    created_at,
                    updated_at
                FROM files
                WHERE conversation_id = %s
                  AND path = %s
                """,
                (
                    conversation_id,
                    path,
                )
            )

            row = cursor.fetchone()

        if row is None:
            return None

        return self._row_to_file(row)

    def create(
            self,
            conversation_id: int,
            name: str,
            path: str,
            parent_id: int | None = None,
            is_directory: bool = False,
            file_type: str | None = None,
            mime_type: str | None = None,
            size: int = 0,
            source: str = "USER",
    ) -> File:
        """
        Tạo metadata cho một file hoặc thư mục mới.

        Method này CHỈ insert metadata vào PostgreSQL.
        Nó không tạo file thật trên ổ đĩa.

        Ví dụ Agent vừa tạo:

            reports/phong_nha.md

        thì filesystem/file tool chịu trách nhiệm ghi file thật,
        còn method này đăng ký metadata của file vào DB.

        source có thể dùng để phân biệt nguồn tạo file, ví dụ:
            USER
            AGENT
        """

        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO files(
                    conversation_id,
                    parent_id,
                    name,
                    path,
                    is_directory,
                    file_type,
                    mime_type,
                    size,
                    source
                )
                VALUES(
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                RETURNING
                    id,
                    conversation_id,
                    parent_id,
                    name,
                    path,
                    is_directory,
                    file_type,
                    mime_type,
                    size,
                    source,
                    created_at,
                    updated_at
                """,
                (
                    conversation_id,
                    parent_id,
                    name,
                    path,
                    is_directory,
                    file_type,
                    mime_type,
                    size,
                    source,
                )
            )

            row = cursor.fetchone()

        # INSERT thay đổi dữ liệu nên phải commit.
        self.connection.commit()

        return self._row_to_file(row)

    def update(
            self,
            file_id: int,
            name: str,
            path: str,
            parent_id: int | None,
            is_directory: bool,
            file_type: str | None,
            mime_type: str | None,
            size: int,
    ) -> File | None:
        """
        Cập nhật metadata của một file hoặc thư mục.

        Có thể dùng khi:
        - đổi tên file/thư mục;
        - đổi path;
        - di chuyển sang thư mục cha khác;
        - file chuyển thành directory hoặc ngược lại;
        - nội dung file thay đổi làm size thay đổi;
        - mime type / file type thay đổi.

        Lưu ý:
        - source không được update ở đây vì nguồn tạo file
          (USER / AGENT) cần được giữ nguyên.
        - conversation_id cũng không thay đổi vì file vẫn
          thuộc conversation ban đầu.
        - updated_at được cập nhật tại thời điểm UPDATE.
        """

        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE files
                SET
                    parent_id = %s,
                    name = %s,
                    path = %s,
                    is_directory = %s,
                    file_type = %s,
                    mime_type = %s,
                    size = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s

                RETURNING
                    id,
                    conversation_id,
                    parent_id,
                    name,
                    path,
                    is_directory,
                    file_type,
                    mime_type,
                    size,
                    source,
                    created_at,
                    updated_at
                """,
                (
                    parent_id,
                    name,
                    path,
                    is_directory,
                    file_type,
                    mime_type,
                    size,
                    file_id,
                )
            )

            row = cursor.fetchone()

        # UPDATE làm thay đổi dữ liệu nên commit transaction.
        self.connection.commit()

        # Không tìm thấy file_id tương ứng.
        if row is None:
            return None

        return self._row_to_file(row)

    def update_size(
            self,
            file_id: int,
            size: int
    ) -> File | None:
        """
        Chỉ cập nhật kích thước file.

        Method riêng này hữu ích vì Agent thường sửa nội dung file
        nhưng không thay đổi name/path/type.

        Không cần gọi update() với hàng loạt giá trị cũ chỉ để đổi size.
        """

        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE files
                SET
                    size = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                RETURNING
                    id,
                    conversation_id,
                    parent_id,
                    name,
                    path,
                    is_directory,
                    file_type,
                    mime_type,
                    size,
                    source,
                    created_at,
                    updated_at
                """,
                (
                    size,
                    file_id,
                )
            )

            row = cursor.fetchone()

        self.connection.commit()

        if row is None:
            return None

        return self._row_to_file(row)

    def delete(
            self,
            file_id: int
    ) -> bool:
        """
        Xóa metadata file khỏi PostgreSQL.

        Trả về:
        - True: có record được xóa.
        - False: file_id không tồn tại.

        QUAN TRỌNG:
        Method này KHÔNG xóa file vật lý khỏi filesystem.

        Nếu record là directory thì nhờ:
            fk_files_parent ... ON DELETE CASCADE

        PostgreSQL sẽ tự xóa metadata của các file/thư mục con.
        """

        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM files
                WHERE id = %s
                RETURNING id
                """,
                (
                    file_id,
                )
            )

            row = cursor.fetchone()

        self.connection.commit()

        return row is not None
