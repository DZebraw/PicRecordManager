# AGENT.md

## 项目概览

这是一个基于 Python 和 PySide6 的桌面图片档案管理项目。应用入口是 `app.py`，会调用 `pic_record_manager.gui.main()` 启动 GUI。

主要目录：

- `pic_record_manager/`：核心应用代码。
- `tests/`：单元测试和 PySide6 GUI 测试。
- `Themes/`：界面主题、图标、图片和字体资源。
- `data/`：本地运行数据，包括 SQLite 数据库和导入媒体文件；该目录已被 `.gitignore` 忽略。

## 常用命令

安装依赖：

```powershell
python -m pip install -r requirements.txt
```

启动应用：

```powershell
python app.py
```

也可以在 Windows 上运行：

```powershell
.\start.bat
```

运行测试：

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
python -m unittest discover -s tests
```

注意：当前测试文件里可能仍有历史包名导入，例如 `endfielddoc.*`，而源码目录是 `pic_record_manager/`。如果测试因此失败，先确认这是待迁移问题还是兼容别名问题，再修改。

## 开发约定

- 修改前先查看 `git status --short`，不要覆盖用户已有改动。
- 保持改动范围尽量小，优先沿用现有模块和风格。
- UI 代码主要在 `pic_record_manager/gui.py`，存储逻辑在 `pic_record_manager/archive_store.py`，图片预览逻辑在 `pic_record_manager/image_preview.py`，主题资源定位在 `pic_record_manager/theme_assets.py`。
- 中文界面文案请保持 UTF-8 编码；如果终端显示乱码，先检查编码，不要直接把乱码当成真实文案重写。
- 不要提交 `data/` 下的运行时数据库或媒体文件。
- 不要随意改动 `Themes/` 中的二进制资源；只有用户明确要求调整视觉资源时再处理。

## 测试注意事项

- PySide6 GUI 测试应使用 `QT_QPA_PLATFORM=offscreen`，避免依赖真实显示器。
- 涉及数据库和媒体文件的测试应使用临时目录，不要读写项目根目录下的 `data/`。
- 修改存储 schema 时，同步检查迁移逻辑、现有数据兼容性，以及删除媒体文件的行为。
- 修改 GUI 布局或交互时，优先补充或更新对应的 GUI 测试，尤其是按钮、详情页、图片切换、分页和删除行为。

## Git 和推送

- 可以按需提交本地修改，但提交前要说明改动和验证结果。
- 如果需要推送，必须先询问用户要推送到哪个分支。
- 不要擅自创建分支并推送。
