#!/usr/bin/env python3
"""
4PT Academic Paper Analyzer - Hugging Face Gradio Interface
Maintains full analysis quality while providing web accessibility
"""

import os
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Dict, Tuple, Optional

import gradio as gr
import pandas as pd

# Add the parent code directory to path for imports
sys.path.append(str(Path(__file__).parent.parent / "code"))

try:
    from config import Config
    from batch_analyzer import BatchAnalyzer
    from document_reader import DocumentReader
    from response_parser import ResponseParser
except ImportError as e:
    print(f"Import error: {e}")
    print("Running in demo mode without full analysis capabilities")

# Global analyzer instance
analyzer = None

def initialize_analyzer():
    """Initialize the analyzer with HF-compatible settings"""
    global analyzer
    
    try:
        # Check for OpenAI API key
        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("HF_TOKEN") 
        if not api_key:
            return None, "❌ OpenAI API key not found. Please contact administrator."
        
        # Initialize config for HF environment
        Config.OPENAI_API_KEY = api_key
        Config.DEBUG_MODE = False  # Full analysis mode
        Config.DEFAULT_AI_RUNS = 3  # Maintain quality
        Config.ENABLE_MAJORITY_VOTE = True
        
        # Initialize analyzer
        analyzer = BatchAnalyzer(Config())
        return analyzer, "✅ Analyzer initialized successfully"
        
    except Exception as e:
        return None, f"❌ Initialization failed: {str(e)}"

def analyze_single_paper(
    pdf_file,
    analysis_runs: int = 3,
    reasoning_effort: str = "medium",
    enable_consensus: bool = True,
    progress=gr.Progress()
) -> Tuple[str, str, str, str]:
    """
    Analyze a single academic paper using the full 4PT framework
    
    Args:
        pdf_file: Uploaded PDF file
        analysis_runs: Number of independent AI runs (1-5)
        reasoning_effort: AI reasoning effort level
        enable_consensus: Whether to enable majority voting
        progress: Gradio progress tracker
    
    Returns:
        Tuple of (classification, confidence, detailed_analysis, error_message)
    """
    
    if pdf_file is None:
        return "", "", "", "❌ Please upload a PDF file"
    
    global analyzer
    if analyzer is None:
        analyzer, init_msg = initialize_analyzer()
        if analyzer is None:
            return "", "", "", init_msg
    
    try:
        progress(0.1, desc="Processing PDF file...")
        
        # Save uploaded file to temporary location
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(pdf_file.read())
            pdf_path = tmp_file.name
        
        progress(0.2, desc="Reading document content...")
        
        # Read document
        doc_reader = DocumentReader()
        doc_content = doc_reader.read_pdf(pdf_path)
        
        if not doc_content or len(doc_content.strip()) < 100:
            return "", "", "", "❌ Could not extract sufficient text from PDF"
        
        progress(0.3, desc="Configuring analysis parameters...")
        
        # Configure analysis parameters
        original_runs = Config.DEFAULT_AI_RUNS
        original_effort = Config.DEFAULT_REASONING_EFFORT
        original_consensus = Config.ENABLE_MAJORITY_VOTE
        
        Config.DEFAULT_AI_RUNS = analysis_runs
        Config.DEFAULT_REASONING_EFFORT = reasoning_effort.lower()
        Config.ENABLE_MAJORITY_VOTE = enable_consensus
        
        # Create temporary Excel file for single paper analysis
        progress(0.4, desc="Preparing analysis framework...")
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.xlsx') as tmp_excel:
            # Create minimal Excel structure for single paper
            df = pd.DataFrame({
                '#': [1],
                'Title of the Paper': ['Uploaded Paper'],
                'source': [os.path.basename(pdf_file.name) if hasattr(pdf_file, 'name') else 'uploaded.pdf'],
                'Type (Q15)': [''],  # Will be filled by analysis
            })
            df.to_excel(tmp_excel.name, index=False)
            excel_path = tmp_excel.name
        
        progress(0.5, desc="Running 4PT analysis...")
        
        # Run the full analysis pipeline
        try:
            # Use the existing batch analyzer but with single paper
            results_df = analyzer.process_batch(
                excel_path=excel_path,
                raw_data_path=None,  # Generate new analysis
                stage="full",
                use_all_runs=False
            )
            
            progress(0.8, desc="Processing results...")
            
            if results_df is None or results_df.empty:
                return "", "", "", "❌ Analysis failed to produce results"
            
            # Extract results
            human_rows = results_df[results_df['source'] == 'human']
            ai_rows = results_df[results_df['source'] != 'human']
            majority_rows = results_df[results_df['source'].str.contains('majority', na=False)]
            
            progress(0.9, desc="Formatting output...")
            
            # Determine final classification
            if not majority_rows.empty:
                # Use majority vote result
                final_row = majority_rows.iloc[0]
                classification = final_row.get('Type (Q15)', 'Unknown')
                confidence_info = final_row.get(analyzer.AI_AGREEMENT_COL, 'Not available')
                vote_counts = final_row.get(analyzer.Q15_VOTE_COUNTS_COL, 'Not available')
            elif len(ai_rows) > 0:
                # Use first AI result if no majority vote
                final_row = ai_rows.iloc[0]
                classification = final_row.get('Type (Q15)', 'Unknown')
                confidence_info = "Single run (no consensus analysis)"
                vote_counts = "N/A (single run)"
            else:
                return "", "", "", "❌ No AI analysis results found"
            
            # Format confidence information
            confidence_text = f"**Agreement Level**: {confidence_info}\n**Vote Distribution**: {vote_counts}"
            
            # Create detailed analysis
            detailed_analysis = "## 📊 4PT Analysis Results\n\n"
            detailed_analysis += f"**Final Classification**: {classification}\n\n"
            detailed_analysis += f"**Analysis Runs**: {len(ai_rows)} independent evaluations\n\n"
            detailed_analysis += f"**Consensus Method**: {'Majority voting enabled' if enable_consensus else 'Individual runs only'}\n\n"
            
            # Add sample questions and answers if available
            detailed_analysis += "## 🔍 Key Analysis Questions\n\n"
            
            # Extract some key question responses
            key_questions = ['Q1', 'Q3', 'Q6', 'Q9', 'Q12', 'Q15', 'Q16']
            for q in key_questions:
                col_name = f"Response {q}"
                if col_name in final_row:
                    response = final_row[col_name]
                    if pd.notna(response) and str(response).strip():
                        detailed_analysis += f"**{q}**: {str(response)[:200]}{'...' if len(str(response)) > 200 else ''}\n\n"
            
            # Add methodology note
            detailed_analysis += "---\n\n"
            detailed_analysis += "## 📚 Methodology\n\n"
            detailed_analysis += f"This analysis used the complete 28-question 4PT framework with {analysis_runs} independent AI evaluations. "
            if enable_consensus:
                detailed_analysis += "Results represent the majority consensus across all runs."
            else:
                detailed_analysis += "Results represent individual analysis without consensus voting."
            
            progress(1.0, desc="Analysis complete!")
            
            return classification, confidence_text, detailed_analysis, ""
            
        finally:
            # Restore original config
            Config.DEFAULT_AI_RUNS = original_runs
            Config.DEFAULT_REASONING_EFFORT = original_effort
            Config.ENABLE_MAJORITY_VOTE = original_consensus
            
            # Clean up temporary files
            try:
                os.unlink(pdf_path)
                os.unlink(excel_path)
            except:
                pass
    
    except Exception as e:
        error_msg = f"❌ Analysis failed: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"
        return "", "", "", error_msg

def create_interface():
    """Create the Gradio interface"""
    
    # Custom CSS for better styling
    css = """
    .gradio-container {
        max-width: 1200px !important;
    }
    .tab-nav {
        background: linear-gradient(90deg, #1e3a8a, #3b82f6);
    }
    """
    
    with gr.Blocks(css=css, title="4PT Academic Paper Analyzer") as demo:
        gr.Markdown("""
        # 🎓 4PT Academic Paper Analyzer
        
        ## Advanced Policy Theory Classification System
        
        Upload academic papers to analyze them using the **Four Policy Theory (4PT) framework**. 
        This system performs a comprehensive 28-question analysis to classify papers into one of four policy theory types.
        
        **Features:**
        - ✅ Complete 28-question 4PT framework analysis
        - ✅ Multi-run consensus analysis for reliability  
        - ✅ Detailed evidence extraction and reasoning
        - ✅ Research-grade methodology preservation
        """)
        
        with gr.Tab("📄 Single Paper Analysis"):
            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### 📎 Upload & Configure")
                    
                    pdf_input = gr.File(
                        label="Upload PDF Paper",
                        file_types=[".pdf"],
                        type="binary"
                    )
                    
                    with gr.Accordion("⚙️ Analysis Settings", open=False):
                        runs_slider = gr.Slider(
                            minimum=1,
                            maximum=5,
                            value=3,
                            step=1,
                            label="Analysis Runs (More runs = higher reliability)",
                            info="Number of independent AI evaluations"
                        )
                        
                        effort_radio = gr.Radio(
                            choices=["low", "medium", "high"],
                            value="medium",
                            label="Reasoning Effort",
                            info="Higher effort provides more detailed analysis"
                        )
                        
                        consensus_checkbox = gr.Checkbox(
                            value=True,
                            label="Enable Consensus Analysis",
                            info="Use majority voting across runs for final result"
                        )
                    
                    analyze_btn = gr.Button(
                        "🔍 Analyze Paper",
                        variant="primary",
                        size="lg"
                    )
                
                with gr.Column(scale=2):
                    gr.Markdown("### 📊 Analysis Results")
                    
                    with gr.Row():
                        classification_output = gr.Textbox(
                            label="🎯 4PT Classification",
                            placeholder="Upload and analyze a paper to see results...",
                            lines=2
                        )
                        
                        confidence_output = gr.Textbox(
                            label="📈 Confidence & Agreement",
                            placeholder="Confidence metrics will appear here...",
                            lines=3
                        )
                    
                    detailed_output = gr.Markdown(
                        label="📋 Detailed Analysis",
                        value="*Detailed analysis results will appear here after processing...*"
                    )
                    
                    error_output = gr.Textbox(
                        label="⚠️ Errors/Warnings",
                        visible=False,
                        lines=3
                    )
        
        with gr.Tab("ℹ️ About 4PT Framework"):
            gr.Markdown("""
            ## What is the 4PT Framework?
            
            The **Four Policy Theory (4PT) framework** is an academic classification system for analyzing policy research papers based on their theoretical foundations.
            
            ### The Four Types:
            
            **Type 1**: Applied problem-solving focused research  
            **Type 2**: Market-oriented, utility-maximizing approaches  
            **Type 3**: Applied research with broader behavioral considerations  
            **Type 4**: General theory development beyond specific applications  
            
            ### Analysis Process:
            
            1. **Document Processing**: PDF text extraction and preparation
            2. **28-Question Framework**: Comprehensive structured analysis
            3. **Multi-Run Analysis**: Multiple independent AI evaluations  
            4. **Consensus Building**: Majority voting for final classification
            5. **Quality Assurance**: Confidence scoring and uncertainty analysis
            
            ### Quality Guarantees:
            
            - ✅ **Research-Grade Methodology**: Same analysis pipeline used in academic research
            - ✅ **Reproducible Results**: Consistent classification across runs
            - ✅ **Evidence-Based**: Classifications linked to specific textual evidence
            - ✅ **Uncertainty Quantification**: Clear confidence levels for all results
            
            ### Supported File Types:
            - PDF academic papers (journal articles, working papers, reports)
            - Text must be machine-readable (not scanned images)
            - Recommended: Papers focused on policy, governance, or regulatory topics
            """)
        
        with gr.Tab("🚀 API Usage"):
            gr.Markdown("""
            ## Programmatic Access
            
            This interface can also be used programmatically via Gradio's API:
            
            ```python
            import gradio as gr
            
            # Connect to the deployed interface
            client = gr.Interface.load("spaces/your-username/4pt-academic-analyzer")
            
            # Analyze a paper
            result = client.predict(
                pdf_file="path/to/paper.pdf",
                analysis_runs=3,
                reasoning_effort="medium",
                enable_consensus=True
            )
            
            classification, confidence, detailed_analysis, errors = result
            print(f"Classification: {classification}")
            ```
            
            ## Batch Processing
            
            For large-scale analysis, consider using the original command-line interface:
            
            ```bash
            # Clone the repository
            git clone https://github.com/your-repo/4pt-analyzer
            
            # Run batch analysis
            python code/pipeline_main.py --stage full --excel-path your_papers.xlsx
            ```
            """)
        
        # Connect the analyze button to the analysis function
        analyze_btn.click(
            fn=analyze_single_paper,
            inputs=[pdf_input, runs_slider, effort_radio, consensus_checkbox],
            outputs=[classification_output, confidence_output, detailed_output, error_output],
            show_progress=True
        )
        
        # Show/hide error output based on content
        def update_error_visibility(error_text):
            return gr.update(visible=bool(error_text.strip()))
        
        error_output.change(
            fn=update_error_visibility,
            inputs=[error_output],
            outputs=[error_output]
        )
    
    return demo

if __name__ == "__main__":
    # Initialize the analyzer
    analyzer, init_message = initialize_analyzer()
    print(init_message)
    
    # Create and launch the interface
    demo = create_interface()
    demo.launch(
        share=False,  # Set to True for temporary public links during development
        debug=True,
        show_error=True,
        server_port=7860  # Standard port for HF Spaces
    )