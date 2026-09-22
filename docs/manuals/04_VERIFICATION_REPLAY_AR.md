# VAIXLNS Unified — التحقق وإعادة التشغيل

## الاختبار
```bash
python -m pytest -q
```

## Replay
يجب أن تستخدم إعادة التشغيل المدخلات الأصلية نفسها.

التحقق المقبول:
```
hash(original_output) == hash(replayed_output)
```

أما اختلاف الناتج مع نفس المدخلات فيسجل NON_DETERMINISTIC_OUTPUT.

## Ledger
```text
Genesis → Event₁ → Event₂ → … → Eventₙ
```
ويجب أن يظل hash chain وMerkle root متسقين.
