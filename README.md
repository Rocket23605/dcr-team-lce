
# TD Checker (Streamlit App)
แอปสำหรับเปรียบเทียบ `berth_id` จากไฟล์ `.dna` กับไฟล์อ้างอิง `.txt` ตาม `td_id` (เช่น `Y1, YE, FE, DR`)

## วิธีใช้งานแบบง่ายที่สุด
1) ติดตั้ง Python 3.10+ (หากยังไม่มี)
2) เปิด Command Prompt / Terminal แล้วรันในโฟลเดอร์แอปนี้:
```
pip install -r requirements.txt
streamlit run app.py
```
3) หน้าต่างเบราว์เซอร์จะเปิดขึ้นอัตโนมัติ → อัปโหลดไฟล์ `.dna` (1–3 ไฟล์) และไฟล์อ้างอิง `.txt` (เช่น Y1.txt)  
4) ใส่ td_id ที่ต้องการตรวจ เช่น `Y1 YE FE DR` แล้วกด **สร้างรายงาน**  
5) ดาวน์โหลดไฟล์ Excel สรุปผล

> ถ้าทีมไม่มี Python: สามารถแพ็กเป็น .exe ด้วย PyInstaller หรือรันบน Streamlit Community Cloud ได้ (แนะนำสำหรับทีมที่ไม่ถนัดไอที)

## โครงสร้างไฟล์อ้างอิง
- ชื่อไฟล์ให้ตรงกับ td_id เช่น `Y1.txt`, `YE.txt`, `FE.txt`, `DR.txt`
- ด้านในสามารถคั่นด้วย comma, space, หรือ newline ก็ได้ เช่น
```
A101, A102, A103
B201
B202 B203
```

## อธิบายผลลัพธ์
- **SUMMARY**: รวมจำนวนรายการที่ `matched`, `missing_in_dna`, `extra_in_dna` ต่อ td_id
- ชีตตามชื่อ td_id: รายการ `berth_id` ทีละสถานะ (`MATCHED`, `MISSING_IN_DNA`, `EXTRA_IN_DNA`)

## แพ็กเป็น .exe (ทางเลือก)
```
pip install pyinstaller
pyinstaller --onefile --add-data "app.py;." --name td_checker_app runner.py
```
> หมายเหตุ: Streamlit เป็นเว็บแอป จึงมักสะดวกกว่าหากรันด้วย `streamlit run app.py` โดยตรง หรือ deploy บนคลาวด์
