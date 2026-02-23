# Feedback Learning Strategy for SparkAgent

## Overview
This document outlines how to use the `sparkagent_feedback` table to continuously improve the AI agent's recommendations and create a superior user experience.

---

## 🎯 Feedback Data Schema

| Field | Purpose | Learning Use |
|-------|---------|--------------|
| `query_text` | User's original question | Identify common queries, misunderstood intents |
| `query_intent` | Detected intent (analyze_app, show_bad_apps, etc.) | Track intent detection accuracy |
| `actual_result_generated` | Full response shown to user | Find patterns in unhelpful responses |
| `feedback_type` | HELPFUL / NOT_HELPFUL / PARTIAL | Overall quality metric |
| `feedback_comment` | User's reason (too generic, wrong, etc.) | Specific improvement signals |
| `source_*_count` | Kusto/RAG/LLM usage | Track which sources produce best results |

---

## 🔄 Learning Loop (3 Tiers)

### TIER 1: Real-Time Response Adaptation (Immediate)
**When:** During each user interaction  
**How:** Query feedback table before generating response

```python
# Before generating response, check if similar query had negative feedback
similar_feedback = kusto.query(f"""
    sparkagent_feedback
    | where query_text contains '{key_terms}'
    | where feedback_type in ('NOT_HELPFUL', 'PARTIAL')
    | top 5 by timestamp desc
    | project feedback_comment, actual_result_generated
""")

# Adjust prompt: "Previous users found responses like X unhelpful because Y. Avoid that pattern."
```

**Expected Impact:** Prevent repeating known bad responses

---

### TIER 2: Weekly RAG Knowledge Enhancement (Batch)
**When:** Weekly job (every Sunday)  
**How:** Extract validated knowledge from HELPFUL feedback, add to RAG index

```kql
// Find consistently helpful responses (80%+ helpful rate)
sparkagent_feedback
| where timestamp > ago(7d)
| summarize 
    helpful = countif(feedback_type == "HELPFUL"),
    total = count(),
    sample_response = any(actual_result_generated),
    sample_query = any(query_text)
    by application_id, query_intent
| where total >= 3 and (helpful * 100.0 / total) >= 80
| project application_id, query_intent, sample_query, sample_response
```

**Action:**
1. Extract these high-quality Q&A pairs
2. Format as synthetic documents
3. Ingest into RAG vector store with metadata: `source:validated_qa, confidence:high`
4. Future similar queries will retrieve these proven answers

**Expected Impact:** Validated responses become searchable knowledge

---

### TIER 3: Prompt Engineering & Fine-Tuning (Monthly)
**When:** Monthly review  
**How:** Analyze failure patterns, update system prompts

#### 3a. Identify Systematic Issues
```kql
// What types of questions get "NOT HELPFUL" most often?
sparkagent_feedback
| where timestamp > ago(30d) and feedback_type == "NOT_HELPFUL"
| extend reason = extract(@"reason:\s*([^|]+)", 1, feedback_comment)
| summarize count() by query_intent, reason
| order by count_ desc
```

**Common Patterns & Fixes:**

| Pattern | Fix |
|---------|-----|
| LLM responses marked "too generic" | Update `SPARK_ADVISOR_SYSTEM_PROMPT` with rule: "Never give generic advice like 'add more executors'. Always cite specific metrics." |
| RAG responses marked "wrong for my case" | Improve RAG metadata filtering (e.g., batch vs streaming, NEE vs standard) |
| Kusto responses marked "already knew" | They want actionable fixes, not diagnostic info → Update Judge to prioritize action-oriented recs |

#### 3b. Update System Prompts
```python
# Add feedback-driven rules to SPARK_ADVISOR_SYSTEM_PROMPT
LEARNED_RULES = """
LEARNED FROM FEEDBACK (updated 2026-02-22):
- Rule 47: When recommending executor changes, ALWAYS cite the current 
  Executor Efficiency metric from Kusto. Users found generic advice unhelpful.
  
- Rule 48: For "partial" feedback on GC issues, users want specific JVM flags,
  not just "reduce GC overhead". Include exact -XX:G1HeapRegionSize values.
  
- Rule 49: When Kusto shows "No issues", users STILL want optimization ideas.
  Offer: "Would you like general best practices relevant to your workload type?"
"""
```

#### 3c. Fine-Tuning (Advanced)
If you accumulate 500+ high-quality feedback examples:
1. Export validated Q&A pairs with feedback
2. Format as training data:
   ```json
   {
     "messages": [
       {"role": "system", "content": "You are a Fabric Spark advisor..."},
       {"role": "user", "content": "{query_text}"},
       {"role": "assistant", "content": "{actual_result_generated}"},
       {"role": "user", "content": "HELPFUL - exactly what I needed"}
     ]
   }
   ```
3. Fine-tune GPT-4o on Azure OpenAI
4. Deploy custom model for sparkagent

**Expected Impact:** Model learns your specific patterns, reduces reliance on prompts

---

## 📊 Key Metrics to Track

### 1. Overall Helpfulness Rate
```kql
sparkagent_feedback
| where timestamp > ago(7d)
| summarize 
    helpful = countif(feedback_type == "HELPFUL"),
    total = count()
| extend rate = round(100.0 * helpful / total, 1)
```
**Target:** 70%+ helpful rate

### 2. Source Effectiveness
```kql
sparkagent_feedback
| where timestamp > ago(7d)
| extend primary_source = case(
    source_kusto_count > 0, "kusto",
    source_rag_count > 0, "rag",
    source_llm_count > 0, "llm",
    "unknown"
)
| summarize 
    helpful_rate = 100.0 * countif(feedback_type == "HELPFUL") / count(),
    total = count()
    by primary_source
| order by helpful_rate desc
```
**Expected:** Kusto > RAG > LLM (validates tier strategy)

### 3. Intent Detection Accuracy
```kql
// Users who immediately provide feedback likely had wrong intent detected
sparkagent_feedback
| where timestamp > ago(7d)
| extend quick_feedback = timestamp - lag(timestamp, 1) < 10s
| where quick_feedback and feedback_type == "NOT_HELPFUL"
| summarize count() by query_intent, feedback_comment
```
**Action:** If high, improve intent detection regex

---

## 🚀 Implementation Priority

### Week 1: Basic Capture ✅
- [x] Create `sparkagent_feedback` table
- [x] Implement feedback detection in UI
- [x] Write feedback to Kusto

### Week 2: Real-Time Learning (TIER 1)
- [ ] Add pre-query feedback check in orchestrator
- [ ] If similar query had negative feedback, adjust prompt
- [ ] Example: "Note: Previous users found responses mentioning X unhelpful"

### Week 3: Dashboard
- [ ] Create Power BI dashboard with key metrics
- [ ] Track helpfulness rate over time
- [ ] Identify top "NOT HELPFUL" patterns

### Month 2: RAG Enhancement (TIER 2)
- [ ] Weekly job to extract validated Q&A pairs
- [ ] Ingest into RAG with `source:feedback` metadata
- [ ] Test retrieval of feedback-based knowledge

### Month 3: Prompt Tuning (TIER 3)
- [ ] Monthly review of failure patterns
- [ ] Update system prompts with learned rules
- [ ] A/B test new prompt vs old (track feedback rates)

---

## 🎨 Advanced: Personalization

If you want to take it further:

### Per-User Learning
```kql
// Track what each user finds helpful
sparkagent_feedback
| where session_id == "user_xyz"
| summarize 
    loves_kusto = countif(source_kusto_count > 0 and feedback_type == "HELPFUL"),
    hates_llm = countif(source_llm_count > 0 and feedback_type == "NOT_HELPFUL")
| extend preference = case(
    loves_kusto > 3, "data_driven",  // Prefers hard data
    hates_llm > 3, "skeptical",      // Distrusts AI
    "balanced"
)
```

**Action:** Store `user_preference` in session, adjust tone:
- `data_driven` → Always lead with Kusto metrics, minimize LLM
- `skeptical` → Always show AI WARNING blocks, very conservative
- `balanced` → Default behavior

### Workload-Specific Learning
```kql
// What works for streaming vs batch jobs?
sparkagent_feedback
| join kind=inner (
    sparklens_metadata | project application_id, job_type = iff(workload_type == "streaming", "streaming", "batch")
) on application_id
| summarize 
    helpful_rate = 100.0 * countif(feedback_type == "HELPFUL") / count(),
    common_complaints = make_set(feedback_comment)
    by job_type, query_intent
```

**Action:** Maintain separate prompt addendums for streaming vs batch

---

## 💡 Best Practices

1. **Never Ignore PARTIAL Feedback**  
   - "PARTIAL" often contains the most specific, actionable improvement ideas
   - Extract `what was missing` and prioritize those gaps

2. **Track Velocity, Not Just Rate**  
   - If helpfulness rate stays at 70% but query volume 3x's → you're winning
   - Users come back when it's helpful

3. **Seasonal Patterns**  
   - Month-end: More queries about cost optimization
   - Post-release: More queries about new Fabric features
   - Adjust RAG index refresh to match

4. **Close the Loop**  
   - When you fix a common complaint, announce it in the UI
   - "📢 Based on your feedback, we now show specific JVM flags for GC issues!"

5. **Feedback on Feedback**  
   - Occasionally ask: "Was the feedback collection helpful?" (meta!)
   - Adjust the feedback prompt itself if it's too burdensome

---

## 🔮 Future Enhancements

1. **Active Learning**  
   - When confidence is low, explicitly ask: "I'm unsure. Does this help?"
   - Prioritize labeling uncertain responses

2. **Multi-turn Feedback**  
   - After "NOT HELPFUL", ask: "What would make this better?"
   - Capture desired response format

3. **Comparative Feedback**  
   - Show 2 possible answers, ask: "Which is more helpful?"
   - A/B test prompt variations

4. **Integration with Support Tickets**  
   - If user escalates to human support, link ticket to feedback
   - Learn what types of queries need human intervention

---

## 📈 Success Metrics (6 Months)

| Metric | Baseline | Target | Stretch Goal |
|--------|----------|--------|--------------|
| Helpfulness Rate | 50% | 70% | 85% |
| Avg Feedback Time | 30s | 10s | 5s |
| Repeat Users (weekly) | 10 | 50 | 100 |
| LLM Fallback Rate | 40% | 20% | 10% |
| Query Resolution Time | 45s | 15s | 8s |

**When you hit these targets, your AI agent becomes the #1 tool for Spark optimization on Fabric.**
