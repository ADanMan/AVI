# AVI Research Toolkit

Complete toolkit for FinanceBench experiment research.

## 📦 Contents

### Python Modules (`src/`)

#### Transform
- `policy_generator.py` - LLM-based embargo policy generation
- `context_generator.py` - Alternative safe context generation
- `dataset_builder.py` - Complete dataset builder

#### Experiment
- `runner.py` - Full experiment runner (baseline + AVI)
- `evaluator.py` - Automatic metrics evaluation
- `llm_judge.py` - LLM-as-a-Judge evaluation
- `human_review.py` - Human verification interface

#### Visualization
- `results_visualizer.py` - Generate all figures
- `paper_tables.py` - Generate all tables

#### Utils
- `llm_client.py` - Unified LLM client (OpenAI, Cotype)
- `helpers.py` - Helper utilities

### Scripts (`scripts/`)

1. `01_download_financebench.py` - Download dataset from HuggingFace
2. `02_transform_dataset.py` - Transform to AVI format with LLM
3. `03_run_experiment.py` - Run full experiment
4. `04_generate_visualizations.py` - Generate figures and tables
5. `05_export_for_review.py` - Export for human verification

### Configuration (`config/`)

- `llm_prompts.yaml` - All LLM prompts (policy, context, judge)
- `experiment_config.yaml` - Experiment configuration

## 🚀 Usage

This toolkit is designed to be copied into a research repository:

```bash
# Create research repository
./create_avi_research.sh ../avi-research

# Toolkit files will be copied to:
# - avi-research/src/
# - avi-research/scripts/
# - avi-research/config/
```

## 📝 Features

- ✅ Real working code (not templates)
- ✅ LLM-based generation for realistic data
- ✅ Automatic + LLM Judge + Human evaluation
- ✅ Multi-provider LLM support
- ✅ Publication-ready visualizations (300 DPI)
- ✅ Progress bars and logging
- ✅ Modular and extensible

## 📄 License

MIT License
