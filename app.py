import streamlit as st
import pandas as pd
import re
from io import BytesIO
from datetime import datetime
import zipfile

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


def _prepare_td_files_from_uploads(dna_files, unique_only=True):
    """Parse multiple .dna files and build a list of dicts: {td_id, file_name, data(bytes), count}"""
    frames = []
    for f in dna_files:
        frames.append(parse_dna_file(f))
    if not frames:
        return []
    df = pd.concat(frames, ignore_index=True)
    if df.empty:
        return []

    td_files = []
    for td, grp in df.groupby("td_id"):
        values = grp["berth_id"].astype(str)
        if unique_only:
            values = pd.Index(values).unique()
            values = sorted(values)
        content = "\n".join(values) + ("\n" if len(values) else "")
        data = content.encode("utf-8")
        fname = f"{_sanitize_filename(str(td))}.txt"
        td_files.append({"td_id": str(td), "file_name": fname, "data": data, "count": len(values)})
    return sorted(td_files, key=lambda x: x["td_id"])


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


# ============== DVS PRODUCER (Persist results; Checkbox + one ZIP) ==============
def render_producer():
    st.button("← กลับหน้าแรก", on_click=_back_to_home)
    st.title("DVS Producer")

    dna_files = st.file_uploader("อัปโหลดไฟล์ berth.dna (หลายไฟล์ได้)", type=["dna", "txt"], accept_multiple_files=True)
    unique_only = st.checkbox("ลบซ้ำและเรียงค่า (recommended)", value=True)
    produce_clicked = st.button("🏁 Produce")

    # เมื่อกด Produce ให้เตรียมข้อมูลและเก็บไว้ใน session_state เพื่อไม่ให้หายตอน rerun
    if produce_clicked:
        if not dna_files:
            st.error("กรุณาอัปโหลดไฟล์ .dna อย่างน้อย 1 ไฟล์")
            st.stop()
        try:
            td_files = _prepare_td_files_from_uploads(dna_files, unique_only=unique_only)
        except Exception as e:
            st.error(f"ประมวลผลไม่สำเร็จ: {e}")
            st.stop()

        if not td_files:
            st.error("ไม่พบข้อมูลในไฟล์ .dna")
            st.stop()

        st.session_state["producer_td_files"] = td_files
        # รีเซ็ตการเลือกทั้งหมดให้ว่าง
        for it in td_files:
            st.session_state[f"sel_{it['file_name']}"] = False

    # หากมีผลลัพธ์ใน state ให้แสดงส่วนเลือกไฟล์ + ดาวน์โหลด เสมอ (ไม่หายเมื่อมี rerun จาก checkbox)
    td_files_state = st.session_state.get("producer_td_files", [])
    if td_files_state:
        st.subheader("📦 สรุปจำนวนรายการต่อ td_id")
        st.dataframe(pd.DataFrame([{"td_id": x["td_id"], "count": x["count"]} for x in td_files_state]).sort_values("td_id").reset_index(drop=True), use_container_width=True)

        st.subheader("🗂️ เลือกไฟล์ที่จะดาวน์โหลด")
        # ปุ่มเลือกทั้งหมด/ล้างเลือก
        c1, c2, c3 = st.columns([1,1,2])
        with c1:
            if st.button("เลือกทั้งหมด"):
                for it in td_files_state:
                    st.session_state[f"sel_{it['file_name']}"] = True
                st.rerun()
        with c2:
            if st.button("ล้างการเลือก"):
                for it in td_files_state:
                    st.session_state[f"sel_{it['file_name']}"] = False
                st.rerun()
        with c3:
            if st.button("ล้างผลลัพธ์ (เริ่มใหม่)"):
                for it in td_files_state:
                    st.session_state.pop(f"sel_{it['file_name']}", None)
                st.session_state.pop("producer_td_files", None)
                st.rerun()

        # แสดง checkbox แบบ 3 คอลัมน์ เพื่อประหยัดพื้นที่
        cols = st.columns(3)
        for i, item in enumerate(td_files_state):
            key = f"sel_{item['file_name']}"
            if key not in st.session_state:
                st.session_state[key] = False
            with cols[i % 3]:
                st.checkbox(f"{item['file_name']} ({item['count']})", key=key)

        
        # ปุ่มเดียว: ดาวน์โหลดไฟล์ที่เลือกทันที (สร้าง ZIP on-the-fly)
        selected_items = [it for it in td_files_state if st.session_state.get(f"sel_{it['file_name']}", False)]
        disabled = len(selected_items) == 0

        # เตรียม ZIP bytes ตามการเลือก
        zip_bytes = b""
        zip_filename = "dvs_selected.zip"
        if not disabled:
            memzip = BytesIO()
            with zipfile.ZipFile(memzip, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
                for it in selected_items:
                    zf.writestr(it["file_name"], it["data"])
            memzip.seek(0)
            zip_bytes = memzip.getvalue()
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            zip_filename = f"dvs_selected_{ts}.zip"

        st.download_button(
            label="⬇️ ดาวน์โหลดไฟล์ที่เลือก",
            data=zip_bytes,
            file_name=zip_filename,
            mime="application/zip",
            use_container_width=True,
            disabled=disabled,
            key="dl_zip_selected"
        )
    


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
