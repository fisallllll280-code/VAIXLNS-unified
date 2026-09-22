# VAIXLNS Unified — التثبيت

```bash
git clone https://github.com/fisallllll280-code/VAIXLNS-unified.git
cd VAIXLNS-unified
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

اختبار البيئة:
```bash
python -m pytest -q
```

ملاحظة: اعتماد التشغيل النهائي على واجهة entrypoint يجب أن يتطابق مع الملفات الفعلية في الإصدار المنشور؛ لا يُستخدم أمر غير موجود في المستودع.
