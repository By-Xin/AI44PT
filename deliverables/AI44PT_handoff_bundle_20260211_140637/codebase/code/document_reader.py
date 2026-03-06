"""
文档读取模块 - 处理PDF和Markdown文件的读取
"""
import re
from pathlib import Path
from typing import List, Dict
import fitz


class DocumentReader:
    """文档读取器类"""
    
    @staticmethod
    def read_pdf(path: str) -> List[Dict[str, any]]:
        """
        读取PDF文件并提取每页文本
        
        Args:
            path: PDF文件路径
            
        Returns:
            包含页码和文本的字典列表
        """
        doc = fitz.open(path)
        pages = []
        for i, pg in enumerate(doc):
            pages.append({'page': i+1, 'text': pg.get_text('text') or ''})
        doc.close()  # 添加文档关闭
        return pages

    @staticmethod
    def read_markdown(path: str, heading_pattern: str = r'^#{1,6}\s') -> List[Dict[str, any]]:
        """
        读取Markdown文件并按标题分节
        
        Args:
            path: Markdown文件路径
            heading_pattern: 标题识别的正则表达式
            
        Returns:
            包含节号和文本的字典列表
        """
        heading_re = re.compile(heading_pattern)
        sections = []
        current_lines = []
        section_idx = 1
        
        with open(path, 'r', encoding='utf-8') as f:
            for raw_line in f:
                line = raw_line.rstrip('\n')
                if heading_re.match(line.strip()):
                    if current_lines:
                        sections.append({
                            'page': section_idx, 
                            'text': '\n'.join(current_lines).strip()
                        })
                        section_idx += 1
                    current_lines = [line]
                else:
                    current_lines.append(line)
                    
        # 处理最后一节
        if current_lines:
            sections.append({
                'page': section_idx, 
                'text': '\n'.join(current_lines).strip()
            })
        
        # 如果没有找到节，将整个文件作为一节
        if not sections:
            text = Path(path).read_text(encoding='utf-8')
            sections.append({'page': 1, 'text': text})
            
        return sections