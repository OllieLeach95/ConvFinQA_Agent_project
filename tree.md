.
├── data
│   ├── convfinqa_dataset.json
│   ├── eval_results_cond_1.json
│   ├── eval_results_cond_10.json
│   ├── eval_results_cond_11.json
│   ├── eval_results_cond_2.json
│   ├── eval_results_cond_3.json
│   ├── eval_results_cond_4.json
│   ├── eval_results_cond_5.json
│   ├── eval_results_cond_6.json
│   ├── eval_results_cond_7.json
│   ├── eval_results_cond_8.json
│   ├── eval_results_cond_9.json
│   ├── parser_failures.json
│   └── v1_baseline_eval_results.json
├── dataset.md
├── figures
│   ├── chat_example.png
│   ├── cli.png
│   ├── conversation_types.png
│   ├── dataset_stats.png
│   ├── exampleq.png
│   ├── figure5.png
│   ├── gpt.png
│   └── tomorolinkedinlogo.png
├── notebooks
│   ├── ablation_analysis.ipynb
│   └── visualisations
│       ├── accuracy_by_condition.png
│       ├── error_taxonomy.png
│       ├── performance_stability.png
│       └── reflection_correction.png
├── pyproject.toml
├── README.md
├── REPORT.md
├── scripts
│   ├── evaluate.py
│   └── validate_parser.py
├── src
│   ├── __init__.py
│   ├── agent
│   │   ├── client.py
│   │   ├── context_builder.py
│   │   ├── orchestrator.py
│   │   ├── prompts
│   │   │   ├── agentic_analyst_system_prompt.xml
│   │   │   ├── baseline_analyst_system_prompt.xml
│   │   │   ├── planner_system_prompt.xml
│   │   │   ├── reviewer_system_prompt.xml
│   │   │   └── validator_system_prompt.xml
│   │   └── tools.py
│   ├── logger.py
│   ├── main.py
│   ├── models
│   │   └── schemas.py
│   └── utils
│       ├── eval_utils.py
│       └── parser.py
└── tree.md

11 directories, 49 files
