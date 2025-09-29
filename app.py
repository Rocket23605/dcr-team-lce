import streamlit as st
import pandas as pd
import re
from io import BytesIO
from datetime import datetime

# ============== PAGE CONFIG ==============
st.set_page_config(page_title="DVS Tools", page_icon="🧭", layout="wide")

# ============== HELPERS (shared) ==============
def parse_dna_file(file) -> pd.DataFrame:
    """อ่านไฟล์ .dna แล้วดึงคู่ (berth_id, td_id) ออกมา
    - ข้ามเฉพาะบรรทัดคอมเมนต์ที่ขึ้นต้นด้วย //
    - รองรับคอมเมนต์ท้ายบรรทัด (inline comment) โดยตัดส่วนที่ตามหลัง // ออกก่อนแยกคอลัมน์
    """
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

        # เริ่มอ่านหลังหัวข้อ DATA
        if s.startswith("** DATA BEGINS HERE **"):
            in_data = True
            continue
        if not in_data or not s:
            continue

        # ข้ามหัวตาราง/ metadata
        if s.startswith("Version") or s.startswith("berth_id"):
            continue

        # --- ข้ามเฉพาะคอมเมนต์ทั้งบรรทัด ---
        if s.startswith("//"):
            continue

        # --- ตัดคอมเมนต์ท้ายบรรทัด (inline comment) ถ้ามี ---
        cut = raw
        pos = cut.find("//")
        if pos > 0:  # มี // และไม่ได้อยู่ต้นบรรทัด
            cut = cut[:pos]

        # แยกคอลัมน์ (คั่นด้วยแท็บ/มีช่องว่างปน)
        toks = [t.strip() for t in cut.split("\t") if t.strip() != ""]
        if not toks:
            continue

        berth_id = toks[0]
        td_id    = toks[-1]

        # เผื่อกรณีมีเศษคอมเมนต์โผล่มาเป็นคอลัมน์แรก
        if str(berth_id).startswith("//"):
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


def _sanitize_filename(name: str) -> str:
    safe = re.sub(r"[^0-9A-Za-z._-]+", "_", name.strip())
    return safe or "TD"


def _back_to_home():
    st.session_state.page = "home"
    st.rerun()


# ============== HOMEPAGE ==============
def render_home():
    st.title("DVS Tools • DCR Thailand")
    st.write("เลือกเครื่องมือที่ต้องการใช้งาน")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("🏭 DVS Producer (Berth sorter)", use_container_width=True):
            st.session_state.page = "producer"
            st.rerun()
    with c2:
        if st.button("🧪 DVS Checker", use_container_width=True):
            st.session_state.page = "checker"
            st.rerun()


# ============== DVS CHECKER (ตามแอปเดิม) ==============
def render_checker():
    st.button("← กลับหน้าแรก", on_click=_back_to_home)
    st.title("DVS Checker")

    dna_files = st.file_uploader("อัปโหลดไฟล์ berth.dna (หลายไฟล์ได้)", type=["dna", "txt"], accept_multiple_files=True)
    td_input = st.text_input("ใส่รายการ td_id คั่นด้วยช่องว่าง จากนั้นกด Enter", value="Y1 YE FE DR").strip()
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
        st.caption("Tips: เตรียมลิสต์สเปกของแต่ละ td ไว้ล่วงหน้าแล้ว copy/paste ลงช่องของ td นั้น ๆ")


# ============== DVS PRODUCER (หลายไฟล์ + ไม่รวม zip + ตัดคอมเมนต์) ==============
def render_producer():
    st.button("← กลับหน้าแรก", on_click=_back_to_home)
    st.title("DVS Producer")

    dna_files = st.file_uploader("อัปโหลดไฟล์ berth.dna (หลายไฟล์ได้)", type=["dna", "txt"], accept_multiple_files=True)
    unique_only = st.checkbox("ลบซ้ำและเรียงค่า (recommended)", value=True)
    produce = st.button("🏁 Produce")

    if produce:
        if not dna_files:
            st.error("กรุณาอัปโหลดไฟล์ .dna อย่างน้อย 1 ไฟล์")
            st.stop()

        # รวมข้อมูลจากทุกไฟล์ .dna (ตัดคอมเมนต์ด้วย parse_dna_file)
        frames = []
        for f in dna_files:
            try:
                frames.append(parse_dna_file(f))
            except Exception as e:
                st.error(f"อ่านไฟล์ล้มเหลว: {f.name} ({e})")
        if not frames:
            st.error("ไม่พบข้อมูลในไฟล์ .dna ที่อัปโหลด")
            st.stop()

        df = pd.concat(frames, ignore_index=True)

        if df.empty:
            st.error("ไม่พบข้อมูลในไฟล์ .dna")
            st.stop()

        # ดาวน์โหลดทีละไฟล์ .txt ต่อ td_id (ไม่รวม zip)
        st.subheader("⬇️ ดาวน์โหลดไฟล์ .txt ต่อ td_id")
        counts = []
        for td, grp in df.groupby("td_id"):
            values = grp["berth_id"].astype(str)
            count = len(values)
            if unique_only:
                values = pd.Index(values).unique()
                values = sorted(values)
                count = len(values)
            content = "\n".join(values) + ("\n" if len(values) else "")
            data = content.encode("utf-8")
            fname = f"{_sanitize_filename(str(td))}.txt"
            st.download_button(
                label=f"ดาวน์โหลด {fname} ({count} รายการ)",
                data=data,
                file_name=fname,
                mime="text/plain",
                use_container_width=True,
                key=f"dl_{fname}"
            )
            counts.append({"td_id": td, "count": count})

        # สรุปนับจำนวนต่อ td_id
        if counts:
            st.subheader("📦 สรุปจำนวนรายการต่อ td_id")
            st.dataframe(pd.DataFrame(counts).sort_values('td_id').reset_index(drop=True), use_container_width=True)


# ============== ROUTING ==============
if "page" not in st.session_state:
    st.session_state.page = "home"

if st.session_state.page == "home":
    render_home()
elif st.session_state.page == "checker":
    render_checker()
elif st.session_state.page == "producer":
    render_producer()
else:
    render_home()
