#!/usr/bin/env python3
"""
Core 4PT Analyzer - Focused on Q&A interaction without Excel complexity
"""

import os
import json
import tempfile
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime

import PyMuPDF as fitz
from openai import OpenAI

class Core4PTAnalyzer:
    """Simplified 4PT analyzer focused on Q&A interaction"""
    
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)
        self.model = "gpt-4o"
        self.temperature = 0.1
        
        # Load codebook and questions
        self.codebook = self._load_codebook()
        self.questions = self._load_questions()
        
        # Store current analysis context
        self.current_paper = None
        self.current_analysis = None
        self.paper_content = None
    
    def _load_codebook(self) -> str:
        """Load the 4PT framework codebook"""
        codebook_path = Path(__file__).parent / "code" / "data" / "processed" / "TheCodingTask.md"
        
        # If codebook file doesn't exist, use embedded version
        if not codebook_path.exists():
            return """
# 4PT Framework Codebook

## Four Policy Theory Types:

**Type 1**: Applied problem-solving research focused on specific real-world policy challenges
**Type 2**: Market-oriented approaches emphasizing utility maximization and economic rationality  
**Type 3**: Applied research incorporating broader behavioral and social considerations beyond self-interest
**Type 4**: General theoretical development extending beyond specific policy applications

## Analysis Framework:

The analysis evaluates papers across multiple dimensions including problem focus, theoretical foundations, methodological approaches, and scope of conclusions.
"""
        
        try:
            return codebook_path.read_text(encoding='utf-8')
        except:
            return self._get_fallback_codebook()
    
    def _get_fallback_codebook(self) -> str:
        """Fallback codebook if file loading fails"""
        return """
# 4PT Framework Codebook

## Four Policy Theory Types:

**Type 1**: Applied problem-solving research focused on specific real-world policy challenges
**Type 2**: Market-oriented approaches emphasizing utility maximization and economic rationality  
**Type 3**: Applied research incorporating broader behavioral and social considerations beyond self-interest
**Type 4**: General theoretical development extending beyond specific policy applications
"""
    
    def _load_questions(self) -> Dict[int, str]:
        """Load the 28-question framework"""
        return {
            1: "Does the article fit in the universe of sustainability analyses we seek to assess? (Yes/No)",
            2: "What problems or set of problems is the article trying to address?",
            3: "Do the analysis, conclusions, and theories derive from, and are directed to, understanding and/or managing a clearly specified 'on the ground' problem or class of problems? (Yes/No)",
            4: "Provide arguments that support your response to Q3",
            5: "Provide some key text passages from the article that support your Q3 response",
            6: "Are the analysis, conclusions, and theories generated to apply beyond understanding, and/or managing a clearly specified 'on the ground' problem or class of problems? (Yes/No)",
            7: "Provide arguments that support your response to Q6",
            8: "Provide some key text passages from the article that support your Q6 response",
            9: "Do the analysis, conclusions, and theories treat individuals, organizations and states as largely self-interested, satisfaction driven entities that seek to maximize some kind of 'utility' outcome? (Yes/No)",
            10: "Provide arguments that support your response to Q9",
            11: "Provide some key text passages from the article that support your Q9 response",
            12: "Do the analysis incorporate theories and conclusions incorporate an assessment of individuals, organizations and/or states that extends beyond self-interested satisfaction seeking motivations? (Yes/No)",
            13: "Provide arguments that support your response to Q12",
            14: "Provide some key text passages from the article that support your Q12 response",
            15: "Based on your analysis above, what is your final 4PT Type classification? (Type 1 / Type 2 / Type 3 / Type 4)",
            16: "What is the difficulty level of this classification? (1 - Very Easy / 2 - Easy / 3 - Medium / 4 - Hard / 5 - Very Hard)",
            17: "Based on your analysis, do you think this article should be classified as Type 1? (Yes/No) Why or why not.",
            18: "To what extent does this article align with Type 1? Respond with a score between 0 and 1 (three decimal places) followed by a brief rationale.",
            19: "On a 1-5 Likert scale, how strongly do you agree that this article fits Type 1? Provide the number, the matching label, and a short justification.",
            20: "Based on your analysis, do you think this article should be classified as Type 2? (Yes/No) Why or why not.",
            21: "To what extent does this article align with Type 2? Respond with a score between 0 and 1 (three decimal places) followed by a brief rationale.",
            22: "On a 1-5 Likert scale, how strongly do you agree that this article fits Type 2? Provide the number, the matching label, and a short justification.",
            23: "Based on your analysis, do you think this article should be classified as Type 3? (Yes/No) Why or why not.",
            24: "To what extent does this article align with Type 3? Respond with a score between 0 and 1 (three decimal places) followed by a brief rationale.",
            25: "On a 1-5 Likert scale, how strongly do you agree that this article fits Type 3? Provide the number, the matching label, and a short justification.",
            26: "Based on your analysis, do you think this article should be classified as Type 4? (Yes/No) Why or why not.",
            27: "To what extent does this article align with Type 4? Respond with a score between 0 and 1 (three decimal places) followed by a brief rationale.",
            28: "On a 1-5 Likert scale, how strongly do you agree that this article fits Type 4? Provide the number, the matching label, and a short justification."
        }
    
    def extract_pdf_text(self, pdf_path: str) -> str:
        """Extract text content from PDF"""
        try:
            doc = fitz.open(pdf_path)
            text_content = []
            
            for page_num in range(doc.page_count):
                page = doc[page_num]
                text = page.get_text()
                if text.strip():
                    text_content.append(f"--- Page {page_num + 1} ---\n{text}")
            
            doc.close()
            return "\n\n".join(text_content)
            
        except Exception as e:
            raise Exception(f"Failed to extract PDF text: {str(e)}")
    
    def analyze_paper(self, pdf_file, progress_callback=None) -> Dict:
        """
        Perform complete 4PT analysis on uploaded paper
        
        Args:
            pdf_file: Uploaded PDF file object
            progress_callback: Optional callback for progress updates
            
        Returns:
            Dict containing analysis results
        """
        
        if progress_callback:
            progress_callback(0.1, "Processing PDF file...")
        
        # Save and extract PDF text
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            if hasattr(pdf_file, 'read'):
                tmp_file.write(pdf_file.read())
            else:
                tmp_file.write(pdf_file)
            pdf_path = tmp_file.name
        
        try:
            paper_text = self.extract_pdf_text(pdf_path)
            if len(paper_text.strip()) < 500:
                raise Exception("Insufficient text extracted from PDF")
            
            self.paper_content = paper_text
            
            if progress_callback:
                progress_callback(0.3, "Running 4PT analysis...")
            
            # Perform analysis
            analysis_result = self._run_analysis(paper_text, progress_callback)
            
            # Store results for follow-up questions
            self.current_paper = pdf_file.name if hasattr(pdf_file, 'name') else "uploaded_paper.pdf"
            self.current_analysis = analysis_result
            
            if progress_callback:
                progress_callback(1.0, "Analysis complete!")
            
            return analysis_result
            
        finally:
            # Clean up temporary file
            try:
                os.unlink(pdf_path)
            except:
                pass
    
    def _run_analysis(self, paper_text: str, progress_callback=None) -> Dict:
        """Run the core 4PT analysis"""
        
        # Create analysis prompt
        analysis_prompt = self._create_analysis_prompt(paper_text)
        
        if progress_callback:
            progress_callback(0.5, "AI analysis in progress...")
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert academic researcher specializing in policy theory analysis. Provide detailed, evidence-based analysis following the 4PT framework."
                    },
                    {
                        "role": "user", 
                        "content": analysis_prompt
                    }
                ],
                temperature=self.temperature,
                max_tokens=4000
            )
            
            raw_analysis = response.choices[0].message.content
            
            if progress_callback:
                progress_callback(0.8, "Processing results...")
            
            # Parse and structure the analysis
            structured_result = self._parse_analysis_result(raw_analysis)
            
            return structured_result
            
        except Exception as e:
            raise Exception(f"Analysis failed: {str(e)}")
    
    def _create_analysis_prompt(self, paper_text: str) -> str:
        """Create the analysis prompt with paper content and questions"""
        
        # Truncate paper if too long (keep first ~8000 characters)
        if len(paper_text) > 8000:
            paper_text = paper_text[:8000] + "\n\n[Document truncated for analysis...]"
        
        prompt = f"""
Please analyze the following academic paper using the 4PT (Four Policy Theory) framework.

# 4PT Framework Reference:
{self.codebook}

# Paper to Analyze:
{paper_text}

# Analysis Instructions:
Please answer the following key questions systematically:

1. **Primary Research Question (Q2)**: What problems or set of problems is the article trying to address?

2. **Problem Focus (Q3)**: Do the analysis, conclusions, and theories derive from, and are directed to, understanding and/or managing a clearly specified 'on the ground' problem or class of problems? (Yes/No)

3. **Broader Application (Q6)**: Are the analysis, conclusions, and theories generated to apply beyond understanding, and/or managing a clearly specified 'on the ground' problem or class of problems? (Yes/No)

4. **Self-Interest Assumption (Q9)**: Do the analysis, conclusions, and theories treat individuals, organizations and states as largely self-interested, satisfaction driven entities that seek to maximize some kind of 'utility' outcome? (Yes/No)

5. **Beyond Self-Interest (Q12)**: Do the analysis incorporate theories and conclusions incorporate an assessment of individuals, organizations and/or states that extends beyond self-interested satisfaction seeking motivations? (Yes/No)

6. **Final Classification (Q15)**: Based on your analysis above, what is your final 4PT Type classification? (Type 1 / Type 2 / Type 3 / Type 4)

7. **Difficulty Assessment (Q16)**: What is the difficulty level of this classification? (1 - Very Easy / 2 - Easy / 3 - Medium / 4 - Hard / 5 - Very Hard)

8. **Type Alignment Analysis**: For each type (1-4), provide:
   - Yes/No classification support
   - Alignment score (0.000-1.000)
   - Confidence level (1-5 Likert scale)

# Output Format:
Please structure your response clearly with section headers and provide specific textual evidence from the paper to support your conclusions.
"""
        
        return prompt
    
    def _parse_analysis_result(self, raw_analysis: str) -> Dict:
        """Parse and structure the raw analysis result"""
        
        # For now, return structured format
        # TODO: Add more sophisticated parsing to extract specific answers
        
        result = {
            "timestamp": datetime.now().isoformat(),
            "raw_analysis": raw_analysis,
            "classification": self._extract_classification(raw_analysis),
            "difficulty": self._extract_difficulty(raw_analysis),
            "key_findings": self._extract_key_findings(raw_analysis),
            "evidence_summary": self._extract_evidence(raw_analysis),
            "type_scores": self._extract_type_scores(raw_analysis)
        }
        
        return result
    
    def _extract_classification(self, text: str) -> str:
        """Extract the final 4PT classification from analysis text"""
        import re
        
        # Look for explicit Type X mentions
        type_pattern = r"Type\s+([1-4])"
        matches = re.findall(type_pattern, text, re.IGNORECASE)
        
        if matches:
            return f"Type {matches[-1]}"  # Use last mentioned type
        
        return "Classification unclear"
    
    def _extract_difficulty(self, text: str) -> str:
        """Extract difficulty assessment"""
        import re
        
        difficulty_pattern = r"difficulty.*?([1-5])"
        matches = re.findall(difficulty_pattern, text, re.IGNORECASE)
        
        if matches:
            level = matches[0]
            labels = {"1": "Very Easy", "2": "Easy", "3": "Medium", "4": "Hard", "5": "Very Hard"}
            return f"{level} - {labels.get(level, 'Unknown')}"
        
        return "Not specified"
    
    def _extract_key_findings(self, text: str) -> List[str]:
        """Extract key findings from analysis"""
        # Simple extraction - look for numbered points or bullet points
        findings = []
        
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            if (line.startswith('- ') or 
                line.startswith('* ') or 
                any(line.startswith(f'{i}.') for i in range(1, 10))):
                findings.append(line)
        
        return findings[:10]  # Limit to top 10 findings
    
    def _extract_evidence(self, text: str) -> List[str]:
        """Extract evidence passages mentioned in analysis"""
        # Look for quoted text or explicit evidence mentions
        import re
        
        evidence = []
        
        # Find quoted passages
        quote_pattern = r'"([^"]{20,200})"'
        quotes = re.findall(quote_pattern, text)
        evidence.extend(quotes[:5])
        
        # Find evidence keywords
        evidence_pattern = r"evidence.*?[:：]\s*(.{20,200})"
        evidence_matches = re.findall(evidence_pattern, text, re.IGNORECASE)
        evidence.extend(evidence_matches[:3])
        
        return evidence
    
    def _extract_type_scores(self, text: str) -> Dict[str, Dict]:
        """Extract alignment scores for each type"""
        import re
        
        scores = {}
        
        for type_num in range(1, 5):
            type_key = f"Type {type_num}"
            
            # Look for alignment scores
            score_pattern = rf"Type\s+{type_num}.*?(\d\.\d{{3}})"
            score_matches = re.findall(score_pattern, text, re.IGNORECASE)
            
            # Look for Likert ratings
            likert_pattern = rf"Type\s+{type_num}.*?([1-5])\s*[-–—]\s*(\w+)"
            likert_matches = re.findall(likert_pattern, text, re.IGNORECASE)
            
            scores[type_key] = {
                "alignment_score": score_matches[0] if score_matches else "Not found",
                "likert_rating": f"{likert_matches[0][0]} - {likert_matches[0][1]}" if likert_matches else "Not found"
            }
        
        return scores
    
    def ask_followup_question(self, question: str) -> str:
        """
        Answer follow-up questions about the current analysis
        
        Args:
            question: User's follow-up question
            
        Returns:
            AI response to the question
        """
        
        if not self.current_analysis or not self.paper_content:
            return "❌ No paper analysis available. Please upload and analyze a paper first."
        
        followup_prompt = f"""
Based on my previous 4PT analysis of this academic paper, please answer the following follow-up question:

# Previous Analysis:
{self.current_analysis.get('raw_analysis', 'Previous analysis not available')}

# Classification Result:
{self.current_analysis.get('classification', 'Not available')}

# Follow-up Question:
{question}

# Paper Reference (if needed):
{self.paper_content[:2000]}{'...' if len(self.paper_content) > 2000 else ''}

Please provide a detailed, evidence-based response that relates to the 4PT framework analysis.
"""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert academic researcher. Answer follow-up questions about 4PT analysis with specific references to the paper and framework."
                    },
                    {
                        "role": "user",
                        "content": followup_prompt
                    }
                ],
                temperature=self.temperature,
                max_tokens=1500
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            return f"❌ Failed to process follow-up question: {str(e)}"
    
    def get_analysis_summary(self) -> str:
        """Get a formatted summary of the current analysis"""
        
        if not self.current_analysis:
            return "No analysis available"
        
        analysis = self.current_analysis
        
        summary = f"""
## 📊 4PT Analysis Summary

**Paper**: {self.current_paper or 'Uploaded Document'}
**Classification**: {analysis.get('classification', 'Not determined')}
**Difficulty**: {analysis.get('difficulty', 'Not assessed')}
**Analysis Date**: {analysis.get('timestamp', 'Unknown')}

### 🎯 Key Findings
"""
        
        findings = analysis.get('key_findings', [])
        if findings:
            for finding in findings[:5]:
                summary += f"- {finding}\n"
        else:
            summary += "- No specific findings extracted\n"
        
        summary += "\n### 📈 Type Alignment Scores\n"
        
        type_scores = analysis.get('type_scores', {})
        for type_name, scores in type_scores.items():
            alignment = scores.get('alignment_score', 'N/A')
            likert = scores.get('likert_rating', 'N/A')
            summary += f"**{type_name}**: Alignment {alignment}, Rating {likert}\n"
        
        return summary