import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime, date
import gspread
import plotly.graph_objects as go 

# --- Konfigurasi Halaman ---
st.set_page_config(
    page_title="Dashboard Keuangan MAKSIMAL",
    page_icon="🚀", 
    layout="wide"
)

# --- Judul Utama ---
st.title("🚀✨ Dashboard Keuangan Keluarga (Versi MAKSIMAL)")
st.caption(f"Versi 4.3 (Fix NameError) | Tersambung ke Google Sheets 📄 | Data per: {datetime.now().strftime('%d %B %Y')}")

# --- ====================================================== ---
# ---               FUNGSI HELPER VISUALISASI              ---
# --- ====================================================== ---

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
        fontSize=24,
        fontWeight="bold",
        color="#FFFFFF"
    ).encode(
        text=alt.Text('Total', format=',.0f'),
    )
    
    chart = donut + text_total
    # FIX: Mengganti use_container_width dengan width='stretch'
    st.altair_chart(chart, use_container_width=True) # Altair masih pakai use_container_width

def create_calendar_heatmap(df, year_month):
    """Membuat Calendar Heatmap pengeluaran untuk bulan yang dipilih."""
    df_month = df[
        (df['Tipe'] == 'Pengeluaran') & 
        (df['Tanggal'].dt.strftime('%Y-%m') == year_month)
    ]
    
    if df_month.empty:
        st.info("Tidak ada data pengeluaran untuk bulan yang dipilih.")
        return

    df_daily_spend = df_month.groupby(df_month['Tanggal'].dt.date)['Jumlah'].sum().reset_index()
    df_daily_spend['Tanggal'] = pd.to_datetime(df_daily_spend['Tanggal'])
    
    start_date_dt = datetime.strptime(year_month, '%Y-%m').date()
    end_date_dt = (start_date_dt + pd.offsets.MonthEnd(1)).date()
    all_days = pd.date_range(start_date_dt, end_date_dt, freq='D')
    df_calendar = pd.DataFrame(all_days, columns=['Tanggal'])
    
    df_calendar = pd.merge(df_calendar, df_daily_spend, on='Tanggal', how='left').fillna(0)
    
    df_calendar['day'] = df_calendar['Tanggal'].dt.day
    df_calendar['week'] = df_calendar['Tanggal'].dt.isocalendar().week
    df_calendar['weekday'] = df_calendar['Tanggal'].dt.dayofweek # Senin=0, Minggu=6
    
    # --- PERBAIKAN BUG HEATMAP ---
    day_labels = "['Sen', 'Sel', 'Rab', 'Kam', 'Jum', 'Sab', 'Min'][datum.value]"
    
    heatmap = alt.Chart(df_calendar).mark_rect(stroke='black', strokeWidth=1).encode(
        x=alt.X('week:O', title='Minggu ke-', axis=alt.Axis(labels=True, ticks=True, domain=False)),
        y=alt.Y('weekday:O', title='Hari', axis=alt.Axis(labelExpr=day_labels, domain=False, ticks=False)),
        color=alt.Color('Jumlah', title='Pengeluaran', scale=alt.Scale(range='heatmap'), legend=alt.Legend(direction='horizontal', orient='bottom')),
        tooltip=[
            alt.Tooltip('Tanggal', format='%Y-%m-%d', title='Tanggal'),
            alt.Tooltip('Jumlah', format=',.0f', title='Total Pengeluaran')
        ],
        text=alt.Text('day')
    ).properties(
        title=f"Peta Panas Pengeluaran Bulan {year_month}"
    )
    
    st.altair_chart(heatmap + heatmap.mark_text(baseline='middle', color='black'), use_container_width=True) # Altair masih pakai use_container_width
    # --- AKHIR PERBAIKAN ---

def create_sankey_chart(df, key):
    """Membuat Sankey Diagram aliran dana dengan key unik."""
    
    # --- PERBAIKAN BUG "NameError" ---
    # Baris ini tidak sengaja terhapus di v4.2
    df_pemasukan = df[df['Tipe'] == 'Pemasukan']
    # --- AKHIR PERBAIKAN ---
    
    df_pengeluaran = df[df['Tipe'] == 'Pengeluaran']
    
    if df_pemasukan.empty or df_pengeluaran.empty:
        st.info("Data Pemasukan atau Pengeluaran tidak lengkap untuk membuat diagram alir.")
        return

    labels = []
    
    sumber_pemasukan = df_pemasukan['Kategori'].unique().tolist()
    labels.extend(sumber_pemasukan)
    
    node_total_pemasukan_idx = len(labels)
    labels.append("Total Pemasukan")
    
    node_total_pengeluaran_idx = len(labels)
    labels.append("Total Pengeluaran")

    kategori_pengeluaran = df_pengeluaran['Kategori'].unique().tolist()
    labels.extend(kategori_pengeluaran)
    
    label_to_idx = {label: i for i, label in enumerate(labels)}
    
    source_nodes = []
    target_nodes = []
    values = []
    
    df_agg_pemasukan = df_pemasukan.groupby('Kategori')['Jumlah'].sum()
    for kategori, jumlah in df_agg_pemasukan.items():
        source_nodes.append(label_to_idx[kategori])
        target_nodes.append(node_total_pemasukan_idx)
        values.append(jumlah)
        
    total_pemasukan = df_agg_pemasukan.sum()
    
    total_pengeluaran = df_pengeluaran['Jumlah'].sum()
    if total_pengeluaran > 0:
        source_nodes.append(node_total_pemasukan_idx)
        target_nodes.append(node_total_pengeluaran_idx)
        values.append(total_pengeluaran) 

    df_agg_pengeluaran = df_pengeluaran.groupby('Kategori')['Jumlah'].sum()
    for kategori, jumlah in df_agg_pengeluaran.items():
        source_nodes.append(node_total_pengeluaran_idx)
        target_nodes.append(label_to_idx[kategori])
        values.append(jumlah)

    sisa = total_pemasukan - total_pengeluaran
    if sisa > 0:
        node_tabungan_idx = len(labels)
        labels.append("Sisa Dana (Tabungan)")
        
        source_nodes.append(node_total_pemasukan_idx)
        target_nodes.append(node_tabungan_idx)
        values.append(sisa)

    fig = go.Figure(data=[go.Sankey(
        node=dict(
            pad=15,
            thickness=20,
            line=dict(color="black", width=0.5),
            label=labels,
            color="blue"
        ),
        link=dict(
            source=source_nodes,
            target=target_nodes,
            value=values
        )
    )])
    
    fig.update_layout(title_text="Diagram Alir Keuangan (Sankey)", font_size=12, template="plotly_dark")
    st.plotly_chart(fig, use_container_width=True, key=key) 


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

# --- Fungsi Load Data (Tanpa Cache) ---
def load_data(ws):
    """Membaca semua data dari worksheet dan mengubahnya jadi DataFrame."""
    try:
        data = ws.get_all_records()
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
        
        df = df[df['Jumlah'] > 0]
        
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
    jumlah = st.number_input("Jumlah (Rp)", min_value=1.0, step=1000.0, format="%.2f") 
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
            st.rerun() # Menggunakan st.rerun() yang lebih baru
            
    except Exception as e:
        st.sidebar.error(f"Gagal menyimpan ke GSheet: {e}")
elif submitted:
    st.sidebar.error("Koneksi GSheet gagal, tidak bisa menambah transaksi.")

# --- ====================================================== ---
# ---               MAIN DASHBOARD (VERSI MAKSIMAL)          ---
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
            
        all_kategori = df['Kategori'].unique().tolist() 
        selected_kategori = st.multiselect("Filter Kategori", all_kategori, default=all_kategori)
        
        st.divider()

        # --- 2. LOGIKA FILTERISASI DATA ---
        if not isinstance(start_date, date): start_date = min_date
        if not isinstance(end_date, date): end_date = max_date

        df_filtered = df[
            (df['Tanggal'].dt.date >= start_date) &
            (df['Tanggal'].dt.date <= end_date) &
            (df['Kategori'].isin(selected_kategori))
        ]

        if df_filtered.empty:
            st.warning("Tidak ada data transaksi yang sesuai dengan filter Anda.")
        else:
            # --- 3. TAMPILAN TAB ---
            tab_ringkasan, tab_analisis, tab_bulanan, tab_data = st.tabs(
                ["📊 Ringkasan", "📈 Analisis Proporsi", "📅 Analisis Bulanan", "📚 Data Transaksi"]
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

                col1, col2, col3 = st.columns([1.5, 1.5, 2])
                col1.metric("Total Pemasukan", f"Rp {total_pemasukan:,.0f}", "👍")
                col2.metric("Total Pengeluaran", f"Rp {total_pengeluaran:,.0f}", "👎", delta_color="inverse")
                
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

                st.subheader("Pemasukan vs. Pengeluaran Harian")
                df_grouped = df_filtered.groupby(['Tanggal', 'Tipe'])['Jumlah'].sum().reset_index()
                
                bar_chart = alt.Chart(df_grouped).mark_bar().encode(
                    x=alt.X('Tanggal', title='Tanggal', axis=alt.Axis(format="%Y-%m-%d")),
                    y=alt.Y('Jumlah', title='Jumlah (Rp)'),
                    color=alt.Color('Tipe', title='Tipe', scale=alt.Scale(domain=['Pemasukan', 'Pengeluaran'], range=['green', 'red'])),
                    tooltip=['Tanggal', 'Tipe', 'Jumlah']
                ).interactive()
                st.altair_chart(bar_chart, use_container_width=True)

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

            # --- TAB 2: ANALISIS PROPORSI ---
            with tab_analisis:
                st.subheader("Analisis Proporsi (Sesuai Filter)")
                
                col_donut1, col_donut2 = st.columns(2)
                
                with col_donut1:
                    df_chart_pengeluaran = df_filtered[df_filtered["Tipe"] == "Pengeluaran"].groupby("Kategori")["Jumlah"].sum().reset_index()
                    create_donut_chart(df_chart_pengeluaran, "Proporsi Pengeluaran")

                with col_donut2:
                    df_chart_pemasukan = df_filtered[df_filtered["Tipe"] == "Pemasukan"].groupby("Kategori")["Jumlah"].sum().reset_index()
                    create_donut_chart(df_chart_pemasukan, "Proporsi Pemasukan")
                
                st.divider()
                
                st.subheader("Top 5 Kategori Pengeluaran (Sesuai Filter)")
                df_top_5 = df_chart_pengeluaran.sort_values(by="Jumlah", ascending=False).head(5).reset_index(drop=True)
                df_top_5.index = df_top_5.index + 1
                st.dataframe(
                    df_top_5,
                    use_container_width=True,
                    column_config={
                        "Jumlah": st.column_config.NumberColumn("Jumlah (Rp)", format="Rp %'.0f"),
                        "Kategori": st.column_config.TextColumn("Kategori"),
                    }
                )
                
                st.divider()
                
                st.subheader("Diagram Alir Dana / Sankey (Sesuai Filter)")
                create_sankey_chart(df_filtered, key="sankey_filtered")

            # --- TAB 3: ANALISIS BULANAN (BARU) ---
            with tab_bulanan:
                st.subheader("Deep Dive Analisis Bulanan")
                
                df['Bulan-Tahun'] = df['Tanggal'].dt.strftime('%Y-%m')
                bulan_tersedia = df['Bulan-Tahun'].sort_values(ascending=False).unique().tolist()
                
                if not bulan_tersedia:
                    st.warning("Tidak ada data bulanan yang bisa dianalisis.")
                else:
                    selected_month = st.selectbox("Pilih Bulan untuk Analisis", bulan_tersedia)
                    
                    st.divider()
                    
                    create_calendar_heatmap(df, selected_month)
                    
                    st.divider()
                    
                    st.subheader(f"Diagram Alir Dana (Sankey) - Bulan {selected_month}")
                    df_sankey_bulanan = df[df['Bulan-Tahun'] == selected_month]
                    create_sankey_chart(df_sankey_bulanan, key="sankey_monthly")


            # --- TAB 4: DATA TRANSAKSI ---
            with tab_data:
                st.subheader("Data Transaksi (Sesuai Filter)")
                
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
                    height=500,
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
