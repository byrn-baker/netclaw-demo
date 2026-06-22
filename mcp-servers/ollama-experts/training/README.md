# Fine-Tuning Domain Expert Models for NetClaw

This guide walks you through creating domain-specific network engineering models, from beginner (system prompts) to advanced (full QLoRA fine-tuning).

## Level 1: Modelfile System Prompts (Start Here)

**Time required**: 5 minutes
**Hardware**: Any machine running Ollama
**ML knowledge needed**: None

This is the fastest path to a working domain expert. You take an existing model and give it a specialized identity via a system prompt.

### Create your first expert

```bash
# From the modelfiles/ directory
cd mcp-servers/ollama-experts/modelfiles/

# Create the OSPF expert
ollama create netclaw-ospf -f Modelfile.ospf

# Create the BGP expert
ollama create netclaw-bgp -f Modelfile.bgp

# Create the RFC validator
ollama create netclaw-rfc-design -f Modelfile.rfc-design

# Create the general FRR config generator
ollama create netclaw-frr-codegen -f Modelfile.frr-codegen
```

### Test it

```bash
ollama run netclaw-ospf "Generate OSPF config for router P1 with router-id 10.0.0.1, interfaces eth1 (10.1.1.1/30 area 0) and eth2 (10.1.2.1/30 area 0), loopback 10.0.0.1/32"
```

### Tips for better system prompts

1. **Be specific about output format** — "Output ONLY valid FRR config" prevents chatty responses
2. **Include syntax examples** — Models follow patterns they've seen in the prompt
3. **State rules as constraints** — "Never do X" is clearer than "Try to avoid X"
4. **Reference RFCs** — Even if the model doesn't know the RFC content, it anchors the response style
5. **Set low temperature** (0.1) for config generation — you want deterministic, correct output

---

## Level 2: RAG-Augmented Prompts (Intermediate)

**Time required**: 1-2 hours to set up
**Hardware**: Any machine running Ollama
**ML knowledge needed**: None (just file organization)

Instead of cramming everything into the system prompt, dynamically inject relevant RFC sections and config examples based on the specific task.

### How it works

The MCP server's prompt builder can include relevant context:

```python
# In server.py, the prompt construction could be enhanced:
def get_ospf_context(task: str) -> str:
    """Select relevant RFC sections based on task keywords."""
    context_chunks = []
    if "area" in task.lower():
        context_chunks.append(load_chunk("rfc2328_section3_areas.txt"))
    if "authentication" in task.lower():
        context_chunks.append(load_chunk("rfc5709_ospf_auth.txt"))
    if "stub" in task.lower() or "nssa" in task.lower():
        context_chunks.append(load_chunk("rfc3101_nssa.txt"))
    return "\n---\n".join(context_chunks)
```

### Organize your knowledge base

```
training/
  knowledge/
    ospf/
      rfc2328_area_design.txt      # Extracted relevant sections
      rfc2328_lsa_types.txt
      rfc5340_ospfv3_differences.txt
      frr_ospf_examples.txt         # Validated config examples
    bgp/
      rfc4271_path_selection.txt
      rfc4456_route_reflection.txt
      frr_bgp_examples.txt
    general/
      frr_syntax_reference.txt
      common_mistakes.txt
```

### Key advantage

RAG keeps the system prompt small (fast inference) while giving the model access to precise, authoritative content when needed. You can update the knowledge base without retraining.

---

## Level 3: QLoRA Fine-Tuning (Advanced)

**Time required**: 4-8 hours (including training)
**Hardware**: NVIDIA GPU with 16GB+ VRAM (RTX 3090, 4090, A100)
**ML knowledge needed**: Basic Python, comfortable with command line

This creates a truly specialized model that has network engineering knowledge baked into its weights, not just prompted.

### Prerequisites

```bash
# Install Unsloth (recommended — 2x faster than standard training)
pip install "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git"
pip install --no-deps trl peft accelerate bitsandbytes

# Or use the Docker approach (easier, no dependency conflicts):
# See https://finetune.rogueai.de/ for a containerized pipeline
```

### Step 1: Prepare Training Data

Training data is instruction-tuning format: question/answer pairs in JSONL.

```jsonl
{"instruction": "Generate FRR OSPF configuration for a P router", "input": "hostname: P1, router-id: 10.0.0.1, interfaces: eth1 (10.1.1.1/30, area 0), eth2 (10.1.2.1/30, area 0), lo (10.0.0.1/32, area 0)", "output": "router ospf\n ospf router-id 10.0.0.1\n passive-interface lo\n!\ninterface lo\n ip ospf area 0.0.0.0\n!\ninterface eth1\n ip ospf area 0.0.0.0\n ip ospf network point-to-point\n!\ninterface eth2\n ip ospf area 0.0.0.0\n ip ospf network point-to-point\n!"}
{"instruction": "What OSPF LSA types would you expect to see on an ABR?", "input": "", "output": "An ABR generates and receives all LSA types 1-5:\n- Type 1 (Router LSA): Generated for each area it belongs to\n- Type 2 (Network LSA): Generated if DR on multi-access segments\n- Type 3 (Summary LSA): Generated to advertise inter-area routes\n- Type 4 (ASBR Summary): Generated to advertise ASBR reachability\n- Type 5 (External LSA): Received and flooded (not generated unless also ASBR)"}
```

You need **50-200 high-quality examples** per domain. Sources:
- Write them manually from your CCIE knowledge
- Generate from validated lab configs (your ContainerLab outputs)
- Extract from FRR documentation and adapt
- Derive from RFC text (paraphrase, don't copy verbatim)

### Step 2: Train with Unsloth

```python
from unsloth import FastLanguageModel
from trl import SFTTrainer
from datasets import load_dataset

# Load base model in 4-bit
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="deepseek-ai/deepseek-coder-6.7b-instruct",
    max_seq_length=4096,
    load_in_4bit=True,
)

# Add LoRA adapters
model = FastLanguageModel.get_peft_model(
    model,
    r=16,              # LoRA rank (higher = more capacity, more VRAM)
    lora_alpha=32,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
    lora_dropout=0.05,
)

# Load dataset
dataset = load_dataset("json", data_files="datasets/ospf-examples.jsonl")

# Train
trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=dataset["train"],
    max_seq_length=4096,
    dataset_text_field="text",  # or use formatting_func
    args=TrainingArguments(
        output_dir="./output-ospf",
        num_train_epochs=3,
        per_device_train_batch_size=2,
        learning_rate=2e-4,
        warmup_steps=10,
        logging_steps=10,
        save_steps=100,
    ),
)
trainer.train()
```

### Step 3: Merge and Export to GGUF

```python
# Merge LoRA into base model
model.save_pretrained_merged("./merged-ospf", tokenizer)

# Convert to GGUF (requires llama.cpp)
# Option A: Unsloth's built-in export
model.save_pretrained_gguf(
    "./gguf-ospf",
    tokenizer,
    quantization_method="q4_k_m",  # Good quality/size balance
)
```

Or manually with llama.cpp:
```bash
python llama.cpp/convert_hf_to_gguf.py ./merged-ospf --outtype q4_k_m --outfile netclaw-ospf.gguf
```

### Step 4: Import to Ollama

Create a Modelfile for the fine-tuned model:

```
FROM ./netclaw-ospf.gguf

PARAMETER temperature 0.1
PARAMETER top_p 0.9
PARAMETER num_predict 4096

TEMPLATE """{{ if .System }}<|system|>
{{ .System }}<|end|>
{{ end }}{{ if .Prompt }}<|user|>
{{ .Prompt }}<|end|>
{{ end }}<|assistant|>
{{ .Response }}<|end|>"""

SYSTEM """You are NetClaw's OSPF expert. Generate valid FRR configurations."""
```

```bash
ollama create netclaw-ospf-ft -f Modelfile.ospf-finetuned
ollama run netclaw-ospf-ft "Generate OSPF config for P1..."
```

### Step 5: Benchmark

Compare your fine-tuned model against the system-prompt-only version:

```bash
# Run the same 20 test prompts against both
python training/scripts/benchmark.py \
  --model-a netclaw-ospf \
  --model-b netclaw-ospf-ft \
  --test-file training/datasets/ospf-test.jsonl
```

Score on:
- **Syntax validity** — Does it parse as valid FRR config?
- **Completeness** — Are all requested elements present?
- **Correctness** — Does it follow RFC rules?
- **Conciseness** — No extraneous output?

---

## Recommended Learning Path

1. **Week 1**: Create all 4 Modelfiles, test with the MCP server
2. **Week 2**: Build a RAG knowledge base from RFCs and FRR docs
3. **Week 3**: Curate 50 training examples per domain from your lab work
4. **Week 4**: Run your first QLoRA fine-tune, benchmark against Level 1

## Resources

- [Unsloth Documentation](https://unsloth.ai/docs) — Fastest fine-tuning framework
- [Ollama Modelfile Reference](https://github.com/ollama/ollama/blob/main/docs/modelfile.md)
- [GGUF Format Spec](https://github.com/ggerganov/ggml/blob/master/docs/gguf.md)
- [LoRA Paper](https://arxiv.org/abs/2106.09685) — Understanding the technique
- [QLoRA Paper](https://arxiv.org/abs/2305.14314) — 4-bit quantized training
