# VAIXLNS Unified — كتيب النواة والتنفيذ

## Core
- Sovereign Constitution: حدود وقواعد النواة.
- Identity: تعريف الفاعل والصلاحيات والجلسات.
- Ledger: سجل أحداث append-only مع hash chain وMerkle root.

## Execution
- VXRuntime ينفذ داخل envelope.
- Worker ينفذ capability محددة.
- التنفيذ الناجح يسجل EXECUTION_COMPLETED.
- الفشل يسجل EXECUTION_FAILED.
- Replay يعيد نفس inputs ويقارن output hash.

## مبدأ الحدود
Worker لا يملك سلطة سيادية؛ هو منفّذ لقدرة محددة فقط.
