# Evaluation Plan

## Research question
Does hybrid signal fusion improve useful review prioritization compared with single-method anomaly detection, while evidence-grounded explanations improve review transparency?

## Metrics
### Detection
- precision
- recall
- F1
- false-positive rate
- PR-AUC where appropriate

### Review usefulness
- precision@K for top review items;
- mean reciprocal rank for planted anomalies;
- number of rows a reviewer must inspect to find a target anomaly;
- estimated review time saved.

### Explainability
- evidence coverage: proportion of explanation claims traceable to structured evidence;
- unsupported-claim rate;
- consistency with actual detector signals.

### System
- analysis latency;
- memory use;
- deterministic repeatability;
- local/offline capability.

## Baselines
At minimum compare:
1. simple statistical rule set;
2. single ML anomaly model;
3. hybrid fusion model.

Do not claim superiority unless measured on the same evaluation split.
