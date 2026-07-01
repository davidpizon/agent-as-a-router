# ACROUTER_CHEAP_CHAIN: Purpose and Distinction from Cost Configuration

## The Key Distinction

While ACRouter has model costs configured in `data/matrices/phase1_id/model_pricing.json`, the **ACROUTER_CHEAP_CHAIN** serves a **different but complementary purpose**:

### Cost Configuration
- **What:** Stores the per-token pricing for all available models (input, output, cache reads/writes)
- **Used for:** Calculating total API costs for audit/analytics/billing
- **Granularity:** Per-token accuracy (USD per 1M tokens)
- **Scope:** All models in the system

### ACROUTER_CHEAP_CHAIN
- **What:** An **ordered fallback sequence** of models to try for routing decisions themselves
- **Used for:** Selecting which model to use **to run the ACRouter routing logic**
- **Granularity:** Coarse ordering (not exact token counts)
- **Scope:** Only a subset of models designated as suitable for routing

## Why Both Are Necessary

### The Two-Level Cost Optimization Problem

**Level 1: Cost of Running the Router Itself**
- The router needs a model to make routing decisions (e.g., "Which model should handle this task?")
- This requires running the router's decision-making prompt through an LLM
- The router model is different from the backend models being routed to
- **Strategy:** Use the cheapest possible model for the router to minimize routing overhead
- **Implementation:** ACROUTER_CHEAP_CHAIN specifies candidates; router selects the cheapest one

**Level 2: Cost of Backend Task Execution**
- Once the router decides which backend model to use, that model must run the actual task
- The backend model should be selected based on task characteristics and learned performance
- Cost data is used to calculate total API spend for the selected backend model
- **Strategy:** Router observes which backend models perform best for different task dimensions
- **Implementation:** Model pricing data enables cost-aware backend selection via cheap chain escalation

### Code Evidence

**Router Model Selection (Rust):**
```rust
fn select_router_model(candidates: &[Candidate], preferred: Option<&str>) -> Option<String> {
    candidates
        .iter()
        .min_by(|left, right| {
            let left_cost = left.estimated_cost_usd.unwrap_or(f64::INFINITY);
            let right_cost = right.estimated_cost_usd.unwrap_or(f64::INFINITY);
            left_cost.partial_cmp(&right_cost)
        })
        .map(|candidate| candidate.model.clone())
}

// Test: "cheapest_router_model_wins_by_default"
// Confirms: Router selects cheapest model to run routing logic
```

**Backend Model Selection (Python):**
```python
for model in self.cheap_chain:  # Try cheap models first
    attempt = self._attempt(task, model, call_model, verify)
    if attempt.resolved:
        return InferenceDecision(...)  # Task resolved, stop
    cheap_apply_count += int(attempt.apply_ok)

# If cheap chain exhausted, escalate to expensive model
if cheap_apply_count >= self.k:
    attempt = self._attempt(task, self.escalate_to, call_model, verify)
```

## Real-World Example

**Scenario:** Route a coding task with 5,000 input tokens

1. **Pick Router Model (ACROUTER_CHEAP_CHAIN):**
   - Available: `gpt-5.4`, `qwen3.5-plus`, `kimi-k2.5`
   - Costs (1k in + 1k out): $0.017, $0.000771, $0.00029
   - **Router Chooses:** `kimi-k2.5` (cheapest)
   - **Cost:** ~$0.0015 for routing prompt

2. **Router Makes Decision:**
   - Prompt: "Task: [coding problem]. Which model? gpt-5.4, claude-opus, qwen3.5-plus?"
   - Router response: "Task requires complex reasoning → try qwen3.5-plus first"

3. **Try Backend Models (cost-aware cheap chain):**
   - Try 1: `qwen3.5-plus` 
     - Input: 5,000 tokens, Output: 2,000 tokens
     - Cost: `(5000 × 0.11 + 2000 × 0.66) / 1,000,000 = $0.00181`
     - Result: Resolved ✓
   - **Total Cost:** $0.0015 (router) + $0.00181 (backend) = $0.00331

4. **If Qwen Failed:** Router would escalate to expensive model
   - Switch to `claude-opus-4-6`
   - Cost: `(5000 × 5.0 + 2000 × 25.0) / 1,000,000 = $0.0755`
   - Total: $0.0015 + $0.00181 + $0.0755 = $0.0791

## Why This Two-Level Approach?

| Aspect | Reason |
|--------|--------|
| **Separate Router Model** | Router decision logic is cheap; running expensive model just to decide is wasteful |
| **Cheap Chain** | Provides explicit ordering of fallback options; router can reason about escalation strategy |
| **Cost Config** | Enables detailed cost tracking for analytics, billing, and cost-aware escalation thresholds |
| **REWARD_COST_WEIGHT** | In Python, `REWARD_COST_WEIGHT = 0.1` allows optimization of quality vs. cost tradeoffs |
| **Flexibility** | Different deployments can use different cheap chains based on provider availability |

## Configuration Layers

```
ACROUTER_CHEAP_CHAIN = "qwen3.5-plus,kimi-k2.5,gpt-3.5-turbo"  ← Explicit ordering for fallback
                                    ↓
                        Select cheapest (or preferred)
                                    ↓
                            kimi-k2.5 runs routing
                                    ↓
                        Decision: "Try qwen3.5-plus"
                                    ↓
            Model pricing config: { "qwen3.5-plus": { "input_per_1m": 0.11, ... } }
                                    ↓
                        Cost calculation: $0.00181
                                    ↓
                        Task succeeds or escalate
```

## Summary

**ACROUTER_CHEAP_CHAIN is NOT just "the cost-ordered models."** It's a **strategic fallback sequence** for:
1. Selecting the **router model itself** (cost-minimized)
2. Specifying the **backend model escalation policy** (try cheap first, then escalate)

Model costs provide the **metrics** to calculate total spend, while the cheap chain provides the **policy** for when to try which models and when to escalate.
