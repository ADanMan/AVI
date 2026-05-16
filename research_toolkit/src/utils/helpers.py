"""
Helper utilities for research toolkit
"""

import re
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime


def extract_numbers(text: str) -> List[float]:
    """
    Extract all numbers from text

    Args:
        text: Input text

    Returns:
        List of numbers found

    Example:
        >>> extract_numbers("Revenue was $66.6 billion and COGS $63,078 million")
        [66.6, 63078.0]
    """
    # Pattern for numbers with optional currency symbols and thousands separators
    pattern = r'[\$€£¥]?\s*-?\d{1,3}(?:,\d{3})*(?:\.\d+)?'
    matches = re.findall(pattern, text)

    numbers = []
    for match in matches:
        # Clean: remove currency symbols and commas
        clean = re.sub(r'[\$€£¥,\s]', '', match)
        try:
            numbers.append(float(clean))
        except ValueError:
            continue

    return numbers


def numbers_close(num1: float, num2: float, tolerance: float = 0.1) -> bool:
    """
    Check if two numbers are close (within tolerance %)

    Args:
        num1: First number
        num2: Second number
        tolerance: Relative tolerance (0.1 = 10%)

    Returns:
        True if numbers are within tolerance

    Example:
        >>> numbers_close(100.0, 105.0, tolerance=0.1)
        True
        >>> numbers_close(100.0, 120.0, tolerance=0.1)
        False
    """
    if num1 == 0:
        return abs(num2) < tolerance

    return abs((num2 - num1) / num1) < tolerance


def create_experiment_dir(base_path: str = "data/results") -> Path:
    """
    Create timestamped experiment directory

    Args:
        base_path: Base directory for results

    Returns:
        Path to created directory

    Example:
        >>> create_experiment_dir()
        PosixPath('data/results/experiment_20250113_143022')
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    exp_dir = Path(base_path) / f"experiment_{timestamp}"
    exp_dir.mkdir(parents=True, exist_ok=True)

    # Create subdirectories
    (exp_dir / "figures").mkdir(exist_ok=True)
    (exp_dir / "tables").mkdir(exist_ok=True)

    return exp_dir


def save_json(data: Dict[str, Any], path: str, indent: int = 2):
    """Save data as JSON"""
    with open(path, 'w') as f:
        json.dump(data, f, indent=indent)


def load_json(path: str) -> Dict[str, Any]:
    """Load JSON file"""
    with open(path, 'r') as f:
        return json.load(f)


def load_prompts(config_path: str = "config/llm_prompts.yaml") -> Dict[str, str]:
    """
    Load LLM prompts from YAML config

    Args:
        config_path: Path to prompts YAML file

    Returns:
        Dictionary of prompt templates
    """
    import yaml

    with open(config_path, 'r') as f:
        prompts = yaml.safe_load(f)

    return prompts


def format_prompt(template: str, **kwargs) -> str:
    """
    Format prompt template with variables

    Args:
        template: Prompt template with {placeholders}
        **kwargs: Values for placeholders

    Returns:
        Formatted prompt

    Example:
        >>> template = "Question: {question}\\nCompany: {company}"
        >>> format_prompt(template, question="What is revenue?", company="Boeing")
        "Question: What is revenue?\\nCompany: Boeing"
    """
    return template.format(**kwargs)


def ensure_dir(path: str) -> Path:
    """Ensure directory exists"""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


class ExperimentConfig:
    """Helper for loading experiment configuration"""

    def __init__(self, config_path: str = "config/experiment_config.yaml"):
        import yaml

        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

    def get(self, key: str, default: Any = None) -> Any:
        """Get config value using dot notation"""
        keys = key.split('.')
        value = self.config

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k, default)
            else:
                return default

        return value

    def __getitem__(self, key: str) -> Any:
        return self.get(key)
