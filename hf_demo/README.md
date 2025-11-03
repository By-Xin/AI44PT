# 4PT Academic Paper Analyzer

An interactive web application for analyzing academic papers using the Four Policy Theory (4PT) framework.

## Overview

This application provides a user-friendly interface to the comprehensive 4PT analysis system, allowing researchers to upload PDF papers and receive detailed theoretical classifications.

## Features

- **Complete 28-Question Analysis**: Full 4PT framework implementation
- **Multi-Run Consensus**: Configurable number of independent AI evaluations
- **Interactive Interface**: Real-time progress tracking and detailed results
- **Research-Grade Quality**: Maintains the same analytical rigor as the command-line system

## Usage

1. Upload a PDF academic paper
2. Configure analysis parameters (runs, effort level, consensus)
3. Click "Analyze Paper" and wait for results
4. Review the classification, confidence metrics, and detailed analysis

## Technical Details

- Built with Gradio for interactive web interface
- Uses OpenAI GPT models for text analysis
- Implements majority voting for consensus across multiple runs
- Provides detailed evidence extraction and reasoning

## Local Development

```bash
pip install -r requirements.txt
python app.py
```

## Citation

If you use this tool in your research, please cite:

```
[Citation information for the 4PT framework and analysis system]
```

## License

Apache 2.0 License - see LICENSE file for details.