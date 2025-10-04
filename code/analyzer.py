"""
4PT分析器模块 - 核心分析功能
"""
from typing import List, Dict, Optional
import pandas as pd
from openai import OpenAI

from config import Config


class FourPTAnalyzer:
    """4PT框架分析器"""
    
    # 4PT分析问题模板
    QUESTIONS = """
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

15. Based on your analysis above, what is your final 4PT Type classification? (T1, T2, T3, or T4)

16. What is the difficulty level of this classification? (easy, medium, or hard)

Please answer each question clearly and provide specific evidence from the text when requested.
"""
    
    def __init__(self, api_key: Optional[str] = None, model: str = None):
        """
        初始化分析器
        
        Args:
            api_key: OpenAI API密钥，如果不提供则从配置中获取
            model: 使用的模型名称，如果不提供则使用默认模型
        """
        self.api_key = api_key or Config.OPENAI_API_KEY
        self.model = model or Config.CLS_MODEL
        self.client = OpenAI(api_key=self.api_key)
    
    def analyze_article(self, article_pages: List[Dict], codebook_pages: List[Dict]) -> Optional[Dict]:
        """
        使用4PT框架分析文章
        
        Args:
            article_pages: 文章页面列表
            codebook_pages: 编码手册页面列表
            
        Returns:
            分析结果字典，包含分析文本和元数据
        """
        # 合并页面内容为文本
        article_text = self._merge_pages(article_pages, "Page")
        codebook_text = self._merge_pages(codebook_pages, "Section")
        
        # 构建分析提示
        prompt = self._build_prompt(codebook_text, article_text)
        
        try:
            # 调用OpenAI API
            analysis_text = self._call_openai_api(prompt)
            
            # 构建结果
            result = {
                "analysis_text": analysis_text,
                "analysis_metadata": {
                    "model": self.model,
                    "timestamp": pd.Timestamp.now().isoformat(),
                    "prompt_length": len(prompt),
                    "response_length": len(analysis_text)
                }
            }
            
            return result
            
        except Exception as e:
            print(f"Error in analysis: {e}")
            return None
    
    def _merge_pages(self, pages: List[Dict], prefix: str) -> str:
        """合并页面内容为单个文本"""
        return "\n\n".join([f"{prefix} {p['page']}:\n{p['text']}" for p in pages])
    
    def _build_prompt(self, codebook_text: str, article_text: str) -> str:
        """构建分析提示"""
        return f"""
You are an expert public policy analyst reviewing sustainability research articles. 

**Instructions:**
- Answer ALL questions only based on the provided Codebook and Article
- Provide specific citations when requested
- Keep justifications concise and evidence-based
- For Yes/No questions, choose definitively based on evidence

**4PT Codebook:**
{codebook_text}

**Article to Analyze:**
{article_text}

{self.QUESTIONS}
""".strip()
    
    def _call_openai_api(self, prompt: str) -> str:
        """调用OpenAI API获取分析结果"""
        try:
            # 尝试使用新的 responses API
            response = self.client.responses.create(
                model=self.model,
                input=prompt,
                reasoning={"effort": "high"},
                text={"verbosity": "medium"},
            )
            return response.output_text
        except AttributeError:
            # 如果新API不存在，使用标准的chat completions API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2000,
                temperature=0.1
            )
            return response.choices[0].message.content