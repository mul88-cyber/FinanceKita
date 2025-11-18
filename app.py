import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
import gspread  # Pastikan gspread ada di requirements.txt

# --- Konfigurasi Halaman ---
st.set_page_config(
    page_title="Dashboard Keuangan Keluarga JOSS",
    page_icon="💰",
    layout="wide"
)

# --- Judul Utama ---
st.title("💰✨ Dashboard Keuangan Keluarga PRO (JOSS)")
st.caption(f"Versi 3.0 | Tersambung ke Google Sheets 📄 | Data per: {datetime.now().strftime('%d %B %Y')}")

# --- Helper Function untuk Donut Chart ---
def create_donut_chart(df, title):
    """Membuat Donut Chart Altair dari DataFrame."""
    if df.empty or df["Jumlah"].sum() == 0:
        st.info(f"Tidak ada data untuk {title.lower()}.")
        return

    total = df["Jumlah"].sum()
    df['Persentase'] = (df['Jumlah'] / total)

    base = alt.Chart(df).encode(
       theta=alt.Theta("Jumlah", stack=True)
    ).properties(title=title)

    donut = base.mark_arc(outerRadius=120, innerRadius=80).encode(
        color=alt.Color("Kategori", legend=alt.Legend(title="Kategori")),
        order=alt.Order("Jumlah", sort="descending"),
        tooltip=["Kategori", "Jumlah", alt.Tooltip("Persentase", format=".1%")]
    )

    text_total = alt.Chart(pd.DataFrame({'Total': [total]})).mark_text(
        align='center', 
        baseline='middle', 
        fontSize=24, # Diperbesar
        fontWeight="bold",
        color="#FFFFFF"
    ).encode(
        text=alt.Text('Total', format=',.0f'),
    )
    
    chart = donut + text_total
    return st.altair_chart(chart, use_container_width=True)

# --- Setup Koneksi Google Sheets ---
try:
    creds = st.secrets["gsheets_credentials"]
    gc = gspread.service_account_from_dict(creds)
    spreadsheet_url = st.secrets["GSHEET_URL"]
    worksheet_name = st.secrets["WORKSHEET_NAME"]
    sh = gc.open_by_url(spreadsheet_url)
    worksheet = sh.worksheet(worksheet_name)
    GSHEET_CONNECTED = True
except Exception as e:
    st.error(f"Gagal terhubung ke Google Sheets. Pastikan 'secrets.toml' sudah benar. Error: {e}")
    GSHEET_CONNECTED = False
    worksheet = None

# --- Fungsi untuk Membaca Data ---
@st.cache_data(ttl=30) # Waktu cache dipersingkat jadi 30 detik
def load_data(_ws):
    """Membaca semua data dari worksheet dan mengubahnya jadi DataFrame."""
    try:
        data = _ws.get_all_records()
        if not data:
            return pd.DataFrame(columns=["Tanggal", "Tipe", "Kategori", "Jumlah", "Catatan"])
        
        df = pd.DataFrame(data)
        
        required_cols = ["Tanggal", "Tipe", "Kategori", "Jumlah", "Catatan"]
        for col in required_cols:
            if col not in df.columns:
                df[col] = None
        
        df['Tanggal'] = pd.to_datetime(df['Tanggal'], errors='coerce')
        df['Jumlah'] = pd.to_numeric(df['Jumlah'], errors='coerce').fillna(0)
        df.dropna(subset=['Tanggal'], inplace=True)
        
        return df
    except Exception as e:
        st.error(f"Gagal membaca data dari sheet: {e}")
        return pd.DataFrame(columns=["Tanggal", "Tipe", "Kategori", "Jumlah", "Catatan"])

# --- Sidebar: Input Form ---
st.sidebar.header("📝 Tambah Transaksi Baru")
tipe = st.sidebar.radio("Tipe Transaksi", ["Pemasukan", "Pengeluaran"], horizontal=True, index=1)

if tipe == "Pengeluaran":
    kategori_options = ["🏠 Rumah Tangga", "🍔 Makanan & Minuman", "🚗 Transportasi", "🧾 Tagihan", "👨‍⚕️ Kesehatan", "🎉 Hiburan", "📚 Pendidikan", "🛒 Belanja", "🎁 Hadiah/Amal", "Lainnya"]
else:
    kategori_options = ["💼 Gaji", "💰 Bonus", "📈 Investasi", "Side Hustle", "🎁 Hadiah", "Lainnya"]

with st.sidebar.form("transaction_form", clear_on_submit=True):
    tanggal = st.date_input("Tanggal", datetime.now())
    kategori = st.selectbox("Kategori", kategori_options)
    jumlah = st.number_input("Jumlah (Rp)", min_value=0.0, step=1000.0, format="%.2f")
    catatan = st.text_area("Catatan (Opsional)")
    
    submitted = st.form_submit_button("✓ Tambah Transaksi")

# --- Logika untuk Menambah Transaksi ---
if submitted and GSHEET_CONNECTED:
    try:
        if jumlah <= 0:
            st.sidebar.warning("Jumlah harus lebih besar dari 0.")
        else:
            new_row = [
                tanggal.strftime("%Y-%m-%d"), 
                tipe,
                kategori,
                jumlah,
                catatan
            ]
            all_values = worksheet.get_all_values()
            if not all_values:
                header = ["Tanggal", "Tipe", "Kategori", "Jumlah", "Catatan"]
                worksheet.append_row(header)
            worksheet.append_row(new_row)
            st.sidebar.success("Transaksi berhasil ditambahkan!")
            
            # --- PERBAIKAN BUG ---
            # Paksa clear cache DAN rerun aplikasi
            st.cache_data.clear()
            st.experimental_rerun() 
            # --- AKHIR PERBAIKAN ---
            
    except Exception as e:
        st.sidebar.error(f"Gagal menyimpan ke GSheet: {e}")
elif submitted:
    st.sidebar.error("Koneksi GSheet gagal, tidak bisa menambah transaksi.")

# --- ====================================================== ---
# ---               MAIN DASHBOARD (VERSI JOSS)              ---
# --- ====================================================== ---

if GSHEET_CONNECTED:
    df = load_data(worksheet)

    if df.empty:
        st.info("Belum ada transaksi valid di Google Sheet. Silakan tambahkan transaksi baru melalui sidebar.")
        st.balloons()
    else:
        # --- 1. FILTER DATA ---
        st.header("🔍 Filter Dashboard")
        
        min_date_val = df['Tanggal'].min()
        max_date_val = df['Tanggal'].max()

        if pd.isna(min_date_val) or pd.isna(max_date_val):
            min_date = datetime.now().date()
            max_date = datetime.now().date()
        else:
            min_date = min_date_val.date()
            max_date = max_date_val.date()
        
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Tanggal Mulai", min_date, min_value=min_date, max_value=max_date)
        with col2:
            end_date = st.date_input("Tanggal Akhir", max_date, min_value=min_date, max_value=max_date)
            
        all_kategori = df['Kategori'].unique()
        selected_kategori = st.multiselect("Filter Kategori", all_kategori, default=all_kategori)
        
        st.divider()

        # --- 2. LOGIKA FILTERISASI DATA ---
        if not isinstance(start_date, datetime.date): start_date = min_date
        if not isinstance(end_date, datetime.date): end_date = max_date

        df_filtered = df[
            (df['Tanggal'].dt.date >= start_date) &
            (df['Tanggal'].dt.date <= end_date) &
            (df['Kategori'].isin(selected_kategori))
        ]

        if df_filtered.empty:
            st.warning("Tidak ada data transaksi yang sesuai dengan filter Anda.")
        else:
            # --- 3. TAMPILAN TAB ---
            tab_ringkasan, tab_analisis, tab_data = st.tabs(
                ["📊 Ringkasan", "📈 Analisis Mendalam", "📚 Data Transaksi"]
            )

            # --- TAB 1: RINGKASAN ---
            with tab_ringkasan:
                st.subheader(f"Ringkasan dari {start_date.strftime('%d/%m/%Y')} s/d {end_date.strftime('%d/%m/%Y')}")

                total_pemasukan = df_filtered[df_filtered["Tipe"] == "Pemasukan"]["Jumlah"].sum()
                total_pengeluaran = df_filtered[df_filtered["Tipe"] == "Pengeluaran"]["Jumlah"].sum()
                saldo_saat_ini = total_pemasukan - total_pengeluaran
                jumlah_transaksi = df_filtered.shape[0]
                
                total_hari = (end_date - start_date).days + 1
                avg_pengeluaran = total_pengeluaran / total_hari if total_hari > 0 else 0

                col1, col2, col3 = st.columns([1.5, 1.5, 2]) # Lebar kolom diubah
                col1.metric("Total Pemasukan", f"Rp {total_pemasukan:,.0f}", "👍")
                col2.metric("Total Pengeluaran", f"Rp {total_pengeluaran:,.0f}", "👎", delta_color="inverse")
                
                # --- UPGRADE UI "JOSS" ---
                saldo_color = "green" if saldo_saat_ini >= 0 else "red"
                col3.markdown(f"""
                <div style="background-color: #222; border: 2px solid {saldo_color}; border-radius: 10px; padding: 16px; text-align: center;">
                    <span style="font-size: 1.2rem; color: #AAA; font-weight: bold;">SALDO AKHIR</span>
                    <br>
                    <span style="font-size: 2.5rem; font-weight: bold; color: {saldo_color};">Rp {saldo_saat_ini:,.0f}</span>
                </div>
                """, unsafe_allow_html=True)
                
                st.divider()
                
                col4, col5 = st.columns(2)
                col4.metric("Jumlah Transaksi", f"{jumlah_transaksi} kali")
                col5.metric("Rata-rata Pengeluaran / Hari", f"Rp {avg_pengeluaran:,.0f}")
                
                st.divider()

                # --- FITUR BARU "JOSS": GRAFIK BATANG PEMASUKAN VS PENGELUARAN ---
                st.subheader("Pemasukan vs. Pengeluaran Harian")
                df_grouped = df_filtered.groupby(['Tanggal', 'Tipe'])['Jumlah'].sum().reset_index()
                
                bar_chart = alt.Chart(df_grouped).mark_bar().encode(
                    x=alt.X('Tanggal', title='Tanggal', axis=alt.Axis(format="%Y-%m-%d")),
                    y=alt.Y('Jumlah', title='Jumlah (Rp)'),
                    color=alt.Color('Tipe', title='Tipe', scale=alt.Scale(domain=['Pemasukan', 'Pengeluaran'], range=['green', 'red'])),
                    tooltip=['Tanggal', 'Tipe', 'Jumlah']
                ).interactive()
                st.altair_chart(bar_chart, use_container_width=True)

                # Grafik Arus Kas (Cashflow)
                st.subheader("Arus Kas (Cashflow Kumulatif)")
                df_sorted = df_filtered.sort_values(by="Tanggal").copy()
                if not df_sorted.empty:
                    df_sorted['Perubahan'] = df_sorted.apply(lambda row: row['Jumlah'] if row['Tipe'] == 'Pemasukan' else -row['Jumlah'], axis=1)
                    df_before = df[df['Tanggal'].dt.date < start_date]
                    saldo_awal = df_before.apply(lambda row: row['Jumlah'] if row['Tipe'] == 'Pemasukan' else -row['Jumlah'], axis=1).sum()
                    df_sorted['Saldo Kumulatif'] = df_sorted['Perubahan'].cumsum() + saldo_awal

                    line_chart = alt.Chart(df_sorted).mark_line(point=True, strokeWidth=3).encode(
                        x=alt.X('Tanggal', title='Tanggal'),
                        y=alt.Y('Saldo Kumulatif', title='Saldo (Rp)'),
                        tooltip=['Tanggal', 'Tipe', 'Kategori', 'Jumlah', 'Saldo Kumulatif']
                    ).interactive()
                    st.altair_chart(line_chart, use_container_width=True)

            # --- TAB 2: ANALISIS MENDALAM ---
            with tab_analisis:
                st.subheader("Analisis Proporsi Pemasukan & Pengeluaran")
                
                col_donut1, col_donut2 = st.columns(2)
                
                with col_donut1:
                    df_chart_pengeluaran = df_filtered[df_filtered["Tipe"] == "Pengeluaran"].groupby("Kategori")["Jumlah"].sum().reset_index()
                    create_donut_chart(df_chart_pengeluaran, "Proporsi Pengeluaran")

                with col_donut2:
                    df_chart_pemasukan = df_filtered[df_filtered["Tipe"] == "Pemasukan"].groupby("Kategori")["Jumlah"].sum().reset_index()
                    create_donut_chart(df_chart_pemasukan, "Proporsi Pemasukan")
                
                st.divider()
                
                # --- FITUR BARU "JOSS": TOP 5 PENGELUARAN ---
                st.subheader("Top 5 Kategori Pengeluaran")
                df_top_5 = df_chart_pengeluaran.sort_values(by="Jumlah", ascending=False).head(5).reset_index(drop=True)
                df_top_5.index = df_top_5.index + 1 # Mulai index dari 1
                st.dataframe(
                    df_top_5,
                    use_container_width=True,
                    column_config={
                        "Jumlah": st.column_config.NumberColumn("Jumlah (Rp)", format="Rp %'.0f"),
                        "Kategori": st.column_config.TextColumn("Kategori"),
                    }
                )


            # --- TAB 3: DATA TRANSAKSI ---
            with tab_data:
                st.subheader("Data Transaksi (Sesuai Filter)")
                
                # --- FITUR BARU "JOSS": RINGKASAN PIVOT ---
                with st.expander("📊 Klik untuk melihat Ringkasan Kategori (sesuai filter)"):
                    df_pivot = df_filtered.groupby(['Tipe', 'Kategori'])['Jumlah'].sum().reset_index()
                    st.dataframe(
                        df_pivot.sort_values(by=["Tipe", "Jumlah"], ascending=[True, False]), 
                        use_container_width=True,
                        column_config={
                            "Jumlah": st.column_config.NumberColumn("Total Jumlah (Rp)", format="Rp %'.0f"),
                        }
                    )
                
                st.dataframe(
                    df_filtered.sort_values(by="Tanggal", ascending=False), 
                    use_container_width=True,
                    height=500, # Tambahkan tinggi agar bisa di-scroll
                    column_config={
                        "Jumlah": st.column_config.NumberColumn("Jumlah (Rp)", format="Rp %'.0f"),
                        "Tanggal": st.column_config.DateColumn("Tanggal", format="DD/MM/YYYY"),
                        "Tipe": st.column_config.TextColumn("Tipe"),
                        "Kategori": st.column_config.TextColumn("Kategori"),
                        "Catatan": st.column_config.TextColumn("Catatan")
                    }
                )

else:
    st.error("Aplikasi tidak dapat berjalan tanpa koneksi ke Google Sheets. Silakan periksa 'secrets' Anda di Streamlit Cloud.")
