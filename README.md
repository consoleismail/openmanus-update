# OpenManus

A versatile AI agent framework for solving various tasks autonomously.

## Overview

OpenManus is an open-source framework for building general AI agents capable of handling diverse tasks including software development, data analysis, web automation, and more. The framework includes multiple specialized agents and a comprehensive tool collection.

### Source Code Audit Summary

- **Core Architecture**: Modular design with agent classes in `app/agent/`, tools in `app/tool/`, and configuration management.
- **Key Components**:
  - **Agents**: Manus (general-purpose), SWEAgent (software engineering), DataAnalysisAgent, BrowserAgent, MCP-enabled agents.
  - **Tools**: File operations, bash commands, browser automation (Playwright, Browser-Use), search engines, visualization, sandbox execution.
  - **Protocols**: MCP (Model Context Protocol) server integration for tool calling.
  - **Configuration**: TOML-based config for LLM settings, agent options.
- **Entry Points**: `main.py` (CLI), `run_mcp.py` (MCP server), `run_flow.py` (multi-agent workflow).
- **Sandbox**: Docker-based isolated execution environment.
- **Dependencies**: Python 3.12+, extensive package list for AI, web, and system integration.

## Developers

Contributors (from git history): ismail developer

Core team (as per project): Xinbin Liang (@mannaandpoem), Jinyu Xiang (@XiangJinyu), Zhaoyang Yu (@MoshiQAQ), Jiayi Zhang (@didiforgithub), Sirui Hong (@stellaHSR), Sheng Fan, Xiao Tang, Bang Liu, Yuyu Luo, Chenglin Wu.

## Installation on Linux Mint

### Prerequisites

Ensure the following system dependencies are installed:

```bash
sudo apt update
sudo apt install -y python3.12 python3.12-venv python3-pip git curl build-essential libssl-dev libffi-dev python3-dev libjpeg-dev zlib1g-dev
```

For Docker sandbox (optional):
```bash
sudo apt install -y docker.io
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker $USER
# Log out and back in for group changes
```

### Clone Repository

```bash
git clone https://github.com/FoundationAgents/OpenManus.git
cd OpenManus
```

### Method 1: Using pip (Recommended for simplicity)

```bash
python3.12 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Method 2: Using uv (Faster package management)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.cargo/env  # Add to ~/.bashrc if needed
uv venv --python 3.12
source .venv/bin/activate
uv pip install -r requirements.txt
```

### Browser Automation Setup

To ensure browser automation works correctly and persists across sessions (especially in ephemeral environments like Daytona), use the provided setup script:

```bash
python setup_browsers.py
```

This script installs Chromium into a local `.playwright-browsers` directory within the project, which OpenManus is configured to detect and use automatically.

### Configuration

1. Copy example config:
```bash
cp config/config.example.toml config/config.toml
```

2. Edit `config/config.toml` with your API keys and settings. Example:
```toml
[llm]
model = "gpt-4o"
base_url = "https://api.openai.com/v1"
api_key = "sk-your-api-key-here"
max_tokens = 4096
temperature = 0.0
```

For MCP server, copy and edit:
```bash
cp config/mcp.example.json config/mcp.json
```

## Usage

### Running the Main Agent

The primary way to interact with OpenManus is through the command line.

#### Basic Usage

```bash
python main.py
# Then enter your prompt when prompted
```

#### With Prompt Argument

```bash
python main.py --prompt "Create a Python script to calculate Fibonacci numbers"
```

#### Options

- `--prompt`: Direct prompt input (optional, will prompt if not provided)

### Running MCP Server

For integration with MCP-compatible clients:

```bash
python run_mcp.py
```

Configuration via `config/mcp.json`.

### Running Multi-Agent Flow

For complex tasks requiring multiple agents:

```bash
python run_flow.py
```

Enable data analysis agent in `config/config.toml`:
```toml
[runflow]
use_data_analysis_agent = true
```

### Installed Entry Point (After pip install -e .)

If installed in editable mode:
```bash
pip install -e .
openmanus --prompt "Your task here"
```

### Example Prompts

- Software Development: "Build a Flask web app for a todo list with SQLite database"
- Data Analysis: "Analyze the CSV file and create visualizations"
- Web Automation: "Scrape product prices from example.com"
- General: "Generate a 7-day travel itinerary for Japan"

### Advanced Configuration

To maximize OpenManus's effectiveness, fine-tune the configuration:

- **LLM Settings**: Adjust `temperature` for creativity (higher) vs. precision (lower). Set `max_tokens` based on task complexity.
- **Agent Selection**: Enable specific agents in `config/config.toml` under `[agent]` for tailored capabilities.
- **Tool Customization**: Modify tool parameters in the config to suit your environment.
- **Sandbox Configuration**: For isolated execution, configure Docker settings in the sandbox module.

### Maximizing Usefulness

- **Prompt Engineering**: Use clear, detailed prompts with context. Specify output formats and constraints.
- **Multi-Agent Workflows**: For complex tasks, use `run_flow.py` to leverage multiple agents.
- **Integration**: Connect via MCP server for seamless tool calling in other applications.
- **Resource Management**: Monitor token usage and costs; use local models via Ollama for cost savings.
- **Iterative Refinement**: Start with basic prompts and refine based on outputs.
- **Security**: Use sandbox for untrusted code execution to prevent system risks.

### Troubleshooting

- **Installation Issues**: Ensure Python 3.12+ and all dependencies. Use virtual environments.
- **API Errors**: Verify API keys and endpoints in config.
- **Performance**: Reduce `max_tokens` or use faster models if slow.
- **Tool Failures**: Check system permissions for file operations, browser automation.
- **Logs**: Enable logging in config for debugging.

### Additional Examples

- **Code Review**: "Review the code in main.py for potential bugs"
- **Automation Script**: "Write a bash script to automate daily backups"
- **Research Task**: "Summarize recent papers on AI agents"
- **Interactive Session**: "Help me debug this error: [paste error]"

## Project Structure

- `app/agent/`: Agent implementations (Manus, SWE, DataAnalysis, etc.)
- `app/tool/`: Tool collections and implementations
- `app/mcp/`: MCP protocol handling
- `app/sandbox/`: Isolated execution environment
- `config/`: Configuration files
- `examples/`: Usage examples and benchmarks
- `tests/`: Test suites

## Contributing

We welcome contributions! Please run pre-commit checks before PRs:

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

## License

MIT License

## Citation

```bibtex
@misc{openmanus2025,
  author = {Xinbin Liang and Jinyu Xiang and Zhaoyang Yu and Jiayi Zhang and Sirui Hong and Sheng Fan and Xiao Tang and Bang Liu and Yuyu Luo and Chenglin Wu},
  title = {OpenManus: An open-source framework for building general AI agents},
  year = {2025},
  publisher = {Zenodo},
  doi = {10.5281/zenodo.15186407},
  url = {https://doi.org/10.5281/zenodo.15186407},
}
