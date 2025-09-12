
import streamlit as st
import pandas as pd
import io, re
from io import BytesIO

st.set_page_config(page_title="TD Checker", page_icon="✅", layout="wide")

st.title("TD Checker • เปรียบเทียบ berth_id ระหว่างไฟล์ .dna และไฟล์อ้างอิง")
st.markdown("""
อัปโหลดไฟล์ .dna (ได้สูงสุด 3 ไฟล์) และไฟล์อ้างอิง (.txt) แล้วเลือก td_id (เช่น **Y1, YE, FE, DR**) เพื่อสร้างรายงานอัตโนมัติ
""")

def parse_dna_file(file) -> pd.DataFrame:
    content = file.read()
    try:
        text = content.decode("utf-8", errors="ignore")
    except:
        text = content.decode(errors="ignore")
    lines = text.splitlines()
    in_data = False
    rows = []
    for raw in lines:
        s = raw.strip()
        if s.startswith("** DATA BEGINS HERE **"):
            in_data = True
            continue
        if not in_data:
            continue
        if not s:
            continue
        if s.startswith("Version") or s.startswith("berth_id"):
            continue
        toks = [t.strip() for t in raw.split('\t') if t.strip() != ""]
        if not toks:
            continue
        berth_id = toks[0]
        td_id    = toks[-1]
        if berth_id.startswith("//"):
            continue
        rows.append((berth_id.strip(), td_id.strip()))
    df = pd.DataFrame(rows, columns=["berth_id", "td_id"])
    return df

def load_reference_ids(txt_file) -> set:
    content = txt_file.read()
    try:
        text = content.decode("utf-8", errors="ignore")
    except:
        text = content.decode(errors="ignore")
    tokens = re.split(r"[,\s]+", text.strip())
    return {t for t in tokens if t}

def compare_sets(name: str, dna_set: set, ref_set: set) -> pd.DataFrame:
    missing = sorted(ref_set - dna_set)  # อยู่ในสเปก แต่ไม่อยู่ใน .dna
    extra   = sorted(dna_set - ref_set)  # อยู่ใน .dna แต่ไม่อยู่ในสเปก
    matched = sorted(dna_set & ref_set)
    parts = []
    parts += [{"td_id": name, "status": "MISSING_IN_DNA", "berth_id": bid} for bid in missing]
    parts += [{"td_id": name, "status": "EXTRA_IN_DNA",   "berth_id": bid} for bid in extra]
    parts += [{"td_id": name, "status": "MATCHED",        "berth_id": bid} for bid in matched]
    return pd.DataFrame(parts, columns=["td_id", "status", "berth_id"])

dna_files = st.file_uploader("อัปโหลดไฟล์ .dna (1–3 ไฟล์)", type=["dna","txt"], accept_multiple_files=True)
ref_files = st.file_uploader("อัปโหลดไฟล์อ้างอิง (.txt) เช่น Y1.txt, YE.txt ... (อัปโหลดหลายไฟล์ได้)", type=["txt"], accept_multiple_files=True)

td_input = st.text_input("ใส่รายการ td_id (คั่นด้วยช่องว่าง)", value="Y1 YE FE DR").strip()
td_list = [t for t in td_input.split() if t]

run_btn = st.button("🔎 สร้างรายงาน")

if run_btn:
    if not dna_files:
        st.error("กรุณาอัปโหลดไฟล์ .dna อย่างน้อย 1 ไฟล์")
        st.stop()

    # รวมข้อมูลจากไฟล์ .dna
    frames = []
    for f in dna_files:
        try:
            df = parse_dna_file(f)
            frames.append(df)
        except Exception as e:
            st.error(f"อ่านไฟล์ล้มเหลว: {f.name} ({e})")
    if not frames:
        st.error("ไม่พบข้อมูลในไฟล์ .dna ที่อัปโหลด")
        st.stop()

    df_all = pd.concat(frames, ignore_index=True)

    # สร้าง mapping td -> ref_set จากไฟล์อ้างอิง
    ref_map = {t: set() for t in td_list}
    # เดา td จากชื่อไฟล์อ้างอิง: เช่น Y1.txt -> Y1
    name_map = {}
    for rf in ref_files or []:
        stem = rf.name.rsplit(".",1)[0]
        name_map[stem] = rf

    for td in td_list:
        if td in name_map:
            try:
                # ต้องอ่านสำเนาไฟล์ (file_uploader เป็น stream, ใช้ครั้งเดียว)
                ref_bytes = name_map[td].getvalue()
                ref_buf = io.BytesIO(ref_bytes)
                ref_map[td] = load_reference_ids(ref_buf)
            except Exception as e:
                st.warning(f"อ่านไฟล์อ้างอิง {name_map[td].name} ไม่ได้: {e}")
                ref_map[td] = set()
        else:
            ref_map[td] = set()  # ไม่อัปโหลดไฟล์ให้ td นี้ จะเทียบเฉพาะรายการที่พบใน .dna

    # จัดทำผลลัพธ์
    summary_rows = []
    per_td_results = {}
    for td in td_list:
        dna_ids = set(df_all.loc[df_all["td_id"] == td, "berth_id"].astype(str))
        ref_ids = ref_map.get(td, set()) or set()
        # ถ้าไม่มีไฟล์อ้างอิง ให้ถือว่า ref = dna (เพื่อให้เห็นรายการทั้งหมดอย่างน้อย)
        if len(ref_ids) == 0:
            ref_ids = dna_ids.copy()
        result_df = compare_sets(td, dna_ids, ref_ids)
        per_td_results[td] = result_df
        n_miss = (result_df["status"] == "MISSING_IN_DNA").sum()
        n_extra = (result_df["status"] == "EXTRA_IN_DNA").sum()
        n_match = (result_df["status"] == "MATCHED").sum()
        summary_rows.append({
            "td_id": td,
            "ref_count": len(ref_ids),
            "dna_count": len(dna_ids),
            "matched": n_match,
            "missing_in_dna": n_miss,
            "extra_in_dna": n_extra
        })

    summary = pd.DataFrame(summary_rows)
    st.subheader("📊 SUMMARY")
    st.dataframe(summary, use_container_width=True)

    # สร้างไฟล์ Excel ให้ดาวน์โหลด
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        summary.to_excel(writer, sheet_name="SUMMARY", index=False)
        for td, dfres in per_td_results.items():
            sheet = td[:31] if td else "TD"
            dfres.to_excel(writer, sheet_name=sheet, index=False)
    output.seek(0)
    st.download_button(
        label="⬇️ ดาวน์โหลดรายงาน Excel",
        data=output,
        file_name="td_compare_report.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    st.success("สร้างรายงานสำเร็จ")
    st.caption("Tip: ถ้าต้องการให้ทีมงานใช้งานง่าย ให้เตรียมไฟล์อ้างอิงชื่อ Y1.txt, YE.txt, FE.txt, DR.txt แล้วอัปโหลดคู่กับไฟล์ .dna")
