# PicRecordManager

一个基于 PySide6 的桌面档案管理原型。当前界面采用暗黑色基调、现代卡片布局和标准桌面交互，保留左侧书签分类与右侧图片预览卡片两个核心区域。

## 运行

```powershell
python -m pip install -r requirements.txt
python app.py
```

## 当前功能

- 左侧书签分类
- 新建书签
- 批量导入档案照片并复制到 `data/media`
- 图片预览卡片和列表视图切换
- 点击预览卡片进入详情页，左侧查看大图，右侧编辑文字并保存
- 标题、备注、书签检索
- 详情页左上角返回列表
- SQLite 本地存储，数据库位于 `data/archive.db`

## 说明

界面暂时不使用纸质背景、胶带装饰或主题图片资源，以便先把基础交互和布局打稳。桌面 GUI 使用 PySide6，图片预览使用 Qt 图像能力生成缩略图，支持常见格式，如 `.png`、`.jpg`、`.jpeg`、`.bmp`、`.gif`。
