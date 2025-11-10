import shutil
from pathlib import Path

# 1. 删除 output 目录下的所有内容（保留 output 目录本身）
output_dir = Path("output")
if output_dir.exists() and output_dir.is_dir():
    for item in output_dir.iterdir():
        try:
            if item.is_dir():
                shutil.rmtree(item)  # 递归删除子目录
            else:
                item.unlink()  # 删除文件
        except Exception as e:
            print(f"删除 {item} 失败: {e}")

# 2. 删除指定目录
delete_paths = [
    "./train/dataset/cache",
    "./train/dataset/target",
    "./train/edit-dataset/cache",
    "./train/edit-dataset/control",
    "./train/edit-dataset/target"
]
for path_str in delete_paths:
    path = Path(path_str)
    if path.exists():
        try:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()  # 若为文件则直接删除
        except Exception as e:
            print(f"删除 {path} 失败: {e}")

# 3. 创建目录（父目录不存在则自动创建，目录已存在不报错）
mkdir_paths = [
    "./train/dataset/target",
    "./train/dataset/cache",
    "./train/edit-dataset/cache",
    "./train/edit-dataset/control",
    "./train/edit-dataset/target"
]
for path_str in mkdir_paths:
    path = Path(path_str)
    try:
        path.mkdir(parents=True, exist_ok=True)  # 等效于 mkdir -p
    except Exception as e:
        print(f"创建 {path} 失败: {e}")