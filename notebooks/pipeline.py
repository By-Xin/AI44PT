# 4PT Batch Analysis Pipeline
# 批量处理Excel中的文章并生成AI分析结果

import os
import json
import re
import math
import pathlib
import textwrap
import pandas as pd
import numpy as np
from openai import OpenAI
import fitz  # PyMuPDF
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

# === 配置 ===
# EXCEL_PATH = "/Users/xinby/Desktop/AI44PT_Desktop/data/processed/JRGsamples/JRG article sublist.xlsx"
EXCEL_PATH = "/Users/xinby/Desktop/AI44PT_Desktop/data/processed/JRGsamples/2sample.xlsx"
PDF_FOLDER = "/Users/xinby/Desktop/AI44PT_Desktop/data/processed/JRGsamples/"
CODEBOOK_MD = "/Users/xinby/Desktop/AI44PT_Desktop/data/processed/TheCodingTask.md"
# 修改输出路径到根目录/results文件夹
OUTPUT_DIR = "/Users/xinby/Desktop/AI44PT_Desktop/results/"
OUTPUT_EXCEL = os.path.join(OUTPUT_DIR, f"analysis_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")

CLS_MODEL = "gpt-5-2025-08-07"
# 分析参数配置
TEMPERATURE = 0.1  # 设为0.0确保完全确定性结果，0.1为轻微随机性
AI_RUNS = 3  # 设为3或5可并行记录多次运行结果

# OpenAI API 高级参数配置（仅适用于支持的模型）
REASONING_EFFORT = "high"  # 推理努力程度: "low", "medium", "high"
TEXT_VERBOSITY = "medium"  # 文本详细程度: "low", "medium", "high"

# 构建基础source标识（包含模型和参数信息）
BASE_AI_SOURCE_ID = f"{CLS_MODEL}-temp{TEMPERATURE}"

# 确保输出目录存在
os.makedirs(OUTPUT_DIR, exist_ok=True)

# OpenAI client
client = OpenAI(api_key=api_key)
print(f"OpenAI client initialized. Using model: {CLS_MODEL}")

# Load codebook
CODEBOOK_TEXT = pathlib.Path(CODEBOOK_MD).read_text(encoding="utf-8")
print(f"Loaded Codebook.md: {len(CODEBOOK_TEXT)} chars")

# === 原始的4PT分析问题（保持不变）===
FOURPT_QUESTIONS = """
Please analyze this article using the 4PT framework by answering the following questions:

1. Does the article fit in the universe of sustainability analyses we seek to assess? (Yes/No)

2. What problems or set of problems is the article trying to address?

3. Do the analysis, conclusions, and theories derived from, and directed to, understanding and/or managing a clearly specified 'on the ground' problem or class of problems? (Yes/No)

4. Provide arguments that support your response to Q3 (Does the article address a clearly specified on-ground problem?)

5. Provide some key text passages from the article that support your Q3 response

6. Are the analysis, conclusions, and theories generated to apply beyond understanding, and/or managing a clearly specified 'on the ground' problem or class of problems? (Yes/No)

7. Provide arguments that support your response to Q6 (Does the article generate analysis, conclusions, and theories to apply beyond understanding/managing a clearly specified on-ground problem?)

8. Provide some key text passages from the article that support your Q6 response

9. Do the analysis, conclusions, and theories treat individuals, organizations and states as largely self-interested, satisfaction driven entities that seek to maximize some kind of 'utility' outcome? (Yes/No)

10. Provide arguments that support your response to Q9 (Does the article treat entities as self-interested, utility-maximizing agents?)

11. Provide some key text passages from the article that support your Q9 response

12. Do the analysis incorporate theories and conclusions incorporate an assessment of individuals, organizations and/or states that extends beyond self-interested satisfaction seeking motivations? (Yes/No)

13. Provide arguments that support your response to Q12 (Does the article extend beyond self-interested satisfaction seeking motivations?)

14. Provide some key text passages from the article that support your Q12 response

15. Based on your analysis above, what is your final 4PT Type classification? (Type 1 / Type 2 / Type 3 / Type 4)

16. What is the difficulty level of this classification? (1 - Very Easy / 2 - Easy / 3 - Medium / 4 - Hard / 5 - Very Hard)

Please answer each question clearly and provide specific evidence from the text when requested.
"""

STRUCTURED_RESPONSE_INSTRUCTIONS = """
- Produce your answers using the exact XML-style template below.
- Do not add any commentary or text outside the template.
- Keep all citations, bullet lists, and supporting evidence inside the corresponding <Q#> tags.
- Preserve multi-line structure within a tag when presenting multiple bullet points or citations.

<BEGIN_4PT_RESPONSE>
<Q1>[Answer here]</Q1>
<Q2>[Answer here]</Q2>
<Q3>[Answer here]</Q3>
<Q4>[Answer here]</Q4>
<Q5>[Answer here]</Q5>
<Q6>[Answer here]</Q6>
<Q7>[Answer here]</Q7>
<Q8>[Answer here]</Q8>
<Q9>[Answer here]</Q9>
<Q10>[Answer here]</Q10>
<Q11>[Answer here]</Q11>
<Q12>[Answer here]</Q12>
<Q13>[Answer here]</Q13>
<Q14>[Answer here]</Q14>
<Q15>[Answer here]</Q15>
<Q16>[Answer here]</Q16>
</END_4PT_RESPONSE>
""".strip()


def read_pdf(path: str):
    """Read PDF and extract text from all pages"""
    try:
        doc = fitz.open(path)
        pages = []
        for i, pg in enumerate(doc):
            pages.append({'page': i+1, 'text': pg.get_text('text') or ''})
        doc.close()
        return pages
    except Exception as e:
        print(f"  ⚠️ Error reading PDF {path}: {e}")
        return None


def read_markdown(path: str, heading_pattern: str = r'^#{1,6}\s'):
    """Read markdown file and split into sections"""
    heading_re = re.compile(heading_pattern)
    sections = []
    current_lines = []
    section_idx = 1
    with open(path, 'r', encoding='utf-8') as f:
        for raw_line in f:
            line = raw_line.rstrip('\n')
            if heading_re.match(line.strip()):
                if current_lines:
                    sections.append({'page': section_idx, 'text': '\n'.join(current_lines).strip()})
                    section_idx += 1
                current_lines = [line]
            else:
                current_lines.append(line)
        if current_lines:
            sections.append({'page': section_idx, 'text': '\n'.join(current_lines).strip()})
    if not sections:
        text = pathlib.Path(path).read_text(encoding='utf-8')
        sections.append({'page': 1, 'text': text})
    return sections


def analyze_article_fourpt_single(article_pages: list, codebook_pages: list, model: str = CLS_MODEL):
    if not article_pages:
        return None, None
    
    # 将页面内容合并为文本
    article_text = "\n\n".join([f"Page {p['page']}:\n{p['text']}" for p in article_pages])
    codebook_text = "\n\n".join([f"Section {p['page']}:\n{p['text']}" for p in codebook_pages])
    
    prompt = f"""
You are an expert public policy analyst reviewing sustainability research articles. 

**Instructions:**
- Answer ALL questions only based on the provided Codebook and Article
- Provide specific citations when requested
- Keep justifications concise and evidence-based
- For Yes/No questions, choose definitively based on evidence
- For Yes-or-No or multiple choice problems, answer from the given options only (the options are in parentheses)
- Format your entire response using the XML template below to ensure each answer stays inside its <Q#> tag. Do not include any text outside the template.

{STRUCTURED_RESPONSE_INSTRUCTIONS}

**4PT Codebook:**
{codebook_text}

**Article to Analyze:**
{article_text[:50000]}  # 限制长度避免超出token限制

{FOURPT_QUESTIONS}
    """.strip()

    try:
        # 尝试新API格式，如果不可用则使用标准API
        try:
            response = client.responses.create(
                model=model,
                input=prompt,
                reasoning={"effort": REASONING_EFFORT},
                text={"verbosity": TEXT_VERBOSITY},
            )
            analysis_text = response.output_text
        except AttributeError:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=30000,
                temperature=TEMPERATURE
            )
            analysis_text = response.choices[0].message.content
        
        # 在API调用完成后立即生成时间戳
        api_timestamp = get_timestamp()
        return analysis_text, api_timestamp
        
    except Exception as e:
        print(f"  ⚠️ Error in analysis: {e}")
        return None, None


def analyze_article_fourpt_multiple(article_pages: list, codebook_pages: list, model: str = CLS_MODEL):
    """使用4PT框架分析文章 - 支持多次独立运行"""
    if AI_RUNS <= 1:
        # 单次运行
        response, timestamp = analyze_article_fourpt_single(article_pages, codebook_pages, model)
        if response:
            answers = parse_ai_response(response)
            return [(answers, timestamp)] if answers else []
        return []
    
    # 多次独立运行模式
    print(f"    🔄 Running {AI_RUNS} independent iterations...")
    answer_sets = []
    
    for i in range(AI_RUNS):
        print(f"      Iteration {i+1}/{AI_RUNS}...")
        response, timestamp = analyze_article_fourpt_single(article_pages, codebook_pages, model)
        if response:
            answers = parse_ai_response(response)
            if answers:
                answer_sets.append((answers, timestamp))
            else:
                print(f"      ⚠️ Iteration {i+1} failed to parse")
                answer_sets.append((None, timestamp))  # 保持位置对应，仍然记录时间戳
        else:
            print(f"      ⚠️ Iteration {i+1} failed")
            answer_sets.append((None, get_timestamp()))  # 失败时也记录时间戳
    
    print(f"    ✅ Completed {sum(1 for x, _ in answer_sets if x is not None)}/{AI_RUNS} successful runs")
    
    return answer_sets


def parse_ai_response(response_text):
    """解析AI的响应文本，提取每个问题的答案"""
    if not response_text:
        return {}
    
    answers = {}

    # 方法1：优先解析结构化模板
    structured_block = re.search(r'<BEGIN_4PT_RESPONSE>(.*?)</END_4PT_RESPONSE>', response_text, re.DOTALL | re.IGNORECASE)
    template_body = structured_block.group(1) if structured_block else response_text

    structured_matches = re.findall(r'<Q(\d+)>(.*?)</Q\1>', template_body, re.DOTALL | re.IGNORECASE)

    for q_str, raw_answer in structured_matches:
        try:
            q_num = int(q_str)
            answer = re.sub(r'\r\n?', '\n', raw_answer).strip()
            answer = re.sub(r'[ \t]+\n', '\n', answer)
            answer = re.sub(r'\n{3,}', '\n\n', answer)
            answers[q_num] = answer
        except ValueError:
            continue

    # 方法2：如果结构化解析缺失部分，回退到数字分割
    if len(answers) < 16:
        pattern = r'(?:^|\n)(?:Q?(\d+)[\.\):\s]+)(.*?)(?=\n(?:Q?\d+[\.\):\s])|$)'
        matches = re.findall(pattern, response_text, re.DOTALL | re.MULTILINE)

        for match in matches:
            try:
                q_num = int(match[0])
                if q_num in answers:
                    continue
                answer = match[1].strip()
                answer = re.sub(r'\n+', ' ', answer)
                answer = re.sub(r'\s+', ' ', answer)
                answers[q_num] = answer
            except ValueError:
                continue

    # 方法3：仍未解析足够答案时逐行解析
    if len(answers) < 10:
        lines = response_text.split('\n')
        current_q = None
        current_answer = []

        for line in lines:
            match = re.match(r'^(?:Q?)?(\d+)[\.\):\s]+(.*)', line.strip())
            if match:
                if current_q and current_q not in answers:
                    answers[current_q] = ' '.join(current_answer).strip()
                current_q = int(match.group(1))
                current_answer = [match.group(2)] if match.group(2) else []
            elif current_q and line.strip():
                current_answer.append(line.strip())

        if current_q and current_q not in answers:
            answers[current_q] = ' '.join(current_answer).strip()
    
    # 特殊处理：提取Yes/No答案
    for q_num in [1, 3, 6, 9, 12]:
        if q_num in answers:
            text = answers[q_num]
            # 查找Yes或No（忽略大小写）
            if re.search(r'\byes\b', text, re.IGNORECASE):
                answers[q_num] = "Yes"
            elif re.search(r'\bno\b', text, re.IGNORECASE):
                answers[q_num] = "No"
    
    return answers


# def _self_test_parse_ai_response():
#     """Lightweight sanity check to verify structured parsing retains citations and multi-line content."""
#     sample_response = textwrap.dedent(
#         """
#         Introductory note that should be ignored.
#         <BEGIN_4PT_RESPONSE>
#         <Q1>Yes</Q1>
#         <Q2>The article evaluates regulatory gaps in carbon market oversight.</Q2>
#         <Q3>No</Q3>
#         <Q4>The discussion focuses on theoretical trade-offs without a specific local deployment.</Q4>
#         <Q5>- "Page 12: Section 3 argues for broader institutional reforms."
#         - "Page 18: The authors critique existing enforcement models."</Q5>
#         <Q6>Yes</Q6>
#         <Q7>They propose a federal standard applicable to emerging markets.</Q7>
#         <Q8>- "Page 24: Comparative analysis across EU and US systems."</Q8>
#         <Q9>No</Q9>
#         <Q10>Stakeholders are portrayed as mission-driven rather than utility driven.</Q10>
#         <Q11>- "Page 30: Interviews highlight collaborative motivations."</Q11>
#         <Q12>Yes</Q12>
#         <Q13>The framework emphasises stewardship and shared governance.</Q13>
#         <Q14>- "Page 34: Case study on community-led compliance."</Q14>
#         <Q15>Type 3</Q15>
#         <Q16>3 - Medium</Q16>
#         </END_4PT_RESPONSE>
#         """
#     ).strip()

#     parsed = parse_ai_response(sample_response)

#     assert len(parsed) == 16, f"Expected 16 answers, got {len(parsed)}"
#     assert parsed[1] == "Yes", "Q1 should be normalised to 'Yes'"
#     assert "Page 12" in parsed[5] and "Page 18" in parsed[5], "Q5 should retain multi-line citations"
#     assert parsed[15] == "Type 3", "Q15 should preserve type formatting"
#     assert parsed[16] == "3 - Medium", "Q16 should keep difficulty label"

#     print("✅ parse_ai_response self-test passed (structured template parsing)")


def get_timestamp():
    """生成时间戳，格式为yymmddhhmmss"""
    return datetime.now().strftime('%y%m%d%H%M%S')


def find_pdf_file(article_id, pdf_folder):
    """根据文章ID查找对应的PDF文件"""
    pdf_path = os.path.join(pdf_folder, f"{article_id}.pdf")
    if os.path.exists(pdf_path):
        return pdf_path
    return None


def get_column_mapping(df_columns):
    """根据Excel列名中的[Q]标注获取列名映射"""
    column_mapping = {}
    
    for col in df_columns:
        # 查找[Q数字]模式
        match = re.search(r'\[Q(\d+)\]', col)
        if match:
            q_num = int(match.group(1))
            column_mapping[q_num] = col
    
    return column_mapping


def process_batch_analysis():
    """批量处理Excel中的所有文章"""
    
    # 读取Excel
    print(f"Reading Excel from: {EXCEL_PATH}")
    df_human = pd.read_excel(EXCEL_PATH)
    print(f"Found {len(df_human)} articles to process")
    
    # 获取列名映射（基于[Q]标注）
    column_mapping = get_column_mapping(df_human.columns)
    print(f"Found {len(column_mapping)} question mappings")
    print("Question mappings found:")
    for q_num in sorted(column_mapping.keys()):
        col_name = column_mapping[q_num]
        print(f"  Q{q_num}: {col_name[:50]}...")
    
    # 加载codebook pages（用于分析）
    cb_pages = read_markdown(CODEBOOK_MD)
    print(f"Codebook sections loaded: {len(cb_pages)}")
    
    # 准备结果列表（每篇文章会有两行：human和AI）
    results = []
    
    # 统计信息
    success_count = 0
    pdf_not_found_count = 0
    pdf_error_count = 0
    analysis_error_count = 0
    
    # 处理每篇文章
    for idx, row in df_human.iterrows():
        article_id = row['#']
        title = row.get('Title of the Paper', 'Unknown')
        
        print(f"\n[{idx+1}/{len(df_human)}] Processing article #{article_id}: {title[:50]}...")
        
        # Step 1: 添加human结果行（保持所有原始列）
        human_row = row.to_dict()
        human_row['source'] = 'human'  # 标记为human结果
        human_row['Analysis_Status'] = 'HUMAN_ORIGINAL'  # 标记状态
        results.append(human_row)
        print(f"  ✓ Added human result row")
        
        # Step 2: 准备AI分析
        # 查找PDF文件
        pdf_path = find_pdf_file(article_id, PDF_FOLDER)
        
        if not pdf_path:
            print(f"  ⚠️ PDF not found for article #{article_id}")
            pdf_not_found_count += 1
            # 为每个预期的运行创建失败行
            for run_idx in range(AI_RUNS):
                ai_row = row.to_dict()  # 从human行复制基本信息
                run_source_id = f"{BASE_AI_SOURCE_ID}-run{run_idx+1}" if AI_RUNS > 1 else BASE_AI_SOURCE_ID
                ai_row['source'] = run_source_id
                ai_row['Analysis_Status'] = f'PDF_NOT_FOUND_{get_timestamp()}'
                # 清空所有问题的答案（保留元数据）
                for q_num in column_mapping.keys():
                    ai_row[column_mapping[q_num]] = ''
                # 清空Analysis result列
                if 'Analysis result (based on column U and X)' in ai_row:
                    ai_row['Analysis result (based on column U and X)'] = ''
                if 'Analysis result (based on column AB and AE)' in ai_row:
                    ai_row['Analysis result (based on column AB and AE)'] = ''
                results.append(ai_row)
            print(f"  ✓ Added {AI_RUNS} AI result rows (PDF not found)")
            continue
        
        print(f"  📄 Found PDF: {os.path.basename(pdf_path)}")
        
        # 读取PDF
        article_pages = read_pdf(pdf_path)
        if not article_pages:
            print(f"  ⚠️ Failed to read PDF")
            pdf_error_count += 1
            # 为每个预期的运行创建失败行
            for run_idx in range(AI_RUNS):
                ai_row = row.to_dict()  # 从human行复制基本信息
                run_source_id = f"{BASE_AI_SOURCE_ID}-run{run_idx+1}" if AI_RUNS > 1 else BASE_AI_SOURCE_ID
                ai_row['source'] = run_source_id
                ai_row['Analysis_Status'] = f'PDF_READ_ERROR_{get_timestamp()}'
                # 清空所有问题的答案
                for q_num in column_mapping.keys():
                    ai_row[column_mapping[q_num]] = ''
                # 清空Analysis result列
                if 'Analysis result (based on column U and X)' in ai_row:
                    ai_row['Analysis result (based on column U and X)'] = ''
                if 'Analysis result (based on column AB and AE)' in ai_row:
                    ai_row['Analysis result (based on column AB and AE)'] = ''
                results.append(ai_row)
            print(f"  ✓ Added {AI_RUNS} AI result rows (PDF read error)")
            continue
        
        print(f"  📖 PDF loaded: {len(article_pages)} pages, {sum(len(p['text']) for p in article_pages)} chars")
        
        # AI分析
        print(f"  🤖 Running AI analysis...")
        ai_answer_sets = analyze_article_fourpt_multiple(article_pages, cb_pages)
        
        if not ai_answer_sets:
            print(f"  ⚠️ All AI analysis runs failed")
            analysis_error_count += 1
            # 为每个预期的运行创建失败行
            for run_idx in range(AI_RUNS):
                ai_row = row.to_dict()  # 从human行复制基本信息
                run_source_id = f"{BASE_AI_SOURCE_ID}-run{run_idx+1}" if AI_RUNS > 1 else BASE_AI_SOURCE_ID
                ai_row['source'] = run_source_id
                ai_row['Analysis_Status'] = f'ANALYSIS_ERROR_{get_timestamp()}'
                # 清空所有问题的答案
                for q_num in column_mapping.keys():
                    ai_row[column_mapping[q_num]] = ''
                # 清空Analysis result列
                if 'Analysis result (based on column U and X)' in ai_row:
                    ai_row['Analysis result (based on column U and X)'] = ''
                if 'Analysis result (based on column AB and AE)' in ai_row:
                    ai_row['Analysis result (based on column AB and AE)'] = ''
                results.append(ai_row)
            print(f"  ✓ Added {AI_RUNS} AI result rows (with error status)")
            continue
        
        # 处理每次AI运行的结果
        ai_success_count = 0
        for run_idx, (ai_answers, api_timestamp) in enumerate(ai_answer_sets):
            run_source_id = f"{BASE_AI_SOURCE_ID}-run{run_idx+1}" if AI_RUNS > 1 else BASE_AI_SOURCE_ID
            
            # 构建AI结果行 - 从human行复制基本信息
            ai_row = row.to_dict()  # 从human行复制所有基本信息
            ai_row['source'] = run_source_id
            
            if ai_answers is None:
                # 这次运行失败 - 使用API调用时的时间戳
                ai_row['Analysis_Status'] = f'ANALYSIS_ERROR_{api_timestamp}'
                # 清空所有问题的答案
                for q_num in column_mapping.keys():
                    ai_row[column_mapping[q_num]] = ''
                # 清空Analysis result列
                if 'Analysis result (based on column U and X)' in ai_row:
                    ai_row['Analysis result (based on column U and X)'] = ''
                if 'Analysis result (based on column AB and AE)' in ai_row:
                    ai_row['Analysis result (based on column AB and AE)'] = ''
                print(f"    ⚠️ Run {run_idx+1} failed")
            else:
                # 这次运行成功 - 使用API调用时的时间戳
                ai_row['Analysis_Status'] = f'SUCCESS_{api_timestamp}'
                ai_success_count += 1
                
                # 清空原有的human答案
                for q_num in column_mapping.keys():
                    ai_row[column_mapping[q_num]] = ''
                # 清空Analysis result列
                if 'Analysis result (based on column U and X)' in ai_row:
                    ai_row['Analysis result (based on column U and X)'] = ''
                if 'Analysis result (based on column AB and AE)' in ai_row:
                    ai_row['Analysis result (based on column AB and AE)'] = ''
                if 'Problem type of the article (Type 1, 2, 3, and 4 autopopulated based on response to column U and AB)' in ai_row:
                    ai_row['Problem type of the article (Type 1, 2, 3, and 4 autopopulated based on response to column U and AB)'] = ''
                
                # 填充AI的答案
                for q_num, col_name in column_mapping.items():
                    if q_num in ai_answers:
                        answer = ai_answers[q_num]
                        
                        # 特殊格式处理
                        if q_num == 15:  # 4PT Type分类
                            # 统一格式为 "Type X"
                            answer = answer.upper()
                            if "TYPE" not in answer:
                                if "T1" in answer:
                                    answer = "Type 1"
                                elif "T2" in answer:
                                    answer = "Type 2"
                                elif "T3" in answer:
                                    answer = "Type 3"
                                elif "T4" in answer:
                                    answer = "Type 4"
                                else:
                                    # 尝试提取数字
                                    match = re.search(r'[1-4]', answer)
                                    if match:
                                        answer = f"Type {match.group()}"
                            else:
                                # 确保格式为 "Type X" 而不是 "TypeX"
                                answer = re.sub(r'Type\s*(\d)', r'Type \1', answer)
                            ai_row[col_name] = answer
                            
                        elif q_num == 16:  # 难度等级
                            answer_lower = answer.lower()
                            if "very easy" in answer_lower:
                                ai_row[col_name] = "1 - Very Easy"
                            elif "easy" in answer_lower and "very" not in answer_lower:
                                ai_row[col_name] = "2 - Easy"
                            elif "medium" in answer_lower:
                                ai_row[col_name] = "3 - Medium"
                            elif "hard" in answer_lower and "very" not in answer_lower:
                                ai_row[col_name] = "4 - Hard"
                            elif "very hard" in answer_lower:
                                ai_row[col_name] = "5 - Very Hard"
                            else:
                                # 尝试提取数字
                                match = re.search(r'[1-5]', answer)
                                if match:
                                    num = match.group()
                                    difficulty_map = {
                                        '1': '1 - Very Easy',
                                        '2': '2 - Easy', 
                                        '3': '3 - Medium',
                                        '4': '4 - Hard',
                                        '5': '5 - Very Hard'
                                    }
                                    ai_row[col_name] = difficulty_map.get(num, answer)
                                else:
                                    ai_row[col_name] = answer
                        else:
                            ai_row[col_name] = answer
                    else:
                        # 如果AI没有回答这个问题，留空
                        ai_row[col_name] = ''
                
                print(f"    ✅ Run {run_idx+1} completed successfully")
                
                # 打印关键结果用于验证（只对第一次成功运行打印）
                if ai_success_count == 1:
                    if 15 in column_mapping and column_mapping[15] in ai_row:
                        print(f"      🎯 AI Classification: {ai_row[column_mapping[15]]}")
                    if 1 in column_mapping and column_mapping[1] in ai_row:
                        print(f"      📌 Sustainability fit: {ai_row[column_mapping[1]]}")
            
            results.append(ai_row)
        
        if ai_success_count > 0:
            success_count += 1
        else:
            analysis_error_count += 1
            
        print(f"  ✓ Added {len(ai_answer_sets)} AI result rows ({ai_success_count} successful)")
    
    # 创建结果DataFrame
    df_results = pd.DataFrame(results)
    
    # 验证结果
    print("\n" + "=" * 60)
    print("RESULTS VALIDATION")
    print("=" * 60)
    print(f"Total rows in results: {len(df_results)}")
    print(f"Expected rows: {len(df_human) * (1 + AI_RUNS)} (human + {AI_RUNS} AI runs for each article)")
    
    # 检查source列的分布
    if 'source' in df_results.columns:
        source_counts = df_results['source'].value_counts()
        print("\nSource distribution:")
        print(source_counts)
    
    # 调整列顺序，确保与原Excel一致
    original_cols = list(df_human.columns)
    # source和Analysis_Status列放在最前面，便于识别
    new_cols = ['#', 'source', 'Analysis_Status'] + [col for col in original_cols if col != '#']
    
    # 确保所有列都存在
    for col in new_cols:
        if col not in df_results.columns:
            df_results[col] = ''
    
    # 重新排序，只包含存在的列
    final_cols = [col for col in new_cols if col in df_results.columns]
    df_results = df_results[final_cols]
    
    # 按文章ID和source排序，确保human和AI结果相邻
    df_results = df_results.sort_values(['#', 'source'], ascending=[True, False])  # human在前，ai在后
    df_results = df_results.reset_index(drop=True)
    
    # 保存结果
    df_results.to_excel(OUTPUT_EXCEL, index=False)
    print(f"\n📊 Results saved to: {OUTPUT_EXCEL}")
    
    # 验证保存的文件
    try:
        df_verify = pd.read_excel(OUTPUT_EXCEL)
        print(f"✅ File saved successfully with {len(df_verify)} rows")
        if 'source' in df_verify.columns:
            source_counts = df_verify['source'].value_counts().to_dict()
            human_rows = source_counts.get('human', 0)
            ai_rows = sum(count for source, count in source_counts.items() if source != 'human')
            print(f"   - Human rows: {human_rows}")
            print(f"   - AI rows: {ai_rows}")
    except Exception as e:
        print(f"⚠️ Could not verify saved file: {e}")
    
    # 打印统计信息
    print("\n" + "=" * 60)
    print("ANALYSIS SUMMARY")
    print("=" * 60)
    print(f"Total articles processed: {len(df_human)}")
    print(f"✅ Successful analyses: {success_count}")
    print(f"⚠️ PDF not found: {pdf_not_found_count}")
    print(f"⚠️ PDF read errors: {pdf_error_count}")
    print(f"⚠️ Analysis errors: {analysis_error_count}")
    
    # 显示对比示例
    if success_count > 0:
        print("\n" + "=" * 60)
        print("SAMPLE COMPARISON (First successful article)")
        print("=" * 60)
        
        # 找到第一个成功的文章ID
        first_success_ai = df_results[(df_results['source'] != 'human') & 
                                      (df_results['Analysis_Status'].str.startswith('SUCCESS'))].iloc[0]
        article_id = first_success_ai['#']
        
        # 获取human和AI的配对结果
        human_result = df_results[(df_results['#'] == article_id) & 
                                 (df_results['source'] == 'human')].iloc[0]
        ai_result = df_results[(df_results['#'] == article_id) & 
                              (df_results['source'] != 'human') &
                              (df_results['Analysis_Status'].str.startswith('SUCCESS'))].iloc[0]
        
        print(f"\nArticle #{article_id}: {human_result['Title of the Paper'][:60]}...")
        
        # 显示关键问题的对比
        comparison_questions = {
            1: "Sustainability fit",
            3: "On-ground problem",
            6: "Beyond on-ground",
            9: "Utility focus",
            12: "Beyond self-interest",
            15: "Final Classification",
            16: "Difficulty"
        }
        
        for q_num, q_desc in comparison_questions.items():
            if q_num in column_mapping:
                col_name = column_mapping[q_num]
                human_ans = human_result.get(col_name, 'N/A')
                ai_ans = ai_result.get(col_name, 'N/A')
                
                # 只显示非空的对比
                if human_ans or ai_ans:
                    print(f"\nQ{q_num} - {q_desc}:")
                    print(f"  Human: {human_ans[:100] if human_ans else 'N/A'}")
                    print(f"  AI:    {ai_ans[:100] if ai_ans else 'N/A'}")
                    
                    # 对于Yes/No问题，标记是否一致
                    if q_num in [1, 3, 6, 9, 12]:
                        if human_ans and ai_ans and human_ans != 'N/A' and ai_ans != 'N/A':
                            match = "✅ Match" if human_ans.lower() == ai_ans.lower() else "❌ Differ"
                            print(f"  {match}")
    
    # 显示结果DataFrame的前几行验证
    print("\n" + "=" * 60)
    rows_per_article = 1 + AI_RUNS
    print(f"FIRST {rows_per_article * 2} ROWS OF RESULTS (2 articles × {rows_per_article} rows each)")
    print("=" * 60)
    display_cols = ['#', 'source', 'Analysis_Status', 'Title of the Paper']
    # 添加Q15（最终分类）如果存在
    if 15 in column_mapping:
        display_cols.append(column_mapping[15])
    
    print(df_results[display_cols].head(rows_per_article * 2).to_string(max_colwidth=40))
    
    return df_results


# === 主程序 ===
if __name__ == '__main__':
    print("=" * 60)
    print("4PT BATCH ANALYSIS PIPELINE")
    print("=" * 60)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Output directory: {OUTPUT_DIR}")

    # if os.getenv("FOURPT_SELF_TEST") == "1":
    #     _self_test_parse_ai_response()
    
    # 运行批处理
    results_df = process_batch_analysis()
    
    # 最终验证
    if results_df is not None and not results_df.empty:
        print("\n" + "=" * 60)
        print("FINAL VERIFICATION")
        print("=" * 60)
        
        # 验证每篇文章都有human和AI两行
        article_ids = results_df['#'].unique()
        print(f"Unique articles: {len(article_ids)}")
        
        for article_id in article_ids[:3]:  # 检查前3篇文章
            article_rows = results_df[results_df['#'] == article_id]
            sources = article_rows['source'].tolist()
            print(f"Article #{article_id}: {sources}")
            if 'human' not in sources:
                print(f"  ⚠️ WARNING: Missing human row for article #{article_id}")
            ai_sources = [s for s in sources if s != 'human']
            if len(ai_sources) != AI_RUNS:
                print(f"  ⚠️ WARNING: Expected {AI_RUNS} AI rows, found {len(ai_sources)} for article #{article_id}")
    
    print(f"\nEnd time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print("PIPELINE COMPLETED")
    print("=" * 60)
    