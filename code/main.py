"""
4PT分析系统 - 模块化版本主程序
"""
import getpass
from pathlib import Path

from config import Config
from document_reader import DocumentReader
from analyzer import FourPTAnalyzer
from result_saver import ResultSaver


class FourPTSystem:
    """4PT分析系统主类"""
    
    def __init__(self):
        """初始化系统"""
        self.config = Config()
        self.document_reader = DocumentReader()
        self.analyzer = None
        self.result_saver = ResultSaver()
        
    def setup(self) -> bool:
        """设置系统，包括验证配置和初始化API客户端"""
        # 验证基本配置
        if not self.config.validate():
            return False
        
        # 如果没有API密钥，提示用户输入
        if not self.config.OPENAI_API_KEY:
            api_key = getpass.getpass("🔑 Enter OPENAI_API_KEY: ")
            self.analyzer = FourPTAnalyzer(api_key=api_key)
        else:
            self.analyzer = FourPTAnalyzer()
        
        print(f"OpenAI client ok. Using model: {self.config.CLS_MODEL}")
        return True
    
    def load_documents(self) -> tuple:
        """加载编码手册和待分析文章"""
        # 加载编码手册
        codebook_pages = self.document_reader.read_markdown(str(self.config.CODEBOOK_MD))
        print(f"Codebook sections: {len(codebook_pages)}")
        
        # 加载待分析文章
        paper_pages = self.document_reader.read_pdf(str(self.config.PAPER_PDF))
        print(f"Paper pages: {len(paper_pages)}")
        
        return codebook_pages, paper_pages
    
    def run_analysis(self, codebook_pages: list, paper_pages: list) -> dict:
        """执行4PT分析"""
        print("\n🔍 Starting 4PT analysis...")
        result = self.analyzer.analyze_article(paper_pages, codebook_pages)
        
        if result:
            print("✅ Analysis completed successfully")
            return result
        else:
            print("❌ Analysis failed")
            return None
    
    def display_and_save_results(self, result: dict) -> None:
        """显示和保存分析结果"""
        if not result:
            print("No results to display!")
            return
        
        # 显示结果
        print("=" * 60)
        print("4PT ANALYSIS RESULT")
        print("=" * 60)
        print(result['analysis_text'])
        print("\n" + "=" * 60)
        print("METADATA:")
        metadata = result['analysis_metadata']
        print(f"Model: {metadata['model']}")
        print(f"Timestamp: {metadata['timestamp']}")
        print(f"Prompt Length: {metadata['prompt_length']} chars")
        print(f"Response Length: {metadata['response_length']} chars")
        
        # 保存结果
        self.result_saver.save_analysis_result(result, article_name="sample_paper")
    
    def run(self) -> None:
        """运行完整的分析流程"""
        print("🚀 Starting 4PT Analysis System...")
        
        # 1. 系统设置
        if not self.setup():
            print("❌ System setup failed!")
            return
        
        # 2. 加载文档
        try:
            codebook_pages, paper_pages = self.load_documents()
        except Exception as e:
            print(f"❌ Failed to load documents: {e}")
            return
        
        # 3. 执行分析
        result = self.run_analysis(codebook_pages, paper_pages)
        
        # 4. 显示和保存结果
        self.display_and_save_results(result)
        
        print("\n🎉 Analysis complete!")


def main():
    """主入口函数"""
    system = FourPTSystem()
    system.run()


if __name__ == '__main__':
    main()