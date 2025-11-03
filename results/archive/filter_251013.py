#!/usr/bin/env python3
"""
筛选包含 251013 的 JSON 文件，并将它们移动到新建的文件夹中
"""

import os
import shutil
import glob

def filter_251013_files():
    # 当前目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 新建的目标文件夹
    target_dir = os.path.join(current_dir, "filtered_251013")
    
    # 创建目标文件夹（如果不存在）
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)
        print(f"创建文件夹: {target_dir}")
    else:
        print(f"文件夹已存在: {target_dir}")
    
    # 查找所有包含 251013 的 JSON 文件
    pattern = "*251013*.json"
    files_to_move = glob.glob(os.path.join(current_dir, pattern))
    
    print(f"\n找到 {len(files_to_move)} 个包含 '251013' 的文件:")
    
    # 移动文件
    moved_count = 0
    for file_path in files_to_move:
        filename = os.path.basename(file_path)
        target_path = os.path.join(target_dir, filename)
        
        try:
            # 复制文件而不是移动，保留原文件
            shutil.copy2(file_path, target_path)
            print(f"✓ 复制: {filename}")
            moved_count += 1
        except Exception as e:
            print(f"✗ 复制失败: {filename} - {str(e)}")
    
    print(f"\n成功复制了 {moved_count} 个文件到 {target_dir}")
    
    # 显示目标文件夹中的文件
    print(f"\n{target_dir} 中的文件:")
    for file in sorted(os.listdir(target_dir)):
        if file.endswith('.json'):
            print(f"  - {file}")

if __name__ == "__main__":
    filter_251013_files()