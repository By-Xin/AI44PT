from typing import List, Dict

# 结构化响应模板
STRUCTURED_RESPONSE_TEMPLATE = """
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
<Q17>[Answer here]</Q17>
<Q18>[Answer here]</Q18>
<Q19>[Answer here]</Q19>
<Q20>[Answer here]</Q20>
<Q21>[Answer here]</Q21>
<Q22>[Answer here]</Q22>
<Q23>[Answer here]</Q23>
<Q24>[Answer here]</Q24>
<Q25>[Answer here]</Q25>
</END_4PT_RESPONSE>
"""

# 系统提示词 (System Prompt)
SYSTEM_PROMPT = f"""
### Role
You are an expert policy analyst and critical thinker specializing in the "Four Problem Types" (4PT) framework for sustainability governance. 

### Task
Your task is to first read and understand the provided Codebook that details the 4PT framework, and then apply this framework to analyze the provided academic articles to classify them into one of four distinct problem types (or "Uncertain") based on the questions below.

### General Guidelines
- Answer ALL questions based on the provided Codebook and Article. Do NOT use any outside knowledge.
- You must remain objective, critical, and rigorous. Keep justifications concise and evidence-based.
- Do not simply rely on keywords; you must analyze the logic of the argument.
- Strictly adhere to the answer formats specified in each question: For Yes-or-No or multiple choice problems, answer from the given options only. Provide specific citations when requested.
- Format your entire response using the XML template below to ensure each answer stays inside its <Q#> tag. Do not include any text outside the template.
- Evaluate each question independently; do not let question order influence your judgment. 
- If uncertain about a question or you think the paragraph does not fit into the 4PT framework, answer "Uncertain" where applicable and provide a solid rationale. 
- Do NOT guess answers; if the information is not present, state that clearly. Do not use any type as a default fallback. You must justify all classifications with evidence from the text.

{STRUCTURED_RESPONSE_TEMPLATE}
""".strip()

def build_user_prompt(coding_task_text: str, executive_summary_text: str, main_body_text: str, article_text: str) -> str:
    return f"""
### Reference Materials
You have access to the full theoretical texts below. You must read and internalize these definitions before answering the questions. Please pay attention to the four schools of thought as defined, which may help in distinguishing between types.

***DOCUMENT 1: THE CODING TASK***
{coding_task_text}
***DOCUMENT 2: EXECUTIVE SUMMARY***
{executive_summary_text}
***DOCUMENT 3: MAIN BODY & FOUR SCHOOLS***
{main_body_text}

### CRITICAL REMINDERS
Based on previous issues, please carefully adhere to the following instructions when generating your response. Yet please keep in mind that these are examples of common pitfalls, not an exhaustive list. Always refer back to the coding task definitions and for final judgment.

**1. THE "ON-THE-GROUND PROBLEM"**
**"On-the-ground problem" refers to substantive, empirically measurable specific policy problems that are: **Specific**: Points to particular events or phenomena, not abstract concepts, or **Teleological**: Analysis begins and ends with solving this specific problem, not validating a universal theory.
Examples of TRUE "On-the-Ground Problems": - **Specific environmental crises**: Illegal logging in Amazon forests, overfishing of Atlantic cod, toxic chemical discharge in a specific river - **Measurable targets**: Global temperature rise limited to 1.5°C, reducing traffic accident deaths, preventing extinction of a specific species (e.g., spotted owl) - **Concrete access issues**: Access to K-12 education, clean water supply for urban populations
 What "On-the-Ground Problem" does NOT mean:
**✗ Abstract values/concepts:**- "Environmental conservation" - "Equity" - "Human rights" - "Social welfare maximization"- "Stakeholder consensus"- "Legitimacy" 
**✗ Policy/governance mechanisms:**- Ecolabel compliance issues- Regulatory enforcement challenges- Top-down policy effectiveness- Information asymmetries - Certification processes- Institutional fragmentation

**2. THE TYPE 4 "STRICTNESS" FALLACY**
* **The Error:** AI often classifies articles as Type 4 just because they advocate for "strict rules" or "punishment."
* **The Rule:** Strict enforcement of a market rule (e.g., timber legality) is often **Type 1** (Commons/Market rules) or **Type 3** (Rule of Law).
* **True Type 4:** Type 4 is defined by **Lexical Priority**. It argues that a specific outcome (e.g., ecological integrity) is *incommensurable* and must be achieved *regardless* of economic utility or stakeholder consensus.

**3. THE "UTILITY" KEYWORD TRAP**
* **The Error:** Classifying as Type 2 just because the word "utility" or "efficiency" appears.
* **The Rule:** Determine if the author *adopts* utility maximization as their goal (Type 1/2) or *critiques* it. Do not simply rely on keyword presence. Focus on the *role* of utility in their argument. For example, if they CRITIQUE utility maximization as insufficient, it may indicate Type 3 or 4.

### Article to Analyze
{article_text}
"""

def format_questions_prompt(question_order: List[int], question_texts: Dict[int, str], enable_shuffle: bool) -> str:
    """根据指定顺序构建问题提示文本"""
    header_lines = [
        "Please analyze this article using the 4PT framework by answering the questions below.",
    ]
    
    if enable_shuffle:
        header_lines.append("Questions are listed in a randomized order. Treat each independently despite ordering.")
    else:
        header_lines.append("Questions are listed below. Treat each independently.")

    question_lines = [
        f"Q{q_num}. {question_texts[q_num]}"
        for q_num in question_order
    ]

    footer_lines = [
        "Answer each question clearly and provide specific evidence or reasoning when requested."
    ]

    return "\n\n".join(header_lines + question_lines + footer_lines)
