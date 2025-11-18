import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
import gspread

# --- Konfigurasi Halaman ---
st.set_page_config(
    page_title="Dashboard Keuangan Keluarga",
    page_icon="💰",
    layout="wide"
)

# --- Judul Utama ---
st.title("💰 Dashboard Kontrol & Catatan Keuangan Keluarga")
st.caption("Tersambung ke Google Sheets 📄")

# --- Setup Koneksi Google Sheets ---

# Menggunakan Streamlit's Connection untuk GSheets
# Ini mengambil kredensial dari st.secrets["gsheets_credentials"]
# dan juga mengambil URL & Nama Sheet dari st.secrets
try:
    # Koneksi GSpread (untuk menulis/append)
    # Kita perlu scope yang tepat untuk gspread
    creds = st.secrets["gsheets_credentials"]
    gc = gspread.service_account_from_dict(creds)
    
    spreadsheet_url = st.secrets["GSHEET_URL"]
    worksheet_name = st.secrets["WORKSHEET_NAME"]
    
    # Buka worksheet
    sh = gc.open_by_url(spreadsheet_url)
    worksheet = sh.worksheet(worksheet_name)
    
    # Tandai koneksi berhasil
    GSHEET_CONNECTED = True

except Exception as e:
    st.error(f"Gagal terhubung ke Google Sheets. Pastikan 'secrets.toml' sudah benar. Error: {e}")
    GSHEET_CONNECTED = False
    worksheet = None # Tambahkan ini agar variabel ada

# --- Fungsi untuk Membaca Data ---
@st.cache_data(ttl=60) # Cache data selama 60 detik
def load_data(_ws):
    """Membaca semua data dari worksheet dan mengubahnya jadi DataFrame."""
    try:
        data = _ws.get_all_records() # Ini membaca data sebagai list of dicts
        
        if not data:
            # Jika sheet kosong, kembalikan DataFrame kosong dengan kolom
            return pd.DataFrame(columns=["Tanggal", "Tipe", "Kategori", "Jumlah", "Catatan"])
            
        df = pd.DataFrame(data)
        
        # Pastikan semua kolom ada
        required_cols = ["Tanggal", "Tipe", "Kategori", "Jumlah", "Catatan"]
        for col in required_cols:
            if col not in df.columns:
                df[col] = None # Atau nilai default lain

        # Konversi tipe data
        df['Tanggal'] = pd.to_datetime(df['Tanggal'])
        df['Jumlah'] = pd.to_numeric(df['Jumlah'])
        return df
    except Exception as e:
        st.error(f"Gagal membaca data dari sheet: {e}")
        return pd.DataFrame(columns=["Tanggal", "Tipe", "Kategori", "Jumlah", "Catatan"])

# --- Sidebar: Input Form ---
st.sidebar.header("📝 Tambah Transaksi Baru")
with st.sidebar.form("transaction_form", clear_on_submit=True):
    tanggal = st.date_input("Tanggal", datetime.now())
    tipe = st.radio("Tipe Transaksi", ["Pemasukan", "Pengeluaran"], horizontal=True)
    
    if tipe == "Pengeluaran":
        kategori_options = ["🏠 Rumah Tangga", "🍔 Makanan & Minuman", "🚗 Transportasi", "🧾 Tagihan", "👨‍⚕️ Kesehatan", "🎉 Hiburan", "📚 Pendidikan", "Lainnya"]
    else:
        kategori_options = ["💼 Gaji", "💰 Bonus", "📈 Investasi", "🎁 Hadiah", "Lainnya"]
    
    kategori = st.selectbox("Kategori", kategori_options)
    jumlah = st.number_input("Jumlah (Rp)", min_value=0.0, step=1000.0, format="%.2f")
    catatan = st.text_area("Catatan (Opsional)")
    
    submitted = st.form_submit_button("✓ Tambah Transaksi")

# --- Logika untuk Menambah Transaksi ---
if submitted and GSHEET_CONNECTED:
    try:
        # Siapkan baris baru sesuai urutan kolom GSheet
        # Penting: konversi tanggal ke string agar GSheet tidak bingung
        new_row = [
            tanggal.strftime("%Y-%m-%d"), # Format tanggal YYYY-MM-DD
            tipe,
            kategori,
            jumlah,
            catatan
        ]
        
        # Cek apakah header sudah ada
        # Cek jika sheet kosong (hanya 0 atau 1 baris (header))
        all_values = worksheet.get_all_values()
        if not all_values:
            header = ["Tanggal", "Tipe", "Kategori", "Jumlah", "Catatan"]
            worksheet.append_row(header)

        # Tambahkan baris baru ke Google Sheet
        worksheet.append_row(new_row)
        
        st.sidebar.success("Transaksi berhasil ditambahkan ke Google Sheets!")
        
        # Hapus cache data agar Streamlit membaca ulang data baru
        st.cache_data.clear()
        
    except Exception as e:
        st.sidebar.error(f"Gagal menyimpan ke GSheet: {e}")
elif submitted:
    st.sidebar.error("Koneksi GSheet gagal, tidak bisa menambah transaksi.")

# --- Main Dashboard: Tampilan Utama ---
if GSHEET_CONNECTED:
    # Muat data dari GSheet
    df = load_data(worksheet)

    if df.empty:
        st.info("Belum ada transaksi di Google Sheet. Silakan tambahkan transaksi baru.")
    else:
        # --- 1. Ringkasan (Metrics/KPIs) ---
        st.header("📊 Ringkasan Keuangan")
        
        total_pemasukan = df[df["Tipe"] == "Pemasukan"]["Jumlah"].sum()
        total_pengeluaran = df[df["Tipe"] == "Pengeluaran"]["Jumlah"].sum()
        saldo_saat_ini = total_pemasukan - total_pengeluaran
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Pemasukan", f"Rp {total_pemasukan:,.0f}")
        col2.metric("Total Pengeluaran", f"Rp {total_pengeluaran:,.0f}", delta_color="inverse")
        
        saldo_color = "green" if saldo_saat_ini >= 0 else "red"
        col3.markdown(f"""
        <div style="border: 2px solid {saldo_color}; border-radius: 10px; padding: 10px; text-align: center;">
            <span style="font-size: 1.1rem; color: #888;">Saldo Saat Ini</span>
            <br>
            <span style="font-size: 1.5rem; font-weight: bold; color: {saldo_color};">Rp {saldo_saat_ini:,.0f}</span>
        </div>
        """, unsafe_allow_html=True)
        
        st.divider()

        # --- 2. Visualisasi ---
        col_chart1, col_chart2 = st.columns(2)

        with col_chart1:
            st.subheader("Analisis Pengeluaran per Kategori")
            df_pengeluaran = df[df["Tipe"] == "Pengeluaran"]
            
            if not df_pengeluaran.empty:
                pengeluaran_by_cat = df_pengeluaran.groupby("Kategori")["Jumlah"].sum().reset_index()
                
                bar_chart = alt.Chart(pengeluaran_by_cat).mark_bar().encode(
                    x=alt.X('Jumlah', title='Total (Rp)'),
                    y=alt.Y('Kategori', title='Kategori', sort='-x'),
                    tooltip=['Kategori', 'Jumlah']
                ).interactive()
                st.altair_chart(bar_chart, use_container_width=True)
            else:
                st.write("Belum ada data pengeluaran.")

        with col_chart2:
            st.subheader("Arus Kas (Cashflow)")
            
            # Pastikan Tanggal sudah di-sort sebelum menghitung cumsum
            df_sorted = df.sort_values(by="Tanggal").copy()
            
            if not df_sorted.empty:
                df_sorted['Perubahan'] = df_sorted.apply(
                    lambda row: row['Jumlah'] if row['Tipe'] == 'Pemasukan' else -row['Jumlah'], 
                    axis=1
                )
                df_sorted['Saldo Kumulatif'] = df_sorted['Perubahan'].cumsum()

                line_chart = alt.Chart(df_sorted).mark_line(point=True).encode(
                    x=alt.X('Tanggal', title='Tanggal'),
                    y=alt.Y('Saldo Kumulatif', title='Saldo (Rp)'),
                    tooltip=['Tanggal', 'Tipe', 'Kategori', 'Jumlah', 'Saldo Kumulatif']
                ).interactive()
                st.altair_chart(line_chart, use_container_width=True)
            else:
                st.write("Data arus kas belum cukup.")

        st.divider()

        # --- 3. Tabel Data (Catatan Keuangan) ---
        st.header("📚 Seluruh Catatan Transaksi")
        st.dataframe(
            df.sort_values(by="Tanggal", ascending=False), 
            use_container_width=True,
            column_config={
                "Jumlah": st.column_config.NumberColumn(format="Rp %f"),
                "Tanggal": st.column_config.DateColumn(format="DD/MM/YYYY")
            }
        )
else:
    st.error("Aplikasi tidak dapat berjalan tanpa koneksi ke Google Sheets. Silakan periksa file 'secrets.toml' Anda.")
