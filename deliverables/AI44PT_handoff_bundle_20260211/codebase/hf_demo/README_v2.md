# 4PT Academic Paper Analyzer - Interactive Version

An interactive web application for analyzing academic papers using the Four Policy Theory (4PT) framework with follow-up Q&A capabilities.

## Key Features

- **📄 Single Paper Analysis**: Upload PDF papers for comprehensive 4PT analysis
- **🎯 Automatic Classification**: AI-driven classification into one of four policy theory types
- **💬 Interactive Q&A**: Ask follow-up questions about analysis results
- **📊 Detailed Evidence**: Extract and highlight supporting evidence from papers
- **🔍 Deep Analysis**: 28-question framework ensures thorough evaluation

## Interface Overview

### Main Components

1. **Upload & Analyze**: Upload PDF and run 4PT analysis
2. **Classification Results**: View type classification and alignment scores  
3. **Detailed Analysis**: Complete analysis breakdown with evidence
4. **Interactive Q&A**: Chat interface for follow-up questions
5. **Example Questions**: Guided prompts for deeper exploration

### Usage Flow

1. **Initialize**: Click "Initialize System" to set up the analyzer
2. **Upload**: Select and upload a PDF academic paper
3. **Analyze**: Click "Analyze Paper" and wait for processing
4. **Review**: Examine classification results and detailed analysis
5. **Explore**: Ask follow-up questions in the Q&A tab

## Technical Details

- **Core Engine**: Simplified analyzer focused on Q&A interaction
- **AI Model**: OpenAI GPT-4 for comprehensive text analysis
- **Framework**: Complete 28-question 4PT evaluation system
- **Interface**: Gradio-based web interface with real-time interaction

## Local Testing

```bash
# Install dependencies
pip install -r requirements_v2.txt

# Set up environment
export OPENAI_API_KEY="your-api-key"

# Run application
python app_v2.py
```

## Deployment to Hugging Face

1. Create new Space with Gradio SDK
2. Upload `app_v2.py`, `core_analyzer.py`, and `requirements_v2.txt`
3. Set `OPENAI_API_KEY` in Space settings
4. Space will auto-build and deploy

## Example Questions

- "Why was this paper classified as Type 2?"
- "What specific evidence supports this classification?"
- "How confident are you in this result?"
- "What would make this paper a different type?"
- "Can you explain the theoretical framework used?"

This streamlined version focuses on the core value proposition: high-quality 4PT analysis with interactive exploration capabilities.