#!/usr/bin/env python3
"""
4PT Academic Paper Analyzer - Interactive Q&A Version
Focus on core analysis and follow-up questions
"""

import os
import sys
from pathlib import Path
from typing import Tuple, List

import gradio as gr

# Import our core analyzer
from core_analyzer import Core4PTAnalyzer

# Global analyzer instance
analyzer = None

def initialize_system():
    """Initialize the analyzer system"""
    global analyzer
    
    # Get API key from environment
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("HF_TOKEN")
    
    if not api_key:
        return "❌ OpenAI API key not found. Please configure OPENAI_API_KEY."
    
    try:
        analyzer = Core4PTAnalyzer(api_key)
        return "✅ 4PT Analyzer initialized successfully!"
    except Exception as e:
        return f"❌ Failed to initialize analyzer: {str(e)}"

def analyze_paper(pdf_file, progress=gr.Progress()) -> Tuple[str, str, str]:
    """
    Analyze uploaded paper and return results
    
    Returns:
        Tuple of (classification_result, detailed_analysis, error_message)
    """
    
    if pdf_file is None:
        return "", "", "Please upload a PDF file to analyze."
    
    global analyzer
    if analyzer is None:
        init_msg = initialize_system()
        if "❌" in init_msg:
            return "", "", init_msg
    
    try:
        # Run analysis with progress tracking
        def progress_callback(value, desc):
            progress(value, desc=desc)
        
        progress(0.0, desc="Starting analysis...")
        
        result = analyzer.analyze_paper(pdf_file, progress_callback)
        
        # Format classification result
        classification = f"""
## 🎯 Classification Result

**Type**: {result.get('classification', 'Not determined')}
**Difficulty**: {result.get('difficulty', 'Not assessed')}
**Analysis Date**: {result.get('timestamp', 'Just now')}

### 📊 Type Alignment Summary
"""
        
        type_scores = result.get('type_scores', {})
        for type_name, scores in type_scores.items():
            alignment = scores.get('alignment_score', 'N/A')
            rating = scores.get('likert_rating', 'N/A')
            classification += f"- **{type_name}**: Score {alignment}, Rating {rating}\n"
        
        # Format detailed analysis
        detailed_analysis = f"""
## 📋 Detailed Analysis

{result.get('raw_analysis', 'Analysis details not available')}

---

### 🔍 Key Evidence
"""
        
        evidence = result.get('evidence_summary', [])
        if evidence:
            for i, ev in enumerate(evidence[:5], 1):
                detailed_analysis += f"{i}. {ev}\n"
        else:
            detailed_analysis += "No specific evidence extracted from analysis."
        
        return classification, detailed_analysis, ""
        
    except Exception as e:
        error_msg = f"Analysis failed: {str(e)}"
        return "", "", error_msg

def ask_followup(question: str, chat_history: List) -> Tuple[List, str]:
    """
    Handle follow-up questions about the analysis
    
    Args:
        question: User's question
        chat_history: Previous chat messages
        
    Returns:
        Tuple of (updated_chat_history, empty_input)
    """
    
    if not question.strip():
        return chat_history, ""
    
    global analyzer
    if analyzer is None or analyzer.current_analysis is None:
        response = "❌ No paper analysis available. Please upload and analyze a paper first."
    else:
        response = analyzer.ask_followup_question(question)
    
    # Add to chat history
    chat_history.append([question, response])
    
    return chat_history, ""  # Return empty string to clear input

def clear_chat():
    """Clear the chat history"""
    return []

def create_interface():
    """Create the Gradio interface"""
    
    # Custom CSS
    css = """
    .gradio-container {
        max-width: 1400px !important;
        margin: 0 auto;
    }
    .chat-container {
        height: 400px;
        overflow-y: auto;
    }
    .analysis-container {
        height: 500px;
        overflow-y: auto;
    }
    """
    
    with gr.Blocks(css=css, title="4PT Academic Paper Analyzer") as demo:
        
        # Header
        gr.Markdown("""
        # 🎓 4PT Academic Paper Analyzer
        
        ## Interactive Analysis & Q&A System
        
        Upload academic papers for comprehensive **Four Policy Theory (4PT) framework** analysis. 
        Get detailed classifications and ask follow-up questions about the results.
        
        **Key Features:**
        - 📄 PDF paper analysis using 28-question framework
        - 🎯 Automatic 4PT type classification  
        - 💬 Interactive Q&A about analysis results
        - 📊 Detailed evidence and reasoning
        """)
        
        # Initialize system status
        with gr.Row():
            init_status = gr.Textbox(
                label="System Status",
                value="Click 'Initialize System' to start",
                interactive=False
            )
            init_button = gr.Button("🔧 Initialize System", variant="secondary")
        
        # Main interface
        with gr.Row():
            # Left column: Upload and Analysis
            with gr.Column(scale=1):
                gr.Markdown("### 📤 Upload & Analyze")
                
                pdf_input = gr.File(
                    label="Upload Academic Paper (PDF)",
                    file_types=[".pdf"],
                    type="binary"
                )
                
                analyze_button = gr.Button(
                    "🔍 Analyze Paper",
                    variant="primary",
                    size="lg"
                )
                
                gr.Markdown("---")
                
                # Classification result
                classification_output = gr.Markdown(
                    label="🎯 Classification Result",
                    value="*Upload and analyze a paper to see classification results...*"
                )
            
            # Right column: Detailed Analysis and Chat
            with gr.Column(scale=2):
                with gr.Tabs():
                    # Tab 1: Detailed Analysis
                    with gr.Tab("📋 Detailed Analysis"):
                        detailed_output = gr.Markdown(
                            value="*Detailed analysis will appear here after processing...*",
                            elem_classes=["analysis-container"]
                        )
                    
                    # Tab 2: Interactive Q&A
                    with gr.Tab("💬 Ask Questions"):
                        gr.Markdown("""
                        ### Ask Follow-up Questions
                        
                        After analyzing a paper, you can ask specific questions about:
                        - Classification reasoning
                        - Evidence interpretation  
                        - Comparison with other types
                        - Methodological details
                        - Policy implications
                        """)
                        
                        chatbot = gr.Chatbot(
                            label="Q&A Chat",
                            elem_classes=["chat-container"],
                            height=350
                        )
                        
                        with gr.Row():
                            question_input = gr.Textbox(
                                label="Your Question",
                                placeholder="Ask about the analysis results...",
                                scale=4
                            )
                            ask_button = gr.Button("📤 Ask", scale=1)
                        
                        with gr.Row():
                            clear_button = gr.Button("🗑️ Clear Chat", variant="secondary")
                    
                    # Tab 3: Example Questions
                    with gr.Tab("❓ Example Questions"):
                        gr.Markdown("""
                        ### Example Follow-up Questions
                        
                        **About Classification:**
                        - "Why was this paper classified as Type 2 instead of Type 1?"
                        - "What evidence supports the Type 3 classification?"
                        - "How confident are you in this classification?"
                        
                        **About Evidence:**
                        - "Can you quote specific passages that support this classification?"
                        - "What are the strongest indicators for this type?"
                        - "Are there any contradictory elements in the paper?"
                        
                        **About Comparison:**
                        - "How does this compare to typical Type 1 papers?"
                        - "What would make this paper a Type 4 instead?"
                        - "Is this a borderline case between types?"
                        
                        **About Methodology:**
                        - "What research methods does the paper use?"
                        - "How does the theoretical framework align with 4PT types?"
                        - "What are the policy implications of this classification?"
                        
                        **About Context:**
                        - "What field of study is this paper from?"
                        - "How does this fit within broader policy research trends?"
                        - "What similar papers would you recommend?"
                        """)
        
        # Error display
        error_output = gr.Textbox(
            label="⚠️ Errors/Warnings",
            visible=False,
            lines=3
        )
        
        # Event handlers
        
        # Initialize system
        init_button.click(
            fn=initialize_system,
            outputs=[init_status]
        )
        
        # Analyze paper
        analyze_button.click(
            fn=analyze_paper,
            inputs=[pdf_input],
            outputs=[classification_output, detailed_output, error_output],
            show_progress=True
        )
        
        # Ask follow-up question
        ask_button.click(
            fn=ask_followup,
            inputs=[question_input, chatbot],
            outputs=[chatbot, question_input]
        )
        
        # Also allow Enter key to ask question
        question_input.submit(
            fn=ask_followup,
            inputs=[question_input, chatbot],
            outputs=[chatbot, question_input]
        )
        
        # Clear chat
        clear_button.click(
            fn=clear_chat,
            outputs=[chatbot]
        )
        
        # Show/hide error output
        def update_error_visibility(error_text):
            return gr.update(visible=bool(error_text.strip()))
        
        error_output.change(
            fn=update_error_visibility,
            inputs=[error_output],
            outputs=[error_output]
        )
        
        # Footer
        gr.Markdown("""
        ---
        
        ### 📚 About the 4PT Framework
        
        The **Four Policy Theory (4PT) framework** classifies policy research based on theoretical foundations:
        
        - **Type 1**: Applied problem-solving focused on specific policy challenges
        - **Type 2**: Market-oriented approaches emphasizing utility maximization  
        - **Type 3**: Applied research with broader behavioral considerations
        - **Type 4**: General theoretical development beyond specific applications
        
        This system uses a comprehensive 28-question analysis framework to ensure rigorous classification.
        """)
    
    return demo

if __name__ == "__main__":
    # Create and launch interface
    demo = create_interface()
    demo.launch(
        share=False,
        debug=True,
        show_error=True,
        server_port=7860
    )