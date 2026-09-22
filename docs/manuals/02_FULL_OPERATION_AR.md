# VAIXLNS Unified — التشغيل الكامل

الدورة الأساسية:
```
Identity
 ↓
Intent / Decision
 ↓
Governance
 ↓
VXRuntime
 ↓
Worker
 ↓
Event Ledger
 ↓
Evidence / Replay
```

التشغيل البرمجي يبدأ بتجهيز Identity وSovereignEventLedger ثم إنشاء ExecutionEnvelope وتسجيل worker وتنفيذ العملية.

المخرجات التشغيلية الأساسية:
- execution_id
- status
- input/output hashes
- ledger event
- execution history
- replay result
