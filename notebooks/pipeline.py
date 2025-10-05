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
EXCEL_PATH = "/Users/xinby/Desktop/AI44PT_Desktop/data/processed/JRGsamples/JRG article sublist.xlsx"
# EXCEL_PATH = "/Users/xinby/Desktop/AI44PT_Desktop/data/processed/JRGsamples/2sample.xlsx"
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

# Majority Vote 配置
ENABLE_MAJORITY_VOTE = True  # 是否启用多数投票功能
OBJECTIVE_QUESTIONS = [1, 3, 6, 9, 12, 15, 16]  # 客观题编号（Yes/No问题和分类问题）
SUBJECTIVE_QUESTIONS = [2, 4, 5, 7, 8, 10, 11, 13, 14]  # 主观题编号（忽略投票）

# 构建基础source标识（包含模型和参数信息）
BASE_AI_SOURCE_ID = f"{CLS_MODEL}-temp{TEMPERATURE}-reasoning_{REASONING_EFFORT}-verbosity_{TEXT_VERBOSITY}"

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

    # 如果结构化解析不完整，标记为格式错误
    if len(answers) < 16:
        print(f"    ⚠️ AI response format error: Only parsed {len(answers)}/16 questions from structured template")
        # 返回空结果，表示解析失败
        return {}
    
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


def calculate_decision_tree_4pt(row, column_mapping):
    """
    根据决策树逻辑计算4PT类型
    
    决策树逻辑:
    - Q3=Yes, Q9=Yes -> Type 1
    - Q3=Yes, Q9=No -> Type 4
    - Q3=No, Q9=Yes -> Type 2
    - Q3=No, Q9=No -> Type 3
    - 其他情况 -> 空字符串
    
    Args:
        row: DataFrame行数据
        column_mapping: 问题编号到列名的映射
    
    Returns:
        str: 计算出的4PT类型
    """
    # 获取Q3和Q9的列名
    q3_col = column_mapping.get(3)
    q9_col = column_mapping.get(9)
    
    if not q3_col or not q9_col:
        return ''
    
    # 获取Q3和Q9的答案
    q3_answer = str(row.get(q3_col, '')).strip().lower()
    q9_answer = str(row.get(q9_col, '')).strip().lower()
    
    # 标准化答案
    q3_yes = 'yes' in q3_answer
    q3_no = 'no' in q3_answer
    q9_yes = 'yes' in q9_answer
    q9_no = 'no' in q9_answer
    
    # 应用决策树逻辑
    if q3_yes and q9_yes:
        return 'Type 1'
    elif q3_yes and q9_no:
        return 'Type 4'
    elif q3_no and q9_yes:
        return 'Type 2'
    elif q3_no and q9_no:
        return 'Type 3'
    else:
        return ''  # 无法确定或答案不明确


def perform_majority_vote(ai_results_list, column_mapping):
    """
    对多次AI运行结果进行多数投票
    
    Args:
        ai_results_list: AI结果列表，每个元素是(answers_dict, timestamp)的元组
        column_mapping: 问题编号到列名的映射
    
    Returns:
        dict: 投票结果字典，包含每个问题的多数投票答案
    """
    if not ai_results_list or len(ai_results_list) < 2:
        return {}
    
    # 只考虑成功的AI结果
    successful_results = [answers for answers, _ in ai_results_list if answers is not None]
    
    if len(successful_results) < 2:
        return {}
    
    majority_answers = {}
    vote_details = {}  # 记录投票详情，用于调试
    
    # 对每个客观问题进行投票
    for q_num in OBJECTIVE_QUESTIONS:
        if q_num not in column_mapping:
            continue
            
        # 收集所有AI对这个问题的答案
        answers_for_question = []
        for ai_answers in successful_results:
            if q_num in ai_answers and ai_answers[q_num]:
                answer = ai_answers[q_num].strip()
                if answer:  # 只考虑非空答案
                    answers_for_question.append(answer)
        
        if not answers_for_question:
            continue
        
        # 对答案进行标准化处理（特别是Yes/No问题）
        normalized_answers = []
        for answer in answers_for_question:
            if q_num in [1, 3, 6, 9, 12]:  # Yes/No问题
                answer_lower = answer.lower()
                if 'yes' in answer_lower:
                    normalized_answers.append('Yes')
                elif 'no' in answer_lower:
                    normalized_answers.append('No')
                else:
                    normalized_answers.append(answer)  # 保持原答案
            elif q_num == 15:  # 4PT分类问题
                # 标准化Type格式
                answer_upper = answer.upper()
                if 'TYPE' in answer_upper:
                    # 提取Type X格式
                    match = re.search(r'TYPE\s*([1-4])', answer_upper)
                    if match:
                        normalized_answers.append(f'Type {match.group(1)}')
                    else:
                        normalized_answers.append(answer)
                else:
                    # 尝试提取数字
                    match = re.search(r'[1-4]', answer)
                    if match:
                        normalized_answers.append(f'Type {match.group()}')
                    else:
                        normalized_answers.append(answer)
            elif q_num == 16:  # 难度等级问题
                # 标准化难度格式
                answer_lower = answer.lower()
                if "very easy" in answer_lower:
                    normalized_answers.append("1 - Very Easy")
                elif "easy" in answer_lower and "very" not in answer_lower:
                    normalized_answers.append("2 - Easy")
                elif "medium" in answer_lower:
                    normalized_answers.append("3 - Medium")
                elif "hard" in answer_lower and "very" not in answer_lower:
                    normalized_answers.append("4 - Hard")
                elif "very hard" in answer_lower:
                    normalized_answers.append("5 - Very Hard")
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
                        normalized_answers.append(difficulty_map.get(num, answer))
                    else:
                        normalized_answers.append(answer)
            else:
                normalized_answers.append(answer)
        
        if not normalized_answers:
            continue
        
        # 统计答案频次
        from collections import Counter
        answer_counts = Counter(normalized_answers)
        vote_details[q_num] = {
            'original_answers': answers_for_question,
            'normalized_answers': normalized_answers,
            'vote_counts': dict(answer_counts)
        }
        
        # 选择多数投票结果
        most_common = answer_counts.most_common()
        if most_common:
            winner_answer, winner_count = most_common[0]
            
            # 检查是否有平票情况
            if len(most_common) > 1 and most_common[0][1] == most_common[1][1]:
                # 平票情况，选择第一个（或者可以实现其他平票处理策略）
                majority_answers[q_num] = f"{winner_answer} [TIE]"
            else:
                majority_answers[q_num] = winner_answer
    
    return majority_answers, vote_details


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
        
        # 添加Majority Vote结果行（如果启用且有多次成功运行）
        if ENABLE_MAJORITY_VOTE and AI_RUNS > 1 and ai_success_count >= 2:
            print(f"  🗳️ Performing majority vote on {ai_success_count} successful runs...")
            majority_results, vote_details = perform_majority_vote(ai_answer_sets, column_mapping)
            
            if majority_results:
                # 创建majority vote行
                majority_row = row.to_dict()  # 从human行复制基本信息
                majority_source_id = f"{BASE_AI_SOURCE_ID}-majority-vote"
                majority_row['source'] = majority_source_id
                majority_row['Analysis_Status'] = f'MAJORITY_VOTE_{get_timestamp()}'
                
                # 清空所有问题的答案
                for q_num in column_mapping.keys():
                    majority_row[column_mapping[q_num]] = ''
                # 清空Analysis result列
                if 'Analysis result (based on column U and X)' in majority_row:
                    majority_row['Analysis result (based on column U and X)'] = ''
                if 'Analysis result (based on column AB and AE)' in majority_row:
                    majority_row['Analysis result (based on column AB and AE)'] = ''
                if 'Problem type of the article (Type 1, 2, 3, and 4 autopopulated based on response to column U and AB)' in majority_row:
                    majority_row['Problem type of the article (Type 1, 2, 3, and 4 autopopulated based on response to column U and AB)'] = ''
                
                # 填充majority vote结果（只填充客观题）
                for q_num, answer in majority_results.items():
                    if q_num in column_mapping:
                        majority_row[column_mapping[q_num]] = answer
                
                # 主观题保持为空，但可以添加一个说明
                for q_num in SUBJECTIVE_QUESTIONS:
                    if q_num in column_mapping:
                        majority_row[column_mapping[q_num]] = '[SUBJECTIVE - NO VOTE]'
                
                results.append(majority_row)
                
                # 打印投票结果摘要
                print(f"    ✅ Majority vote completed")
                for q_num, answer in majority_results.items():
                    if q_num in [1, 3, 6, 9, 12, 15, 16]:  # 只打印关键问题
                        vote_count_info = vote_details.get(q_num, {}).get('vote_counts', {})
                        print(f"      Q{q_num}: {answer} (votes: {vote_count_info})")
        
        if ai_success_count > 0:
            success_count += 1
        else:
            analysis_error_count += 1
            
        total_rows_added = len(ai_answer_sets)
        if ENABLE_MAJORITY_VOTE and AI_RUNS > 1 and ai_success_count >= 2:
            total_rows_added += 1  # 加上majority vote行
            
        print(f"  ✓ Added {total_rows_added} AI result rows ({ai_success_count} successful + {'1 majority vote' if ENABLE_MAJORITY_VOTE and AI_RUNS > 1 and ai_success_count >= 2 else '0 majority vote'})")
    
    # 创建结果DataFrame
    df_results = pd.DataFrame(results)
    
    # 添加Decision Tree 4PT列
    print("\n🌳 Calculating Decision Tree 4PT classifications...")
    decision_tree_col = 'Decision Tree 4PT'
    df_results[decision_tree_col] = df_results.apply(
        lambda row: calculate_decision_tree_4pt(row, column_mapping), axis=1
    )
    
    # 统计Decision Tree结果
    decision_tree_counts = df_results[decision_tree_col].value_counts(dropna=False)
    print(f"Decision Tree 4PT distribution:")
    for dt_type, count in decision_tree_counts.items():
        print(f"  {dt_type if dt_type else '[Empty]'}: {count}")
    
    # 验证结果
    print("\n" + "=" * 60)
    print("RESULTS VALIDATION")
    print("=" * 60)
    print(f"Total rows in results: {len(df_results)}")
    
    # 计算期望行数
    expected_rows_per_article = 1 + AI_RUNS  # human + AI runs
    if ENABLE_MAJORITY_VOTE and AI_RUNS > 1:
        # 对于有足够成功AI运行的文章，会额外增加一行majority vote
        # 这里我们假设大部分文章都会有majority vote行，实际数量可能略少
        expected_rows_per_article += 1
    
    expected_total_rows = len(df_human) * expected_rows_per_article
    print(f"Expected rows (approx): {expected_total_rows} (human + {AI_RUNS} AI runs" + 
          (f" + majority vote" if ENABLE_MAJORITY_VOTE and AI_RUNS > 1 else "") + " for each article)")
    
    # 检查source列的分布
    if 'source' in df_results.columns:
        source_counts = df_results['source'].value_counts()
        print("\nSource distribution:")
        print(source_counts)
    
    # 调整列顺序，确保与原Excel一致，并将Decision Tree 4PT放在Q15旁边
    original_cols = list(df_human.columns)
    # source和Analysis_Status列放在最前面，便于识别
    base_cols = ['#', 'source', 'Analysis_Status']
    
    # 找到Q15列的位置，将Decision Tree 4PT列插入到其后
    q15_col = column_mapping.get(15) if column_mapping else None
    
    if q15_col and q15_col in original_cols:
        # 找到Q15列在原始列中的位置
        q15_index = original_cols.index(q15_col)
        # 构建新的列顺序：base_cols + 原始列（到Q15） + Decision Tree 4PT + 原始列（Q15之后）
        new_cols = (base_cols + 
                   [col for col in original_cols[:q15_index+1] if col not in base_cols] +
                   [decision_tree_col] +
                   [col for col in original_cols[q15_index+1:] if col not in base_cols])
    else:
        # 如果没有找到Q15列，就放在最后
        new_cols = base_cols + [col for col in original_cols if col not in base_cols] + [decision_tree_col]
    
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
            15: "AI Classification",
            16: "Difficulty"
        }
        
        # 添加Decision Tree 4PT的对比
        decision_tree_comparison = True
        
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
        
        # 显示Decision Tree 4PT对比
        if decision_tree_col in human_result.index and decision_tree_col in ai_result.index:
            human_dt = human_result.get(decision_tree_col, 'N/A')
            ai_dt = ai_result.get(decision_tree_col, 'N/A')
            print(f"\nDecision Tree 4PT:")
            print(f"  Human: {human_dt}")
            print(f"  AI:    {ai_dt}")
            if human_dt and ai_dt and human_dt != 'N/A' and ai_dt != 'N/A':
                match = "✅ Match" if human_dt == ai_dt else "❌ Differ"
                print(f"  {match}")
    
    # 显示结果DataFrame的前几行验证
    print("\n" + "=" * 60)
    rows_per_article = 1 + AI_RUNS
    if ENABLE_MAJORITY_VOTE and AI_RUNS > 1:
        rows_per_article += 1  # 加上majority vote行
    print(f"FIRST {rows_per_article * 2} ROWS OF RESULTS (2 articles × {rows_per_article} rows each)")
    print("=" * 60)
    display_cols = ['#', 'source', 'Analysis_Status', 'Title of the Paper']
    # 添加Q15（AI最终分类）和Decision Tree 4PT如果存在
    if 15 in column_mapping:
        display_cols.append(column_mapping[15])
    if decision_tree_col in df_results.columns:
        display_cols.append(decision_tree_col)
    
    print(df_results[display_cols].head(rows_per_article * 2).to_string(max_colwidth=40))
    
    # 如果启用了majority vote，显示一些统计信息
    if ENABLE_MAJORITY_VOTE and AI_RUNS > 1:
        majority_vote_rows = df_results[df_results['source'].str.contains('majority-vote', na=False)]
        print(f"\n📊 Majority Vote Summary:")
        print(f"   - Total majority vote rows: {len(majority_vote_rows)}")
        if len(majority_vote_rows) > 0:
            print(f"   - Articles with majority vote: {majority_vote_rows['#'].nunique()}")
            
            # 显示第一个majority vote结果示例
            if len(majority_vote_rows) > 0:
                first_majority = majority_vote_rows.iloc[0]
                article_id = first_majority['#']
                print(f"\n   Example (Article #{article_id}):")
                for q_num in [1, 3, 6, 9, 12, 15, 16]:
                    if q_num in column_mapping:
                        col_name = column_mapping[q_num]
                        answer = first_majority.get(col_name, 'N/A')
                        if answer and answer != '[SUBJECTIVE - NO VOTE]':
                            tie_marker = " [TIE DETECTED]" if "[TIE]" in str(answer) else ""
                            print(f"     Q{q_num}: {answer}{tie_marker}")
    
    print("\n" + "=" * 60)
    print("MAJORITY VOTE CONFIGURATION")
    print("=" * 60)
    print(f"Majority Vote Enabled: {ENABLE_MAJORITY_VOTE}")
    print(f"Objective Questions (voted): {OBJECTIVE_QUESTIONS}")
    print(f"Subjective Questions (ignored): {SUBJECTIVE_QUESTIONS}")
    print(f"AI Runs per Article: {AI_RUNS}")
    print(f"Minimum Successful Runs for Voting: 2")
    
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
            if len(ai_sources) != AI_RUNS and not (ENABLE_MAJORITY_VOTE and AI_RUNS > 1 and len(ai_sources) == AI_RUNS + 1):
                print(f"  ⚠️ WARNING: Expected {AI_RUNS} AI rows, found {len(ai_sources)} for article #{article_id}")
    
    print(f"\nEnd time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print("PIPELINE COMPLETED")
    print("=" * 60)
    