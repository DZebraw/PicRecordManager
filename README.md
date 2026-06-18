# PicRecordManager

PicRecordManager 是一个基于 Python 和 PySide6 的桌面图片档案管理工具。它用本地 SQLite 保存档案、书签和图片记录，把导入的媒体文件复制到本地 `data/media`，并提供书签分类、预览卡片、详情页多图切换和图片文字记录编辑。

## 快速开始

```powershell
python -m pip install -r requirements.txt
python app.py
```

Windows 下也可以双击或运行：

```powershell
.\start.bat
```

运行测试：

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
python -m unittest discover -s tests
```

## 当前功能

- 左侧书签分类、创建、重命名和删除。
- 新建空档案，进入详情页后可导入多张图片。
- 图片文件复制到 `data/media`，档案数据存储在 `data/archive.db`。
- 主页面以固定 3 列 x 2 行预览卡片展示档案。
- 预览卡片保留完整图片比例，不裁剪缩略图。
- 详情页支持多图前后切换、单图记录编辑和保存。
- 图片导入使用后台 worker，避免大批量复制时阻塞 UI。
- 删除照片和书签前会弹出确认，避免误删。

## 项目层级结构

```text
PicRecordManager/
├─ app.py                         # 应用入口，调用 pic_record_manager.gui.main()
├─ start.bat                      # Windows 快速启动脚本
├─ requirements.txt               # 运行依赖：PySide6、Pillow
├─ README.md                      # 给开发者和新同学看的项目说明
├─ AGENT.md                       # 给后续代码代理看的工程约定
├─ pic_record_manager/
│  ├─ __init__.py
│  ├─ archive_store.py            # SQLite schema、迁移、书签/档案/图片记录 CRUD
│  ├─ gui.py                      # QMainWindow、页面组织、用户流程和信号协调
│  ├─ image_preview.py            # 用 Qt 图像能力加载等比缩略图
│  ├─ import_worker.py            # 后台图片导入 worker
│  ├─ theme_assets.py             # 主题资源路径解析和资源枚举
│  ├─ ui_constants.py             # UI 尺寸、颜色、字体等常量
│  └─ ui_widgets.py               # 复用 PySide6 控件、卡片、预览绘制和书签项
├─ tests/
│  ├─ test_archive_store.py       # 存储层和迁移行为
│  ├─ test_image_preview.py       # 缩略图加载
│  ├─ test_import_worker.py       # 后台导入 worker
│  ├─ test_photo_card_layout.py   # 预览卡片布局和堆叠绘制回归
│  ├─ test_pyside_gui.py          # GUI 交互、详情页、删除确认、导入 busy 状态
│  └─ test_theme_assets.py        # 主题资源解析
├─ Themes/                        # 主题图片、图标、字体资源
└─ data/                          # 本地运行数据；被 .gitignore 忽略
```

## 代码职责梳理

`archive_store.py` 是唯一直接操作 SQLite 和媒体文件复制/删除的模块。GUI 层不要手写 SQL，也不要直接管理数据库连接。

`gui.py` 负责应用窗口、列表页、详情页、页面切换、删除确认、后台导入线程接线和状态刷新。它应保持“流程协调者”的角色，复杂控件优先放到 `ui_widgets.py`。

`ui_widgets.py` 放可复用的 PySide6 控件和绘制逻辑，例如预览堆叠、详情图片预览、档案卡片、书签项。新增视觉组件时优先放这里。

`ui_constants.py` 集中 UI 常量。调整卡片尺寸、颜色、字体、窗口尺寸时优先改这里，避免常量散落在窗口逻辑里。

`import_worker.py` 在后台线程中创建独立 `ArchiveStore` 实例并导入图片。不要在 UI 线程里批量复制文件。

`theme_assets.py` 只做主题资源路径解析，不负责绘制或业务逻辑。

## 新同学上手建议

1. 先运行测试，确认本地环境可用：

   ```powershell
   $env:QT_QPA_PLATFORM = "offscreen"
   python -m unittest discover -s tests
   ```

2. 从 `app.py` 进入 `pic_record_manager.gui.main()`，再看 `ArchiveWindow` 如何组织列表页和详情页。

3. 想理解数据模型，先看 `archive_store.py` 中的 `Album`、`Photo`、`PhotoImage` 和 `_migrate()`。

4. 想改卡片或预览效果，优先看 `ui_widgets.py` 和 `tests/test_photo_card_layout.py`。

5. 想改导入流程，先看 `import_worker.py` 和 `ArchiveWindow.import_images_to_detail()`。

6. 改交互前先补测试，尤其是删除、导入、详情页切换和图片记录保存。

## 开发注意事项

- `data/` 是运行时数据，不要提交数据库或导入图片。
- PySide6 GUI 测试需要设置 `QT_QPA_PLATFORM=offscreen`。
- 中文文案统一保持 UTF-8；如果 PowerShell 显示乱码，先确认终端编码，不要把乱码当作真实文案改写。
- 删除和导入属于高风险交互，修改时要覆盖取消、失败和成功路径。
- 如果需要推送，必须先询问要推送到哪个分支，不要擅自创建分支推送。
