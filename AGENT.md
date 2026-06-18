# AGENT.md

## 项目概览

PicRecordManager 是一个 Python + PySide6 桌面图片档案管理工具。应用入口是 `app.py`，核心窗口由 `pic_record_manager.gui.main()` 启动。运行时数据保存在 `data/archive.db` 和 `data/media/`，该目录被 `.gitignore` 忽略。

## 常用命令

安装依赖：

```powershell
python -m pip install -r requirements.txt
```

启动应用：

```powershell
python app.py
```

Windows 快速启动：

```powershell
.\start.bat
```

运行测试：

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
python -m unittest discover -s tests
```

## 项目层级结构

```text
PicRecordManager/
├─ app.py
├─ start.bat
├─ requirements.txt
├─ README.md
├─ AGENT.md
├─ pic_record_manager/
│  ├─ archive_store.py
│  ├─ gui.py
│  ├─ image_preview.py
│  ├─ import_worker.py
│  ├─ theme_assets.py
│  ├─ ui_constants.py
│  └─ ui_widgets.py
├─ tests/
│  ├─ test_archive_store.py
│  ├─ test_image_preview.py
│  ├─ test_import_worker.py
│  ├─ test_photo_card_layout.py
│  ├─ test_pyside_gui.py
│  └─ test_theme_assets.py
├─ Themes/
└─ data/
```

## 模块职责

- `pic_record_manager/archive_store.py`：SQLite schema、迁移、书签、档案、图片记录和媒体文件复制/删除。GUI 层不要直接写 SQL。
- `pic_record_manager/gui.py`：`ArchiveWindow`、列表页/详情页、页面切换、删除确认、导入线程协调和窗口入口。
- `pic_record_manager/ui_widgets.py`：复用控件和绘制类，包括 `AnimatedButton`、`StackedImagePreview`、`TiltImagePreview`、`AlbumItem`、`PhotoCard`、`PhotoRow`。
- `pic_record_manager/ui_constants.py`：窗口、卡片、字体、颜色、动画时间等 UI 常量。
- `pic_record_manager/import_worker.py`：后台图片导入 worker。批量文件复制不要放在 UI 线程。
- `pic_record_manager/image_preview.py`：等比缩略图加载。
- `pic_record_manager/theme_assets.py`：主题资源路径解析和可用资源枚举。

## 开发约定

- 修改前先查看 `git status --short`，不要覆盖用户已有改动。
- 保持改动范围小，优先沿用现有模块边界。
- 新增 UI 控件优先放到 `ui_widgets.py`；窗口流程协调保留在 `gui.py`。
- 调整尺寸、颜色、字体时优先改 `ui_constants.py`。
- 涉及数据库 schema 时同步更新 `_migrate()` 和存储层测试。
- 涉及导入、删除、详情页切换、图片记录保存时必须补充或更新 GUI 测试。
- PySide6 GUI 测试应设置 `QT_QPA_PLATFORM=offscreen`。
- 测试应使用临时目录，不要读写项目根目录下的 `data/`。
- 中文文案保持 UTF-8；终端乱码时先检查编码，不要按乱码内容改写。
- 不要提交 `data/` 下的运行时数据库或媒体文件。
- 不要随意改动 `Themes/` 中的二进制资源，除非用户明确要求。

## 交互和架构注意事项

- 删除照片或书签必须经过确认弹窗，不要恢复为直接删除。
- 图片导入应通过 `ImageImportWorker` 后台执行，不要在点击处理函数里同步复制大批量文件。
- 预览图应保持 `KeepAspectRatio`，不要为了填满卡片而裁剪图片。
- 主页面档案卡片当前是固定 3 列 x 2 行布局；改动时同步检查 `PHOTO_GRID_COLUMNS`、`PHOTO_GRID_ROWS` 和相关测试。
- `gui.py` 会 re-export 一些 widget 类和常量以兼容测试/外部导入；移动代码时注意保留这些导入面。

## Git 和推送

- 可以按需提交本地修改，但提交前要说明改动和验证结果。
- 如果需要推送，必须先询问用户要推送到哪个分支。
- 不要擅自创建分支并推送。
