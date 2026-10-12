# DocAI đã tách riêng

Repo chính đang chuyển sang `Thundercok/nesy-docai`; DocAI hiện nằm ở
[modules/docai](../modules/docai/README.md), với package, CLI, dependencies và
tests riêng. `inspect_invoice` đã được gỡ khỏi registry RAT mặc định. Tích hợp
sẽ được thực hiện trong một lượt sau theo yêu cầu của người dùng.

Xem [repository_migration.md](repository_migration.md) cho trạng thái chuyển repo.
Tài liệu import NeSy vào reasoning ở lượt trước được giữ tại
[history/nesy_docai_import_20261012.md](history/nesy_docai_import_20261012.md) như
một bản ghi lịch sử; các đường dẫn/khả năng RAT trong bản đó đã được thay thế.
