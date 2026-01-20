---

# ConvFinQA Analysis Report: A Multiple Agent Ablation Study

## Technical note:

Project uses open AI API. Make sure to create a .env file.  
`echo "OPENAI_API_KEY=your_key_here" > .env`

To run the interactive analyst: `uv run python -m src.main <record_id> --condition <id>`. 
Example:  `uv run python -m src.main "Single_JKHY/2009/page_28.pdf-3" --condition 1`

To run the batch evaluation suite: `uv run python scripts/evaluate.py`.  
Defaults to 15 samples (15 samples, 11 conditions, ~4 turns per sample = ~660 calls), change `SAMPLE` variable in `evaluate.py` to reduce this to 1. 

## 1. Introduction:

This report details the development and evaluation of an agentic framework designed to solve the ConvFinQA challenge. Following an initial exploratory phase to establish prompt-engineering baselines and validate data formatting decisions, I conducted a rigorous 11-condition ablation study to identify the optimal configuration for complex financial reasoning. This study focused on isolating the impact of two key areas:
1.  **Intelligence Tiers:** Evaluating the performance curve across model classes (GPT mini vs. GPT 5.2) and varying levels of internal reasoning effort (Medium and High).
2.  **Architectural Orchestration:** Measuring the performance delta between a Single-Pass simple prompt response, a Modular agent with a Planner and Analyst, and a Reflective agent with a Planner, Analyst and added Reviewer.

The goal of this project was to provide some direction and insight on the best architecture for the task at hand, using rigorous evaluation to go beyond a simple accuracy measure. 

---

## Method

### 1. Data Formatting

#### Long-Context Prompting:

Each record in the ConvFinQA dataset typically falls within the 2k–3k token range, which fits comfortably within the context windows of modern reasoning models. With this in mind I chose to feed this entire context as part of the prompt for the QA task over implementing a retrieval setup.

#### Markdown Hypothesis:
- Decision: 
  - After deciding to use long-context prompting and reviewing the ConvFinQA data, I opted to present the table key–value pairs as a Markdown table instead of native JSON. 

- The rationale:
  - Financial tables can be extremely dense and long, in JSON form it can become difficult to extract values buried in nested key-value pairs, headers could be hundreds of tokens away from values potentially stretching the attention mechanism. In Markdown, they sit side-by-side, with columns vertically aligned by pipes. This allows a planner or thinking state to use this visual grid and identify values using natural language e.g. "The 1st value of the third column". My thinking was that this will allow for richer thinking and planning from the baseline/agents.

To implememnt this I created a `utils/parser.py` and validated it using a 2-tier pipeline to ensure zero loss of data during conversion:
1. **Programmatic Tier:** Fast Python/Regex screening for pipe consistency.
2. **LLM Tier (Semantic Auditor):** A `gpt-5-mini` instance run on flagged failures from the programmatic tier. I also added some false negative defense by auditing a random 5% sample of the successful programmatic checks. 

This two-tier pipeline confirmed no strict data loss. However, it did reveal a minor precision artifact (e.g., -9.0 being simplified to -9). This didnt impact the mathematical logic of the study, but in a production environment I would review ways to mitigate these errors.


### 2. Constraints

#### Deterministic Math Execution:

- Decision:
  - Provided a python maths tool (`src/agent/tools.py`) to ensure deterministic outputs.
- Rationale:
  - LLMs excel at formula creation, but struggle when it comes to actually performing calculations, the results for this QA task must be deterministic so we need to prohibit the LLM from performing any calculations itself. Adding a maths tool lets the LLM create the formula and act as a translator.

#### Pydantic

- Decision:
  - Every state in the pipeline (Planner, Analyst, Reviewer) was bound to a strict Pydantic schema using the OpenAI responses.parse interface. 
- The Rationale:
  - In a multi turn agent enforcing correct formatting from the LLM for the next stage is essential in creating a reliable agent. It reduces parsing errors and also increases token efficiency.


### 3. Hierarchical XML Prompts
- Decision:
  - I moved from flat text instructions to a structured XML tagging system (<persona>, <operational_directives>, <output_contract>).
- Rationale:
  - Context Separation: Financial contexts (tables/text) can be very dense. Using XML tags helps the model clearly distinguish between the data it’s analysing and the rules it must follow.
  - Modular Prompting: This structure allowed me to easily swap directives between the Baseline and Agentic versions while keeping the core persona consistent.

#### Prompt Engineering:

Before moving onto the creation of the full agent (planner, analyst, reviewer) I  performed an initial eval on a baseline single pass prompt -> response using a prompt generated by an LLM. I then used a human-in-the-loop approach to engineer the prompt based on error analysis from a few small sample runs. I found four common failures during this.

- Scaling issues: 
  - Initial runs showed the model converting values like "10.5 million" to the full integer (10,500,000). Since the dataset expects the shorthand provided in the source table, I added a directive to use numbers exactly as they appear.
  
- Name Error failures: 
  - Had many cases of Name Error failures due to the model producing variable names that the maths tool couldnt use. To prevent this, I added instructions to try and force every value in the expression to be a literal float or an ans_N variable.

- Model performing calculations:
  -  I observed cases of the model performing calculations in the reasoning field and then outputting a static number. Again added instruction via a role to force the model to define the formula.


Following implementation of this prompt engineering our baseline single prompt agent went from a ~40% accuracy to roughly %80.  
Doing a quick investigation into the turn based accuracy I found that the initial model fell from 90% accuracy to ~65% by turn 3, this seemed to be a good indication that a more sophisticated agent might achieve better turn by turn accuracy.

---

### 4. Ablation Study & Production Refactoring

To find the optimal production configuration, I conducted an iterative architectural evaluation across 11 conditions. While structured like a reverse ablation study, it followed an additive 'staircase' approach with the aim of finding the point at which increased reasoning and architectural complexity stopped yielding an accuracy increase.

### The Experimental Matrix
I mapped three tiers of intelligence against three tiers of orchestration:
1.  **Efficiency Tier (gpt-5-mini):** Optimised for cost and extraction speed.
2.  **Standard Tier (gpt-5.2 Medium):** Balancing reasoning depth with performance.
3.  **Ceiling Tier (gpt-5.2 High):** Testing the maximum reasoning capability of the system.

**Scientific Controls:**
*   **Deterministic Sampling:** Every condition was evaluated against the exact same 15 records using a fixed `Random Seed (42)`.
*   **Separated Architecture:** Where possible I aimed to change one varaible per condition so as to maintain interpretability of the results. Ultimately I set up three groups of conditions to make sure that each addition to the agent could be measured.

| Group | Cond | Name | Rationale |
| :--- | :---: | :--- | :--- |
| **Baselines** | 1 | JSON Baseline (Mini) | GPT 5 mini with JSON as a baseline |
| | 2 | MD Baseline (Mini) | GPT 5 mini with markdown as a baseline |
| | 3 | JSON Baseline (Med) | GPT 5.2 med thinking effort with JSON as a baseline |
| | 4 | MD Baseline (Med) | GPT 5.2 med thinking effort with markdown as a baseline |
| | 5 | MD Baseline (High) |  GPT 5.2 High thinking effort with JSON as a baseline |
| **Modular** | 6 | Modular (Mini) | Planner/Analyst setup on GPT 5 mini, markdown |
| | 7 | Modular (Med) | Planner/Analyst setup on GPT 5.2, markdown, med effort |
| | 8 | Modular (High) | Planner/Analyst setup on GPT 5.2, markdown, high effort |
| **Reflective**| 9 | Reflect (Mini) | Full agent Planner/Analyst/Reviewer setup on GPT 5 mini, markdown |
| | 10 | Reflect (Med) | Full agent Planner/Analyst/Reviewer setup on GPT 5.2, markdown, med effort |
| | 11 | Reflect (High) | Full agent Planner/Analyst/Reviewer setup on GPT 5.2, markdown, high effort |

### Group Rationales

#### 1. Baselines (1–5):
- Aim of this group, establish a baseline and learn whether changing the data format (JSON to Markdown) or increasing the model tier actually helps the model.

#### 2. Modular Architecture (6–8):
- This group tested the ROI of separating the single prompt into two distinct states, a planner/analyst. This group would tell me whether this increased complexity would aid the turn 3 accuracy decay.

#### 3. Reflective Loops (9–11):
- The final group introduced a Reviewer state to identify and fix errors. This group represents the highest token cost and latency. The goal was to determine if the accuracy boost of self-correction justified the increase in API calls, particularly for the smaller "mini" tier.
&nbsp;


### The Production-Grade Refactor
As the complexity of the study grew, I migrated the codebase from a a few flat execution scripts to a modular, Production-Grade Architecture. This refactor was  done with alot of LLM guidance:

*   Separation of Concerns:
    *    I decoupled the system into distinct modules: `ReasoningClient` (API logic), `ContextBuilder` (Data prep), `MathTool` (Execution), and `ConvFinQAManager` (Orchestration).
*   Pydantic:
    *    Using Pydantic, I enforced strict schemas for all agent hand-offs. This eliminated parsing errors and ensured that the Analyst always received valid "Coordinates of Truth" from the Planner.
*   Communication and Logging:
    *    I implemented a dual-stream logging system. While the console provided high-level progress via `Rich`, the background `evaluation.log` captured raw reasoning traces. This was the "key" for error analysis in Section 5.
*   Error Handling:
    *    I implemented fallback logic for model or parsing failures ensuring a single malformed response wouldn't crash a long-running evaluation batch.

Following refactoring I performed a quick initial test of the evaluator on the final condition (11) to make sure that each state was working correctly and took this testing opportunity to do some small prompt engineering on the new states prior to running the full evaluate script.

---

### 5. Error Analysis:

The most significant finding during development was discovering a Positive Bias Conflict in the reviwer. 

#### Self Sabotage
During the testing of Condition 11 (Reflect High), I saw occasions where the  Reviewer state degraded accuracy. Using the raw reasoning traces from the `ReasoningClient`, I found the following scenario:

1.  **Analyst State:** Corrected for sign integrity instructions and generated the mathematically correct negative expression (e.g. `ans_0 / ans_1 = -0.5`).
2.  **Auditor State:** Flagged the negative sign as a failure. Despite the XML instructions, the Reviewer seemed to have a bias where a "difference" or "decrease" should be described as a positive.
3.  **Self-Correction:** The Analyst, deferring to the Auditor’s feedback, "fixed" the expression to a positive value, turning a successful result into an error.

Despite a quick round of prompt engineering to fix this, the reviewer consistently tried to correct negative numbers to positive. This is something that we could change for next time by introducing dynamic prompting depending on whether a negative sign has been produced in any of the ans_N results.


---

### 6. Results



![](./notebooks/visualisations/accuracy_by_condition.png)

 
Figure 1: Bar chart to show overall accuracy of all conditions across all turns.

### Key Takeaways
*   Condition 1 (gpt-5 mini - native json single prompt) achieved the highest accuracy of 83%
*   Adding a planner/analyst to gpt-mini (cond 5) caused a drastic reduction in accuracy - ~64%.
*   Adding back in reflection seemed to fix some of this lost accuracy, but had little to no effect on the gpt-5.2 Med and High thinking effort conditions.
*   Increased complexity and model tier did not result in noticeable overall increases to accuracy.

&nbsp;

---

&nbsp;
&nbsp;

![](./notebooks/visualisations/error_taxonomy.png)

Figure 2: Error taxonomy of the failed turns

### Key Takeaways
* Scale errors were prevalent throughout each condition.
* Very little hallucinations.  Interestingly hallucinations only occured in the high reasoning effort conditions

---

&nbsp;

![](./notebooks/visualisations/reflection_correction.png)

Figure 2: Reviewer correction rate for each reflection condition.

### Key Takeaways
*   **Best Error Correction:** `9. Reflect (Mini)` with a **68.4% recovery rate**, successfully catching errors that other architectures missed.

---

&nbsp;

![](./notebooks/visualisations/performance_stability.png)

Figure 2: By turn accuracy for the best performing models.

### Key Takeaways
*   Increasing architecture complexity and model tier did not improve the chain decay observed in the initial baseline.


---

### --- Category Performance ---
```
             mean   std    max
Category                      
Baseline    76.19  4.89  82.54
Modular     72.49  7.83  77.78
Reflective  73.54  1.83  74.60

--- Tier Performance ---
Tier
gpt-5.2 (High Thinking)      75.133333
gpt-5-mini                   75.000000
gpt-5.2 (Medium Thinking)    73.412500
Name: accuracy, dtype: float64

Correlation between Scale Errors and Accuracy: -0.96
```
*   **Intelligence Tier Comparison:** The gap between **GPT-5-Mini (75.0%)** and **GPT-5.2 High Thinking (75.1%)** is negligible. Paying for High Thinking offers diminishing returns compared to an optimised Mini baseline.



---

### 7. Further work

#### Try non-DSL method for python expression
The DSL method of python expression seems to have introduced many errors - it would be good to give the LLM freedome to define expressions how it wishes and work around that rather than conforming it to a set framework. 

#### Full scale evaluation
This study was run on a sample of just 15 records per condition (~60 turns) as such the reliability of the results is low. Evaluation costs constrained me from running a full evaluation. If i did have the means to run the full suite I'd add the following prior to doing so:

#### Add a Scale Verification

Since there is a near perfect correlation between scale errors and accuracy (-0.96), implementing a more rigorous process for handling these errors will yield the greatest ROI.

#### Transition to Asymmetric Agentic Architecture

The data indicates that splitting the Planner and Analyst into separate roles caused accuracy to drop from 76.2% to 72.5%. However, the analysis on reflection proved this layer successfully clawed back lost performance by catching errors that simpler models missed. With this in mind we can take the best performing baseline model and simply add the best performing reflective layer to it. GPT Mini JSON/Markdown  baseline + GPT Mini Reflection. 

---
