import streamlit as st
import pandas as pd
import re
from io import BytesIO

# ---------- Page config ----------
st.set_page_config(page_title="TD Checker v3 (Manual)", page_icon="✅", layout="wide")
st.title("TD Checker v3 • เปรียบเทียบ berth_id ด้วยรายการอ้างอิงที่วางเอง (Manual paste)")
st.caption("อัปโหลดไฟล์ .dna (หลายไฟล์ได้) + กำหนด td_id และวางลิสต์ berth_id ต่อ td แล้วกดสร้างรายงาน")

# ---------- Helpers ----------
def parse_dna_file(file) -> pd.DataFrame:
    """อ่านไฟล์ .dna แล้วดึงคู่ (berth_id, td_id) ออกมา"""
    content = file.read()
    try:
        text = content.decode("utf-8", errors="ignore")
    except Exception:
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

        # สมมติว่าคั่นด้วยแท็บ (บางไฟล์มีช่องว่างปน)
        toks = [t.strip() for t in raw.split("\t") if t.strip() != ""]
        if not toks:
            continue

        berth_id = toks[0]
        td_id    = toks[-1]

        if str(berth_id).startswith("//"):  # ข้ามคอมเมนต์
            continue

        rows.append((str(berth_id).strip(), str(td_id).strip()))

    df = pd.DataFrame(rows, columns=["berth_id", "td_id"])
    return df


def parse_manual_list(text: str) -> set:
    """รับข้อความที่คั่นด้วย space/comma/newline แล้วแปลงเป็นเซ็ตของรหัส"""
    tokens = re.split(r"[,\s]+", (text or "").strip())
    return {t for t in tokens if t}


def compare_sets(name: str, dna_set: set, ref_set: set) -> pd.DataFrame:
    """คืน DataFrame ที่มี status = MISSING_IN_DNA / EXTRA_IN_DNA / MATCHED"""
    missing = sorted(ref_set - dna_set)  # อยู่ในอ้างอิง แต่ไม่อยู่ใน .dna
    extra   = sorted(dna_set - ref_set)  # อยู่ใน .dna แต่ไม่อยู่ในอ้างอิง
    matched = sorted(dna_set & ref_set)

    parts = []
    parts += [{"td_id": name, "status": "MISSING_IN_DNA", "berth_id": bid} for bid in missing]
    parts += [{"td_id": name, "status": "EXTRA_IN_DNA",   "berth_id": bid} for bid in extra]
    parts += [{"td_id": name, "status": "MATCHED",        "berth_id": bid} for bid in matched]
    return pd.DataFrame(parts, columns=["td_id", "status", "berth_id"])


# ---------- Inputs ----------
dna_files = st.file_uploader("อัปโหลดไฟล์ .dna (1–3 ไฟล์)", type=["dna", "txt"], accept_multiple_files=True)

td_input = st.text_input("ใส่รายการ td_id (คั่นด้วยช่องว่าง)", value="Y1 YE FE DR").strip()
td_list = [t for t in td_input.split() if t]

st.markdown("### วางรายการอ้างอิงของแต่ละ td (คั่นด้วย space / comma / newline)")
manual_map = {}
cols = st.columns(2)
for i, td in enumerate(td_list):
    with cols[i % 2]:
        manual_map[td] = st.text_area(
            f"{td} • วาง `berth_id` ที่เป็นสเปก",
            key=f"ta_{td}",
            height=120,
            placeholder="ตัวอย่าง: A101, A102, A103 หรือพิมพ์เรียงกันเว้นวรรค/บรรทัด"
        )

run_btn = st.button("🔎 สร้างรายงาน")

# ---------- Processing ----------
if run_btn:
    if not dna_files:
        st.error("กรุณาอัปโหลดไฟล์ .dna อย่างน้อย 1 ไฟล์")
        st.stop()

    # รวมข้อมูลจากทุกไฟล์ .dna
    frames = []
    for f in dna_files:
        try:
            frames.append(parse_dna_file(f))
        except Exception as e:
            st.error(f"อ่านไฟล์ล้มเหลว: {f.name} ({e})")
    if not frames:
        st.error("ไม่พบข้อมูลในไฟล์ .dna ที่อัปโหลด")
        st.stop()

    df_all = pd.concat(frames, ignore_index=True)

    # เตรียมเปรียบเทียบ
    summary_rows = []
    per_td_results = {}
    warn_empty = []

    for td in td_list:
        dna_ids = set(df_all.loc[df_all["td_id"] == td, "berth_id"].astype(str))
        ref_ids = parse_manual_list(manual_map.get(td, ""))

        if len(ref_ids) == 0:
            warn_empty.append(td)

        result_df = compare_sets(td, dna_ids, ref_ids)
        per_td_results[td] = result_df

        n_miss  = (result_df["status"] == "MISSING_IN_DNA").sum()
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

    if warn_empty:
        st.warning("td ต่อไปนี้ยังไม่ได้วางรายการอ้างอิง: " + ", ".join(warn_empty))

    summary = pd.DataFrame(summary_rows)
    st.subheader("📊 SUMMARY")
    st.dataframe(summary, use_container_width=True)

    # แสดงผลต่างแบบทันที
    st.subheader("🔎 รายการที่แตกต่าง (ต่อ td_id)")
    for td, dfres in per_td_results.items():
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**{td} — MISSING_IN_DNA** (อยู่ในอ้างอิง แต่ไม่อยู่ใน .dna)")
            st.dataframe(
                dfres.loc[dfres["status"] == "MISSING_IN_DNA", ["berth_id"]],
                use_container_width=True, height=240
            )
        with col2:
            st.markdown(f"**{td} — EXTRA_IN_DNA** (อยู่ใน .dna แต่ไม่อยู่ในอ้างอิง)")
            st.dataframe(
                dfres.loc[dfres["status"] == "EXTRA_IN_DNA", ["berth_id"]],
                use_container_width=True, height=240
            )

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
    st.caption("Tips: ถ้าต้องการให้ทีมใช้งานเร็ว ให้เตรียมลิสต์สเปกของแต่ละ td ไว้ล่วงหน้าแล้ว copy/paste ลงช่องของ td นั้น ๆ")
