FROM python:3.10-slim

WORKDIR /app

# نسخ ملف المتطلبات وتثبيتها مباشرة
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# نسخ باقي ملفات الخدمة
COPY . .

EXPOSE 8000

# التشغيل المباشر باستخدام بايثون لضمان عدم حدوث خطأ في مسار uvicorn
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
