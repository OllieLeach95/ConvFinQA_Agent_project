# ConvFinQA Agent

An agent-based system for conversational question answering over financial documents. This project implements an intelligent agent that can answer complex numerical reasoning questions about financial reports by analyzing both structured tables and unstructured text.

## About ConvFinQA

ConvFinQA is a dataset containing conversational numerical reasoning questions over financial documents. The dataset includes 3,892 conversations with 14,115 questions that require understanding and reasoning over financial tables and text. See `dataset.md` for detailed information about the dataset, including baselines and performance metrics. 

## Get started
### Prerequisites
- Python 3.12+
- [UV environment manager](https://docs.astral.sh/uv/getting-started/installation/)

### Setup
1. Clone this repository
2. Use the UV environment manager to install dependencies:

```bash
# install uv
brew install uv

# set up env
uv sync

# add python package to env
uv add <package_name>
```

## Usage

### CLI Chat Interface

The project includes a CLI application built with [typer](https://typer.tiangolo.com/) that provides an interactive chat interface for querying financial documents.

You can run the application using:
```bash 
uv run main
```
or you can use the longer form:
```bash
uv run python src/main.py
```

To chat with a specific financial document:
```bash
uv run main chat <record_id>
```
[![Chat](figures/chat_example.png)](figures/chat.png)

## Project Structure

- `src/` - Source code for the agent system
  - `agent/` - Agent orchestration, tools, and context building
  - `models/` - Data schemas and models
  - `utils/` - Evaluation and parsing utilities
- `data/` - ConvFinQA dataset
- `notebooks/` - Jupyter notebooks for analysis and experimentation
- `scripts/` - Utility scripts
- `REPORT.md` - Project findings and analysis

## Features

- Conversational question answering over financial documents
- Support for numerical reasoning and calculations
- Integration with structured tables and unstructured text
- Agent-based architecture with tool use capabilities

