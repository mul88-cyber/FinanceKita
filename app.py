import streamlit as st
import pandas as pd
import altair as alt
import plotly.graph_objects as go
from datetime import datetime, date, timedelta
import gspread
import time
import io
from dateutil.relativedelta import relativedelta
import hashlib
import json

# --- Konfigurasi Halaman ---
st.set_page_config(
    page_title="Dashboard FinanceKita PRO",
    page_icon="💸", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Custom CSS untuk UI yang lebih baik ---
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem !important;
        font-weight: 800 !important;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        padding-bottom: 10px;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 15px;
        padding: 20px;
        color: white;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    .stProgress > div > div > div > div {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
    }
    .sidebar-header {
        font-size: 1.5rem !important;
        font-weight: 700 !important;
        color: #764ba2 !important;
        margin-top: 10px;
        margin-bottom: 10px;
    }
    .quick-action-btn {
        width: 100%;
        margin: 5px 0;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white !important;
        border: none;
    }
    .quick-action-btn:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
    }
    .dataframe tbody tr:hover {
        background-color: rgba(102, 126, 234, 0.1) !important;
    }
</style>
""", unsafe_allow_html=True)

# --- Judul Utama ---
st.markdown('<h1 class="main-header">💸 Dashboard FinanceKita PRO</h1>', unsafe_allow_html=True)
st.caption(f"🚀 Versi 5.0 | Tersambung ke Google Sheets | Data per: {datetime.now().strftime('%d %B %Y %H:%M')}")

# --- ====================================================== ---
# ---               FUNGSI HELPER VISUALISASI              ---
# --- ====================================================== ---

def create_donut_chart(df, title, color_scheme="category10"):
    """Membuat Donut Chart Altair dari DataFrame dengan color scheme."""
    if df.empty or df["Jumlah"].sum() == 0:
        st.info(f"Tidak ada data untuk {title.lower()}.")
        return None

    total = df["Jumlah"].sum()
    df['Persentase'] = (df['Jumlah'] / total)
    df['Display'] = df.apply(lambda x: f"{x['Kategori']}: Rp{x['Jumlah']:,.0f} ({x['Persentase']:.1%})", axis=1)

    base = alt.Chart(df).encode(
        theta=alt.Theta("Jumlah:Q", stack=True),
        order=alt.Order("Jumlah:Q", sort="descending")
    ).properties(
        title=alt.TitleParams(
            text=title,
            fontSize=16,
            fontWeight="bold"
        ),
        height=300
    )

    donut = base.mark_arc(outerRadius=120, innerRadius=80).encode(
        color=alt.Color("Kategori:N", 
                       legend=alt.Legend(title="Kategori", columns=2),
                       scale=alt.Scale(scheme=color_scheme)),
        tooltip=[alt.Tooltip("Kategori:N", title="Kategori"),
                alt.Tooltip("Jumlah:Q", title="Jumlah", format=",.0f"),
                alt.Tooltip("Persentase:Q", title="Persentase", format=".1%")]
    )

    text_total = alt.Chart(pd.DataFrame({'Total': [f"Rp{total:,.0f}"]})).mark_text(
        align='center', 
        baseline='middle', 
        fontSize=20,
        fontWeight="bold",
        color="#FFFFFF"
    ).encode(
        text=alt.Text('Total:N'),
    )
    
    return donut + text_total

def create_calendar_heatmap(df, year_month):
    """Membuat Calendar Heatmap pengeluaran untuk bulan yang dipilih."""
    df_month = df[
        (df['Tipe'] == 'Pengeluaran') & 
        (df['Tanggal'].dt.strftime('%Y-%m') == year_month)
    ]
    
    if df_month.empty:
        st.info("Tidak ada data pengeluaran untuk bulan yang dipilih.")
        return None

    df_daily_spend = df_month.groupby(df_month['Tanggal'].dt.date)['Jumlah'].sum().reset_index()
    df_daily_spend['Tanggal'] = pd.to_datetime(df_daily_spend['Tanggal'])
    
    start_date_dt = datetime.strptime(year_month, '%Y-%m').date()
    end_date_dt = (start_date_dt + pd.offsets.MonthEnd(1)).date()
    all_days = pd.date_range(start_date_dt, end_date_dt, freq='D')
    df_calendar = pd.DataFrame(all_days, columns=['Tanggal'])
    
    df_calendar = pd.merge(df_calendar, df_daily_spend, on='Tanggal', how='left').fillna(0)
    
    df_calendar['day'] = df_calendar['Tanggal'].dt.day
    df_calendar['week'] = df_calendar['Tanggal'].dt.isocalendar().week
    df_calendar['weekday'] = df_calendar['Tanggal'].dt.dayofweek
    
    day_labels = "['Sen', 'Sel', 'Rab', 'Kam', 'Jum', 'Sab', 'Min'][datum.value]"
    
    heatmap = alt.Chart(df_calendar).mark_rect(stroke='white', strokeWidth=1).encode(
        x=alt.X('week:O', title='Minggu ke-', 
                axis=alt.Axis(labels=True, ticks=True, domain=False, labelAngle=0)),
        y=alt.Y('weekday:O', title='Hari', 
                axis=alt.Axis(labelExpr=day_labels, domain=False, ticks=False)),
        color=alt.Color('Jumlah:Q', title='Pengeluaran (Rp)', 
                       scale=alt.Scale(scheme='reds'), 
                       legend=alt.Legend(direction='horizontal', orient='bottom')),
        tooltip=[
            alt.Tooltip('Tanggal:T', format='%A, %d %B %Y', title='Tanggal'),
            alt.Tooltip('Jumlah:Q', format=',.0f', title='Total Pengeluaran')
        ]
    ).properties(
        title=alt.TitleParams(
            text=f"Peta Panas Pengeluaran Bulan {year_month}",
            fontSize=16,
            fontWeight="bold"
        ),
        height=250
    )
    
    text = heatmap.mark_text(baseline='middle', fontSize=11, fontWeight='bold').encode(
        text='day:O',
        color=alt.condition(
            alt.datum.Jumlah > df_calendar['Jumlah'].quantile(0.75),
            alt.value('white'),
            alt.value('black')
        )
    )
    
    return heatmap + text

def create_sankey_chart(df, title):
    """Membuat Sankey Diagram aliran dana."""
    df_pemasukan = df[df['Tipe'] == 'Pemasukan']
    df_pengeluaran = df[df['Tipe'] == 'Pengeluaran']
    
    if df_pemasukan.empty or df_pengeluaran.empty:
        return None

    labels = []
    sumber_pemasukan = df_pemasukan['Kategori'].unique().tolist()
    labels.extend(sumber_pemasukan)
    
    node_total_pemasukan_idx = len(labels)
    labels.append("TOTAL PEMASUKAN")
    
    node_total_pengeluaran_idx = len(labels)
    labels.append("TOTAL PENGELUARAN")

    kategori_pengeluaran = df_pengeluaran['Kategori'].unique().tolist()
    labels.extend(kategori_pengeluaran)
    
    label_to_idx = {label: i for i, label in enumerate(labels)}
    
    source_nodes = []
    target_nodes = []
    values = []
    colors = []
    
    df_agg_pemasukan = df_pemasukan.groupby('Kategori')['Jumlah'].sum()
    for kategori, jumlah in df_agg_pemasukan.items():
        source_nodes.append(label_to_idx[kategori])
        target_nodes.append(node_total_pemasukan_idx)
        values.append(jumlah)
        colors.append("rgba(0, 200, 83, 0.8)")
        
    total_pemasukan = df_agg_pemasukan.sum()
    total_pengeluaran = df_pengeluaran['Jumlah'].sum()
    
    if total_pengeluaran > 0:
        source_nodes.append(node_total_pemasukan_idx)
        target_nodes.append(node_total_pengeluaran_idx)
        values.append(total_pengeluaran)
        colors.append("rgba(255, 193, 7, 0.8)")

    df_agg_pengeluaran = df_pengeluaran.groupby('Kategori')['Jumlah'].sum()
    for kategori, jumlah in df_agg_pengeluaran.items():
        source_nodes.append(node_total_pengeluaran_idx)
        target_nodes.append(label_to_idx[kategori])
        values.append(jumlah)
        colors.append("rgba(244, 67, 54, 0.8)")

    sisa = total_pemasukan - total_pengeluaran
    if sisa > 0:
        node_tabungan_idx = len(labels)
        labels.append("💎 TABUNGAN")
        
        source_nodes.append(node_total_pemasukan_idx)
        target_nodes.append(node_tabungan_idx)
        values.append(sisa)
        colors.append("rgba(33, 150, 243, 0.8)")

    fig = go.Figure(data=[go.Sankey(
        arrangement="snap",
        node=dict(
            pad=25,
            thickness=25,
            line=dict(color="black", width=1),
            label=labels,
            color="rgba(100, 126, 234, 0.8)",
            hovertemplate='%{label}: Rp%{value:.0f}<extra></extra>'
        ),
        link=dict(
            source=source_nodes,
            target=target_nodes,
            value=values,
            color=colors,
            hovertemplate='Dana mengalir: Rp%{value:.0f}<extra></extra>'
        )
    )])
    
    fig.update_layout(
        title_text=f"<b>{title}</b>",
        font_size=12,
        height=500,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)'
    )
    
    return fig

def create_monthly_trend_chart(df):
    """Membuat chart trend bulanan."""
    df_monthly = df.copy()
    df_monthly['Bulan'] = df_monthly['Tanggal'].dt.to_period('M').astype(str)
    
    monthly_summary = df_monthly.groupby(['Bulan', 'Tipe'])['Jumlah'].sum().unstack(fill_value=0)
    monthly_summary['Saldo'] = monthly_summary.get('Pemasukan', 0) - monthly_summary.get('Pengeluaran', 0)
    monthly_summary = monthly_summary.reset_index()
    
    base = alt.Chart(monthly_summary).encode(
        x=alt.X('Bulan:N', title='Bulan', axis=alt.Axis(labelAngle=-45))
    )
    
    bars_pemasukan = base.mark_bar(size=25).encode(
        y=alt.Y('Pemasukan:Q', title='Jumlah (Rp)'),
        color=alt.value('#4CAF50'),
        tooltip=['Bulan', alt.Tooltip('Pemasukan:Q', format=',.0f', title='Pemasukan')]
    )
    
    bars_pengeluaran = base.mark_bar(size=25).encode(
        y=alt.Y('Pengeluaran:Q'),
        color=alt.value('#F44336'),
        tooltip=['Bulan', alt.Tooltip('Pengeluaran:Q', format=',.0f', title='Pengeluaran')]
    )
    
    line_saldo = base.mark_line(point=True, strokeWidth=3).encode(
        y=alt.Y('Saldo:Q', title='Saldo'),
        color=alt.value('#2196F3'),
        tooltip=['Bulan', alt.Tooltip('Saldo:Q', format=',.0f', title='Saldo')]
    )
    
    return alt.layer(bars_pemasukan, bars_pengeluaran, line_saldo).resolve_scale(
        y='independent'
    ).properties(
        title="Trend Bulanan - Pemasukan, Pengeluaran & Saldo",
        height=350
    )

# --- ====================================================== ---
# ---              FUNGSI UTILITAS & CACHING               ---
# --- ====================================================== ---

def get_data_hash():
    """Generate hash berdasarkan timestamp untuk cache invalidation."""
    return datetime.now().strftime("%Y%m%d%H")

# Cache data dengan cara yang compatible
def load_data_with_cache(ws, cache_key=None):
    """Membaca data dengan caching yang aman."""
    try:
        # Cek session state untuk cached data
        if 'cached_data' in st.session_state and 'cache_key' in st.session_state:
            if st.session_state.cache_key == get_data_hash():
                return st.session_state.cached_data
        
        # Jika tidak ada cache atau cache expired, load data baru
        data = ws.get_all_records()
        if not data:
            df = pd.DataFrame(columns=["Tanggal", "Tipe", "Kategori", "Jumlah", "Catatan"])
        else:
            df = pd.DataFrame(data)
            
            required_cols = ["Tanggal", "Tipe", "Kategori", "Jumlah", "Catatan"]
            for col in required_cols:
                if col not in df.columns:
                    df[col] = None
            
            df['Tanggal'] = pd.to_datetime(df['Tanggal'], errors='coerce')
            df['Jumlah'] = pd.to_numeric(df['Jumlah'], errors='coerce').fillna(0)
            df.dropna(subset=['Tanggal'], inplace=True)
            df = df[df['Jumlah'] > 0]
        
        # Simpan ke session state
        st.session_state.cached_data = df
        st.session_state.cache_key = get_data_hash()
        st.session_state.last_refresh = datetime.now()
        
        return df
        
    except Exception as e:
        st.error(f"Gagal membaca data: {e}")
        return pd.DataFrame(columns=["Tanggal", "Tipe", "Kategori", "Jumlah", "Catatan"])

def forecast_next_month(df):
    """Prediksi pengeluaran bulan depan."""
    try:
        df_monthly = df[df['Tipe'] == 'Pengeluaran'].copy()
        df_monthly['Bulan'] = df_monthly['Tanggal'].dt.to_period('M')
        monthly_totals = df_monthly.groupby('Bulan')['Jumlah'].sum().tail(3)
        
        if len(monthly_totals) >= 2:
            weights = [0.5, 0.3, 0.2][:len(monthly_totals)]
            forecast = (monthly_totals * weights[:len(monthly_totals)]).sum()
            return forecast
    except:
        pass
    return None

def calculate_budget_vs_actual(df, budget_settings):
    """Menghitung perbandingan budget vs actual spending."""
    results = []
    df_pengeluaran = df[df['Tipe'] == 'Pengeluaran'].copy()
    
    for category, budget in budget_settings.items():
        # Cari kategori yang mengandung nama category (case-insensitive)
        actual = 0
        for cat in df_pengeluaran['Kategori'].unique():
            if category.lower() in cat.lower():
                actual += df_pengeluaran[df_pengeluaran['Kategori'] == cat]['Jumlah'].sum()
        
        if budget > 0:
            percentage = (actual / budget) * 100
            status = "🟢" if percentage <= 80 else "🟡" if percentage <= 100 else "🔴"
            results.append({
                'Kategori': category,
                'Budget': budget,
                'Actual': actual,
                'Percentage': percentage,
                'Status': status
            })
    
    return pd.DataFrame(results)

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
    st.error(f"❌ Gagal terhubung ke Google Sheets: {e}")
    GSHEET_CONNECTED = False
    worksheet = None

# --- ====================================================== ---
# ---                     SIDEBAR                          ---
# --- ====================================================== ---

with st.sidebar:
    st.markdown('<h3 class="sidebar-header">📝 Input Transaksi</h3>', unsafe_allow_html=True)
    
    tipe = st.radio("**Tipe Transaksi**", ["Pemasukan", "Pengeluaran"], 
                    horizontal=True, index=1, label_visibility="collapsed")
    
    if tipe == "Pengeluaran":
        kategori_options = ["🏠 Rumah Tangga", "🍔 Makanan", "🚗 Transportasi", 
                           "🧾 Tagihan", "👨‍⚕️ Kesehatan", "🎉 Hiburan", 
                           "📚 Pendidikan", "🛒 Belanja", "🎁 Hadiah/Amal", "Lainnya"]
    else:
        kategori_options = ["💼 Gaji", "💰 Bonus", "📈 Investasi", 
                           "💻 Freelance", "🎁 Hadiah", "Lainnya"]
    
    with st.form("transaction_form", clear_on_submit=True):
        tanggal = st.date_input("📅 Tanggal", datetime.now())
        kategori = st.selectbox("🏷️ Kategori", kategori_options)
        jumlah = st.number_input("💰 Jumlah (Rp)", min_value=1.0, step=1000.0, 
                                format="%.0f", help="Masukkan jumlah tanpa titik")
        catatan = st.text_area("📝 Catatan (Opsional)", height=80,
                              placeholder="Deskripsi transaksi...")
        
        submitted = st.form_submit_button("✅ **Tambah Transaksi**", use_container_width=True)
    
    # --- QUICK ACTIONS ---
    st.markdown('<h3 class="sidebar-header">⚡ Quick Actions</h3>', unsafe_allow_html=True)
    
    quick_actions = {
        "🍔 Makan Siang": 50000,
        "☕ Kopi": 25000,
        "⛽ Bensin": 150000,
        "📦 GrabFood": 75000,
        "🛒 Minimarket": 100000,
    }
    
    cols = st.columns(2)
    for idx, (name, amount) in enumerate(quick_actions.items()):
        with cols[idx % 2]:
            if st.button(f"{name}\nRp{amount:,}", 
                         use_container_width=True,
                         key=f"quick_{idx}"):
                # Auto-fill form dengan session state
                st.session_state.quick_amount = amount
                st.session_state.quick_category = name.split(" ")[1] if " " in name else name
                st.rerun()
    
    # --- BUDGET SETTINGS ---
    st.markdown('<h3 class="sidebar-header">🎯 Budget Bulanan</h3>', unsafe_allow_html=True)
    
    # Initialize budget settings in session state
    if 'budget_settings' not in st.session_state:
        st.session_state.budget_settings = {
            "Makanan": 1000000,
            "Transportasi": 500000,
            "Hiburan": 300000,
            "Belanja": 800000
        }
    
    budget_categories = ["Makanan", "Transportasi", "Hiburan", "Belanja"]
    for cat in budget_categories:
        st.session_state.budget_settings[cat] = st.number_input(
            f"Budget {cat}", 
            min_value=0, 
            value=st.session_state.budget_settings[cat],
            step=100000,
            key=f"budget_{cat}"
        )
    
    # --- REFRESH DATA ---
    st.markdown('<h3 class="sidebar-header">🔄 Refresh Data</h3>', unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Refresh", use_container_width=True):
            # Clear cache
            if 'cached_data' in st.session_state:
                del st.session_state.cached_data
            if 'cache_key' in st.session_state:
                del st.session_state.cache_key
            st.rerun()
    
    with col2:
        if st.button("📊 Stats", use_container_width=True):
            st.session_state.show_stats = True
    
    # --- EXPORT DATA ---
    st.markdown('<h3 class="sidebar-header">💾 Export Data</h3>', unsafe_allow_html=True)
    
    if st.button("📥 Export CSV", use_container_width=True):
        if GSHEET_CONNECTED and worksheet:
            df = load_data_with_cache(worksheet)
            csv = df.to_csv(index=False)
            st.download_button(
                label="Download CSV",
                data=csv,
                file_name=f"finance_backup_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv",
                use_container_width=True
            )

# --- Logika untuk Menambah Transaksi ---
if submitted and GSHEET_CONNECTED:
    try:
        if jumlah <= 0:
            st.sidebar.warning("❌ Jumlah harus lebih besar dari 0.")
        else:
            with st.sidebar:
                with st.spinner("Menyimpan transaksi..."):
                    new_row = [
                        tanggal.strftime("%Y-%m-%d"), 
                        tipe,
                        kategori,
                        jumlah,
                        catatan or ""
                    ]
                    all_values = worksheet.get_all_values()
                    if not all_values:
                        header = ["Tanggal", "Tipe", "Kategori", "Jumlah", "Catatan"]
                        worksheet.append_row(header)
                    worksheet.append_row(new_row)
                    
                    # Clear cache agar data terbaru di-load
                    if 'cached_data' in st.session_state:
                        del st.session_state.cached_data
                    
                    time.sleep(1)
                    st.success("✅ Transaksi berhasil ditambahkan!")
                    time.sleep(1.5)
                    st.rerun()
    except Exception as e:
        st.sidebar.error(f"❌ Gagal menyimpan: {e}")
elif submitted:
    st.sidebar.error("❌ Koneksi GSheet gagal, tidak bisa menambah transaksi.")

# --- ====================================================== ---
# ---               MAIN DASHBOARD                          ---
# --- ====================================================== ---

if GSHEET_CONNECTED:
    # Load data dengan caching yang aman
    df = load_data_with_cache(worksheet)
    
    if df.empty:
        st.info("📭 Belum ada transaksi di Google Sheet. Mulai dengan menambahkan transaksi di sidebar!")
        st.balloons()
    else:
        # --- 1. FILTER DATA ---
        st.header("🔍 Filter Dashboard")
        
        min_date = df['Tanggal'].min().date()
        max_date = df['Tanggal'].max().date()
        
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            start_date = st.date_input("Dari", min_date, min_value=min_date, max_value=max_date)
        with col2:
            end_date = st.date_input("Sampai", max_date, min_value=min_date, max_value=max_date)
        with col3:
            all_kategori = df['Kategori'].unique().tolist()
            selected_kategori = st.multiselect(
                "Kategori", 
                all_kategori, 
                default=all_kategori,
                placeholder="Pilih kategori..."
            )
        
        # --- Quick Date Range Buttons ---
        col_quick = st.columns(5)
        with col_quick[0]:
            if st.button("Hari Ini", use_container_width=True, key="btn_today"):
                start_date = datetime.now().date()
                end_date = start_date
        with col_quick[1]:
            if st.button("7 Hari", use_container_width=True, key="btn_7days"):
                end_date = datetime.now().date()
                start_date = end_date - timedelta(days=6)
        with col_quick[2]:
            if st.button("Bulan Ini", use_container_width=True, key="btn_month"):
                start_date = datetime.now().replace(day=1).date()
                end_date = datetime.now().date()
        with col_quick[3]:
            if st.button("3 Bulan", use_container_width=True, key="btn_3months"):
                end_date = datetime.now().date()
                start_date = end_date - relativedelta(months=3)
        with col_quick[4]:
            if st.button("Semua", use_container_width=True, key="btn_all"):
                start_date = min_date
                end_date = max_date
        
        st.divider()
        
        # --- 2. LOGIKA FILTERISASI DATA ---
        df_filtered = df[
            (df['Tanggal'].dt.date >= start_date) &
            (df['Tanggal'].dt.date <= end_date) &
            (df['Kategori'].isin(selected_kategori))
        ]
        
        if df_filtered.empty:
            st.warning("⚠️ Tidak ada data yang sesuai dengan filter Anda.")
        else:
            # --- 3. HEADER METRICS ---
            total_pemasukan = df_filtered[df_filtered["Tipe"] == "Pemasukan"]["Jumlah"].sum()
            total_pengeluaran = df_filtered[df_filtered["Tipe"] == "Pengeluaran"]["Jumlah"].sum()
            saldo = total_pemasukan - total_pengeluaran
            jumlah_transaksi = df_filtered.shape[0]
            
            total_hari = (end_date - start_date).days + 1
            avg_pengeluaran_harian = total_pengeluaran / total_hari if total_hari > 0 else 0
            
            # Forecast untuk bulan depan
            forecast = forecast_next_month(df)
            
            col1, col2, col3, col4, col5 = st.columns(5)
            
            with col1:
                st.markdown(f"""
                <div class="metric-card">
                    <div style="font-size: 0.9rem; opacity: 0.9;">Total Pemasukan</div>
                    <div style="font-size: 1.8rem; font-weight: bold;">Rp {total_pemasukan:,.0f}</div>
                    <div style="font-size: 0.8rem;">↑ {total_pemasukan/len(df_filtered[df_filtered["Tipe"] == "Pemasukan"]):,.0f}/transaksi</div>
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                st.markdown(f"""
                <div class="metric-card">
                    <div style="font-size: 0.9rem; opacity: 0.9;">Total Pengeluaran</div>
                    <div style="font-size: 1.8rem; font-weight: bold;">Rp {total_pengeluaran:,.0f}</div>
                    <div style="font-size: 0.8rem;">↓ {avg_pengeluaran_harian:,.0f}/hari</div>
                </div>
                """, unsafe_allow_html=True)
            
            with col3:
                saldo_color = "#4CAF50" if saldo >= 0 else "#F44336"
                st.markdown(f"""
                <div style="background: linear-gradient(135deg, {"#4CAF50" if saldo >= 0 else "#F44336"} 0%, {"#388E3C" if saldo >= 0 else "#D32F2F"} 100%); 
                            border-radius: 15px; padding: 20px; color: white; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                    <div style="font-size: 0.9rem; opacity: 0.9;">Saldo Akhir</div>
                    <div style="font-size: 1.8rem; font-weight: bold;">Rp {saldo:,.0f}</div>
                    <div style="font-size: 0.8rem;">{"🟢 Surplus" if saldo >= 0 else "🔴 Defisit"}</div>
                </div>
                """, unsafe_allow_html=True)
            
            with col4:
                st.markdown(f"""
                <div class="metric-card">
                    <div style="font-size: 0.9rem; opacity: 0.9;">Jumlah Transaksi</div>
                    <div style="font-size: 1.8rem; font-weight: bold;">{jumlah_transaksi:,}</div>
                    <div style="font-size: 0.8rem;">{len(df_filtered[df_filtered["Tipe"] == "Pemasukan"]):,} pemasukan, {len(df_filtered[df_filtered["Tipe"] == "Pengeluaran"]):,} pengeluaran</div>
                </div>
                """, unsafe_allow_html=True)
            
            with col5:
                forecast_text = f"Rp {forecast:,.0f}" if forecast else "Tidak cukup data"
                st.markdown(f"""
                <div class="metric-card">
                    <div style="font-size: 0.9rem; opacity: 0.9;">Prediksi Bulan Depan</div>
                    <div style="font-size: 1.5rem; font-weight: bold;">{forecast_text}</div>
                    <div style="font-size: 0.8rem;">Berdasarkan 3 bulan terakhir</div>
                </div>
                """, unsafe_allow_html=True)
            
            st.divider()
            
            # --- 4. TABS UTAMA ---
            tab1, tab2, tab3, tab4, tab5 = st.tabs([
                "📊 Ringkasan", 
                "📈 Analisis", 
                "📅 Kalender", 
                "💰 Budgeting", 
                "📋 Data"
            ])
            
            # --- TAB 1: RINGKASAN ---
            with tab1:
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("Cash Flow Harian")
                    df_daily = df_filtered.copy()
                    df_daily['Net'] = df_daily.apply(
                        lambda x: x['Jumlah'] if x['Tipe'] == 'Pemasukan' else -x['Jumlah'], 
                        axis=1
                    )
                    daily_net = df_daily.groupby('Tanggal')['Net'].sum().reset_index()
                    
                    if not daily_net.empty:
                        bar_chart = alt.Chart(daily_net).mark_bar(size=20).encode(
                            x=alt.X('Tanggal:T', title='Tanggal', axis=alt.Axis(format="%d %b")),
                            y=alt.Y('Net:Q', title='Net Flow (Rp)'),
                            color=alt.condition(
                                alt.datum.Net > 0,
                                alt.value('#4CAF50'),
                                alt.value('#F44336')
                            ),
                            tooltip=[
                                alt.Tooltip('Tanggal:T', format='%A, %d %B %Y'),
                                alt.Tooltip('Net:Q', format=',.0f', title='Net Flow')
                            ]
                        ).properties(height=300)
                        st.altair_chart(bar_chart, use_container_width=True)
                
                with col2:
                    st.subheader("Saldo Kumulatif")
                    df_cumulative = df_filtered.sort_values('Tanggal').copy()
                    df_cumulative['Perubahan'] = df_cumulative.apply(
                        lambda x: x['Jumlah'] if x['Tipe'] == 'Pemasukan' else -x['Jumlah'], 
                        axis=1
                    )
                    df_cumulative['Saldo Kumulatif'] = df_cumulative['Perubahan'].cumsum()
                    
                    if not df_cumulative.empty:
                        area_chart = alt.Chart(df_cumulative).mark_area(
                            line={'color': '#2196F3'},
                            color=alt.Gradient(
                                gradient='linear',
                                stops=[alt.GradientStop(color='#2196F3', offset=0),
                                      alt.GradientStop(color='rgba(33, 150, 243, 0.1)', offset=1)],
                                x1=0, x2=0, y1=1, y2=0
                            )
                        ).encode(
                            x=alt.X('Tanggal:T', title='Tanggal'),
                            y=alt.Y('Saldo Kumulatif:Q', title='Saldo (Rp)'),
                            tooltip=['Tanggal:T', 'Saldo Kumulatif:Q']
                        ).properties(height=300)
                        st.altair_chart(area_chart, use_container_width=True)
                
                # Trend Bulanan
                st.subheader("Trend Bulanan")
                trend_chart = create_monthly_trend_chart(df)
                if trend_chart:
                    st.altair_chart(trend_chart, use_container_width=True)
            
            # --- TAB 2: ANALISIS ---
            with tab2:
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("Proporsi Pengeluaran")
                    df_pengeluaran = df_filtered[df_filtered["Tipe"] == "Pengeluaran"]
                    if not df_pengeluaran.empty:
                        df_chart_pengeluaran = df_pengeluaran.groupby("Kategori")["Jumlah"].sum().reset_index()
                        donut_pengeluaran = create_donut_chart(df_chart_pengeluaran, "Pengeluaran", "reds")
                        if donut_pengeluaran:
                            st.altair_chart(donut_pengeluaran, use_container_width=True)
                    
                    # Top 5 Pengeluaran
                    st.subheader("🔥 Top 5 Pengeluaran")
                    if not df_pengeluaran.empty:
                        df_top5 = df_pengeluaran.groupby('Kategori')['Jumlah'].sum().nlargest(5).reset_index()
                        df_top5.index = range(1, len(df_top5) + 1)
                        
                        for idx, row in df_top5.iterrows():
                            percent = (row['Jumlah'] / df_pengeluaran['Jumlah'].sum()) * 100
                            st.progress(min(percent/100, 1.0), 
                                       text=f"{row['Kategori']}: Rp{row['Jumlah']:,.0f} ({percent:.1f}%)")
                
                with col2:
                    st.subheader("Proporsi Pemasukan")
                    df_pemasukan = df_filtered[df_filtered["Tipe"] == "Pemasukan"]
                    if not df_pemasukan.empty:
                        df_chart_pemasukan = df_pemasukan.groupby("Kategori")["Jumlah"].sum().reset_index()
                        donut_pemasukan = create_donut_chart(df_chart_pemasukan, "Pemasukan", "greens")
                        if donut_pemasukan:
                            st.altair_chart(donut_pemasukan, use_container_width=True)
                    
                    # Sankey Diagram
                    st.subheader("Diagram Alir Dana")
                    sankey = create_sankey_chart(df_filtered, "Aliran Dana")
                    if sankey:
                        st.plotly_chart(sankey, use_container_width=True)
            
            # --- TAB 3: KALENDER ---
            with tab3:
                st.subheader("Kalender Pengeluaran")
                
                # Pilih bulan
                df['Bulan-Tahun'] = df['Tanggal'].dt.strftime('%Y-%m')
                available_months = sorted(df['Bulan-Tahun'].unique(), reverse=True)
                
                if available_months:
                    selected_month = st.selectbox("Pilih Bulan", available_months, key="select_month")
                    
                    # Heatmap
                    heatmap = create_calendar_heatmap(df, selected_month)
                    if heatmap:
                        st.altair_chart(heatmap, use_container_width=True)
                    
                    # Statistik bulan tersebut
                    df_month = df[df['Bulan-Tahun'] == selected_month]
                    if not df_month.empty:
                        col_stat1, col_stat2, col_stat3 = st.columns(3)
                        with col_stat1:
                            total_month = df_month[df_month['Tipe'] == 'Pengeluaran']['Jumlah'].sum()
                            st.metric(f"Total Pengeluaran {selected_month}", f"Rp {total_month:,.0f}")
                        with col_stat2:
                            avg_daily = total_month / len(df_month['Tanggal'].dt.day.unique())
                            st.metric("Rata-rata Harian", f"Rp {avg_daily:,.0f}")
                        with col_stat3:
                            days_with_spending = len(df_month[df_month['Tipe'] == 'Pengeluaran']['Tanggal'].dt.day.unique())
                            total_days = len(df_month['Tanggal'].dt.day.unique())
                            st.metric("Hari dengan Pengeluaran", f"{days_with_spending}/{total_days}")
            
            # --- TAB 4: BUDGETING ---
            with tab4:
                st.subheader("Budget vs Actual Spending")
                
                # Hitung perbandingan budget vs actual
                budget_vs_actual = calculate_budget_vs_actual(df_filtered, st.session_state.budget_settings)
                
                if not budget_vs_actual.empty:
                    # Tampilkan sebagai tabel
                    st.dataframe(
                        budget_vs_actual,
                        column_config={
                            "Kategori": "Kategori",
                            "Budget": st.column_config.NumberColumn("Budget (Rp)", format="Rp %'.0f"),
                            "Actual": st.column_config.NumberColumn("Actual (Rp)", format="Rp %'.0f"),
                            "Percentage": st.column_config.ProgressColumn(
                                "Persentase",
                                format="%.1f%%",
                                min_value=0,
                                max_value=150,
                            ),
                            "Status": "Status"
                        },
                        use_container_width=True
                    )
                    
                    # Visualisasi perbandingan
                    st.subheader("Visualisasi Budget vs Actual")
                    
                    budget_chart_data = budget_vs_actual.melt(
                        id_vars=['Kategori', 'Status'],
                        value_vars=['Budget', 'Actual'],
                        var_name='Type',
                        value_name='Amount'
                    )
                    
                    budget_chart = alt.Chart(budget_chart_data).mark_bar().encode(
                        x=alt.X('Kategori:N', title='Kategori'),
                        y=alt.Y('Amount:Q', title='Jumlah (Rp)'),
                        color=alt.Color('Type:N', scale=alt.Scale(
                            domain=['Budget', 'Actual'],
                            range=['#4CAF50', '#FF9800']
                        )),
                        column='Type:N',
                        tooltip=['Kategori', 'Type', alt.Tooltip('Amount', format=',.0f')]
                    ).properties(
                        title='Perbandingan Budget vs Actual Spending',
                        height=300
                    )
                    
                    st.altair_chart(budget_chart, use_container_width=True)
                    
                    # Rekomendasi berdasarkan budget
                    st.subheader("💡 Rekomendasi")
                    for _, row in budget_vs_actual.iterrows():
                        if row['Percentage'] > 100:
                            st.warning(f"**{row['Kategori']}**: Melebihi budget sebesar {row['Percentage']-100:.1f}%. Perlu dikurangi pengeluarannya.")
                        elif row['Percentage'] > 80:
                            st.info(f"**{row['Kategori']}**: Mendekati limit budget ({row['Percentage']:.1f}%). Hati-hati dalam pengeluaran.")
                        else:
                            st.success(f"**{row['Kategori']}**: Masih dalam budget ({row['Percentage']:.1f}%). Bagus!")
                else:
                    st.info("Setel budget terlebih dahulu di sidebar untuk melihat analisis budgeting.")
            
            # --- TAB 5: DATA ---
            with tab5:
                st.subheader("Data Transaksi Lengkap")
                
                # Search dan filter tambahan
                col_search, col_sort = st.columns([2, 1])
                with col_search:
                    search_query = st.text_input("🔍 Cari di Catatan...", placeholder="Ketik untuk mencari...", key="search_input")
                
                with col_sort:
                    sort_by = st.selectbox("Urutkan berdasarkan", 
                                          ["Tanggal (Terbaru)", "Tanggal (Terlama)", "Jumlah (Terbesar)", "Jumlah (Terkecil)"],
                                          key="sort_select")
                
                # Apply search filter
                df_display = df_filtered.copy()
                if search_query:
                    df_display = df_display[df_display['Catatan'].astype(str).str.contains(search_query, case=False, na=False)]
                
                # Apply sorting
                if sort_by == "Tanggal (Terbaru)":
                    df_display = df_display.sort_values('Tanggal', ascending=False)
                elif sort_by == "Tanggal (Terlama)":
                    df_display = df_display.sort_values('Tanggal', ascending=True)
                elif sort_by == "Jumlah (Terbesar)":
                    df_display = df_display.sort_values('Jumlah', ascending=False)
                elif sort_by == "Jumlah (Terkecil)":
                    df_display = df_display.sort_values('Jumlah', ascending=True)
                
                # Tampilkan ringkasan
                with st.expander("📊 Ringkasan Kategori", expanded=False):
                    df_summary = df_filtered.groupby(['Tipe', 'Kategori'])['Jumlah'].agg(['sum', 'count']).reset_index()
                    df_summary = df_summary.rename(columns={'sum': 'Total', 'count': 'Jumlah Transaksi'})
                    
                    st.dataframe(
                        df_summary,
                        column_config={
                            "Total": st.column_config.NumberColumn("Total (Rp)", format="Rp %'.0f"),
                            "Jumlah Transaksi": "Jumlah Transaksi",
                            "Tipe": "Tipe",
                            "Kategori": "Kategori"
                        },
                        use_container_width=True
                    )
                
                # Tampilkan data transaksi
                st.dataframe(
                    df_display,
                    column_config={
                        "Tanggal": st.column_config.DateColumn("Tanggal", format="DD/MM/YYYY"),
                        "Tipe": st.column_config.TextColumn("Tipe"),
                        "Kategori": st.column_config.TextColumn("Kategori"),
                        "Jumlah": st.column_config.NumberColumn("Jumlah (Rp)", format="Rp %'.0f"),
                        "Catatan": st.column_config.TextColumn("Catatan")
                    },
                    use_container_width=True,
                    height=400,
                    hide_index=True
                )
                
                # Download button untuk data yang difilter
                csv = df_display.to_csv(index=False)
                st.download_button(
                    label="📥 Download Data (CSV)",
                    data=csv,
                    file_name=f"data_filtered_{start_date}_{end_date}.csv",
                    mime="text/csv",
                    use_container_width=True,
                    key="download_filtered"
                )
                
                # Tampilkan statistik cache jika diminta
                if st.session_state.get('show_stats', False):
                    with st.expander("📈 Cache Statistics"):
                        st.write(f"**Last Refresh:** {st.session_state.get('last_refresh', 'Never')}")
                        st.write(f"**Cache Key:** {st.session_state.get('cache_key', 'None')}")
                        st.write(f"**Data Rows:** {len(df)}")
                        st.write(f"**Memory Usage:** {df.memory_usage(deep=True).sum() / 1024 / 1024:.2f} MB")

else:
    st.error("❌ Aplikasi tidak dapat berjalan tanpa koneksi ke Google Sheets.")
    st.info("""
    ### Untuk menjalankan aplikasi:
    1. Buat file `secrets.toml` di folder `.streamlit/`
    2. Isi dengan credentials Google Sheets Anda:
    ```
    [gsheets_credentials]
    type = "service_account"
    project_id = "..."
    private_key_id = "..."
    private_key = "..."
    client_email = "..."
    client_id = "..."
    auth_uri = "https://accounts.google.com/o/oauth2/auth"
    token_uri = "https://oauth2.googleapis.com/token"
    auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
    client_x509_cert_url = "..."
    
    GSHEET_URL = "https://docs.google.com/spreadsheets/d/..."
    WORKSHEET_NAME = "Data"
    ```
    3. Restart aplikasi Streamlit
    """)

# --- Footer ---
st.divider()
st.caption("© 2024 FinanceKita PRO | Made with ❤️ using Streamlit")
