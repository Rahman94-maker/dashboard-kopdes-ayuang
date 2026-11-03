import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
import json
import os
import geopandas as gpd
from fpdf import FPDF
from google import genai
from google.genai import types
import time

# ==========================================
# 1. KONFIGURASI HALAMAN
# ==========================================
st.set_page_config(
    page_title="Dashboard Kopdes Ayuang",
    page_icon="🏪",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🏪 Dashboard Strategi Pemasaran Koperasi Merah Putih Desa Ayuang")
st.markdown("""
Dashboard ini memetakan **Batas Desa**, **Lokasi Kopdes**, serta **Layer Analisis Bisnis** (Kompetitor, Fasilitas Umum, dan Radius Layanan).
""")

# ==========================================
# FUNGSI AI GEMINI DENGAN AUTO RETRY
# ==========================================
@st.cache_data(ttl=1800, show_spinner=False)
def generate_gemini_text(api_key, prompt, timeout_ms=45000):
    client = genai.Client(api_key=api_key)

    daftar_model = [
        "gemini-3.8-flash",
        "gemini-3.5-flash-lite",
        "gemini-3.6-flash",
    ]

    daftar_error = []

    for model in daftar_model:
        try:
            response = client.interactions.create(
                model=model,
                input=prompt,
            )

            hasil = getattr(response, "output_text", None)

            if hasil and hasil.strip():
                return hasil

            daftar_error.append(
                f"{model}: respons kosong"
            )

        except Exception as e:
            daftar_error.append(f"{model}: {e}")

            pesan = str(e).lower()

            # Coba model berikutnya jika model tidak tersedia,
            # server sibuk, atau batas permintaan tercapai.
            error_sementara = any(kode in pesan for kode in [
                "503", "429", "500", "502", "504",
                "unavailable", "resource_exhausted",
                "not_found", "404", "deadline_exceeded"
            ])

            if error_sementara:
                time.sleep(2)
                continue

            # Error autentikasi atau konfigurasi tidak
            # akan diperbaiki dengan mengganti model.
            raise RuntimeError(
                f"Periksa API Key atau konfigurasi Gemini: {e}"
            ) from e

    raise RuntimeError(
        "Semua model gagal:\n" + "\n".join(daftar_error)
    )

# ==========================================
# 2. LOAD DATA
# ==========================================
@st.cache_data
def load_statistik():
    data = {}
    try:
        data['demografi'] = pd.read_csv('data_penduduk.csv')
        data['pendidikan'] = pd.read_csv('data_pendidikan.csv')
        data['pekerjaan'] = pd.read_csv('data_pekerjaan.csv')
    except FileNotFoundError:
        pass 
    return data

@st.cache_data
def load_titik_lokasi():
    data = {
        'Nama': ['Kopdes Merah Putih', 'Kantor Desa Ayuang', 'Puskesmas Pembantu Ayuang', 'Masjid Al Karim (Babanyu)', 'Masjid FAUZI Danggung', 'SD Negeri 2 Ayuang', 'SPBU Manggu', 'Hampang Agro', 'Bolu Lipat Mama Afipah', 'PP. Annisa', 'Toko Raisya', 'Pondok Pesantren Zainaturrahmah', 'TOKO VIKRI', 'SD Negeri 3 Ayuang', 'Kios hidayah', 'Warung Mama Budi', 'Warung dan Pom Mini Siti', 'Masjid Hasani', 'Pasar Tungging Ayuang', 'Kios Zulfa', 'SMP Negeri 8 Barabai', 'SD Negeri 1 Ayuang'],
        'Lat': [-2.5361272428445845, -2.5408297327976133, -2.543970187455041, -2.531344012801126, -2.5356956624616105, -2.5365209736827716, -2.538005460797599, -2.5489809652066637, -2.5380912072452517, -2.535733176700708, -2.5358557103321866, -2.5361343868668964, -2.531337391724152, -2.5326128767722045, -2.53428493932137, -2.542608129232007, -2.5451177472362843, -2.5462586842289188, -2.546615252250854, -2.5476817167021184, -2.5458274613702265, -2.5462582161285954], 
        'Lon': [115.3997564416875, 115.38756126649488, 115.38744324929357, 115.38991088159337, 115.39405221229744, 115.39724940540621, 115.41360015136493, 115.40784949532312, 115.39918059593421, 115.40347213029375, 115.39594138579531, 115.39516890961059, 115.39111201259273, 115.38960997554904, 115.38818304036255, 115.3874165389585, 115.38754307309893, 115.38798133783465, 115.38789063315522, 115.38756876808539, 115.38921027999919, 115.3856740146539],
        'Tipe': ['Kopdes', 'Fasum', 'Fasum', 'Ibadah', 'Ibadah', 'Pendidikan', 'Fasum', 'Fasum', 'Kompetitor', 'Kompetitor','Kompetitor','Ibadah','Kompetitor','Pendidikan','Kompetitor','Kompetitor', 'Kompetitor','Ibadah','Kopdes','Kompetitor','Pendidikan','Pendidikan'],
        'Deskripsi': ['Toko bahan makanan & kebutuhan pokok', 'Pelayanan administrasi warga', 'Pusat Kesehatan', 'Masjid (Area Babanyu)', 'Masjid (Area Danggung)', 'Sekolah Dasar Negeri', 'Stasiun Pengisian Bahan Bakar', 'Toko Pertanian / Agro', 'Kue & Jajanan Lipat', 'Toko Kelontong / Warung Pesantren', 'Toko Kelontong', 'Sekolah Pesantren', 'Toko Kelontong', 'Sekolah Dasar Negeri', 'Toko Kelontong', 'Toko Kelontong', 'Toko Kelontong dan Pom MINI', 'Masjid Hasani', 'Pasar Tungging Ayuang', 'Toko Kelontong', 'SMP Negeri 8 Barabai', 'Sekolah Dasar Negeri (SDN) 1 Ayuang']
    }
    return pd.DataFrame(data)

stats = load_statistik()
df_titik = load_titik_lokasi()

# ==========================================
# 3. SIDEBAR PENGATURAN & INFO
# ==========================================
st.sidebar.header("⚙️ Pengaturan Tampilan")
opsi_basemap = st.sidebar.radio("Pilih Jenis Peta:", ["Peta Biasa (Garis)", "Foto Satelit (Realita)"])
jenis_peta = "Esri World Imagery" if opsi_basemap == "Foto Satelit (Realita)" else "OpenStreetMap"
tampilkan_batas = st.sidebar.checkbox("Tampilkan Batas Desa (Garis Biru)", value=True)

st.sidebar.markdown("---")
st.sidebar.header("🤖 Fitur AI (Gemini)")
gunakan_ai = st.sidebar.toggle("Buat Ringkasan dengan AI", value=False)
api_key = ""
#if gunakan_ai:
#    api_key = st.sidebar.text_input("Masukkan Gemini API Key:", type="password")
if gunakan_ai:
    # Cek apakah API Key ada di Secrets Streamlit Cloud
    if "GEMINI_API_KEY" in st.secrets:
        api_key = st.secrets["GEMINI_API_KEY"]
    else:
        # Jika tidak ada, baru minta input manual (opsional)
        api_key = st.sidebar.text_input("Masukkan Gemini API Key:", type="password")

# ==========================================
# 1.5. EXECUTIVE SUMMARY (DENGAN AI)
# ==========================================
st.subheader("📌 Ringkasan Eksekutif")

teks_ringkasan_akhir = """
### 📌 Ringkasan Eksekutif (Executive Summary)
**Latar Belakang:** Secara geografis, Kopdes Merah Putih terletak di area persawahan, terpisah dari kluster permukiman warga di bagian selatan. Hal ini menjadi hambatan utama warga untuk berbelanja langsung ke Kopdes.

**Strategi "Jemput Bola" (Sesuai Aturan Kemenkop B-592):**
1. **Drop Point Warga:** Bekerja sama dengan warung lokal (titik oranye) di wilayah selatan sebagai titik titip pesanan.
2. **Layanan Antar Gratis:** Menggunakan armada operasional untuk mengantar pesanan warga setiap sore hari.
3. **Sosialisasi Simpanan Pokok:** Mengedukasi warga bahwa dengan menjadi anggota, mereka mendapatkan kemudahan akses sembako murah yang diantar langsung ke rumah.

**Target Output:** Meningkatkan partisipasi warga (khususnya di wilayah selatan) menjadi anggota Kopdes dan optimalisasi pemenuhan simpanan pokok.
"""

if gunakan_ai and api_key:
    # 1. Cek apakah di session_state sudah ada ringkasan dari AI
    if "ringkasan_ai" in st.session_state:
        # Jika ada, tampilkan menggunakan st.info atau st.markdown
        st.info(st.session_state["ringkasan_ai"])
        
        # (Opsional) Beri tombol untuk menghapus ringkasan dan kembali ke default
        if st.button("Hapus Ringkasan AI & Kembali ke Default"):
            del st.session_state["ringkasan_ai"]
            st.rerun()

    # 2. Tombol untuk memicu pembuatan ringkasan
    if st.button("🤖 Buat Ringkasan dengan Gemini"):
        try:
            jml_kompetitor = len(df_titik[df_titik['Tipe'] == 'Kompetitor'])
            prompt = f"""
            Anda adalah konsultan koperasi desa.
            Buat Ringkasan Eksekutif maksimal 150 kata.
            Data:
            - Desa: Ayuang
            - Luas: 2.70 km2
            - Penduduk: 1.866 jiwa
            - Kompetitor: {jml_kompetitor} titik
            - Kondisi: Kopdes terpisah dari permukiman oleh area persawahan.
            Strategi:
            1. Drop Point di warung lokal.
            2. Layanan antar gratis.
            3. Sosialisasi simpanan pokok.
            Gunakan bahasa formal untuk laporan kepada Dinas Koperasi.
            """

            with st.spinner("Gemini sedang menganalisis..."):
                # Simpan hasil ke session_state
                st.session_state["ringkasan_ai"] = generate_gemini_text(api_key, prompt)
                
            # Refresh halaman agar hasil langsung muncul di atas
            st.rerun() 

        except Exception as e:
            st.warning("⚠️ Layanan AI Gemini sedang mengalami gangguan.")
            st.info("Dashboard tetap berjalan menggunakan Ringkasan Eksekutif standar.")
            with st.expander("Detail teknis error"):
                st.code(str(e))
else:
    # Jika toggle AI dimatikan, tampilkan teks default
    st.info(teks_ringkasan_akhir)

st.markdown("---")

# ==========================================
# 1.7. CHAT INTERAKTIF DENGAN AI
# ==========================================
if gunakan_ai and api_key:
    st.markdown("### 💬 Tanya AI Seputar Data Desa")
    
    if "messages" not in st.session_state:
        st.session_state.messages = []
        
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            
    if prompt_chat := st.chat_input("Contoh: Berapa jumlah warung kompetitor?"):
        st.session_state.messages.append({"role": "user", "content": prompt_chat})
        with st.chat_message("user"):
            st.markdown(prompt_chat)
            
        with st.chat_message("assistant"):
            with st.spinner("AI sedang berpikir..."):
                try:
                    konteks_data = f"""
                    Anda adalah asisten analis data untuk Kopdes Desa Ayuang. 
                    Data yang tersedia:
                    - Luas Desa: 2.70 km2
                    - Penduduk: 1.866 Jiwa
                    - Kompetitor: {len(df_titik[df_titik['Tipe'] == 'Kompetitor'])} warung/toko.
                    - Fasilitas Pendidikan: {len(df_titik[df_titik['Tipe'] == 'Pendidikan'])} sekolah.
                    - Fasilitas Ibadah: {len(df_titik[df_titik['Tipe'] == 'Ibadah'])} masjid.
                    
                    Jawablah pertanyaan pengguna dengan singkat, formal, dan berdasarkan data di atas.
                    """
                    
                    # Menggunakan client yang sama dan model yang valid
                    response_chat = generate_gemini_text(
                        api_key,
                        konteks_data + "\n\nPertanyaan Pengguna: " + prompt_chat,
                        timeout_ms=30000
                    )

                    st.markdown(response_chat)

                    st.session_state.messages.append({
                      "role": "assistant",
                      "content": response_chat
                    })
                    
                except Exception as e:
                    st.error(f"Koneksi AI terputus. Coba tanyakan lagi nanti. (Error: {e})")

st.markdown("---")

# ==========================================
# 4. MEMBUAT PETA FOLIUM & LAYER GROUPS
# ==========================================
m = folium.Map(location=[-2.5356, 115.3997], zoom_start=15, tiles=jenis_peta)

# A. Batas Desa
if tampilkan_batas and os.path.exists('batas_ayuang.geojson'):
    with open('batas_ayuang.geojson', 'r') as f:
        batas_desa = json.load(f)
    folium.GeoJson(batas_desa, name='Batas Desa', style_function=lambda x: {'fillColor': '#3388ff', 'color': '#3388ff', 'weight': 3, 'fillOpacity': 0.1}).add_to(m)

# B. Radius
fg_radius = folium.FeatureGroup(name="🎯 Radius 500m")
folium.Circle(location=[-2.535618, 115.399779], radius=500, color='red', fill=True, fill_color='red', fill_opacity=0.1).add_to(fg_radius)
fg_radius.add_to(m)

# C. Titik Lokasi
fg_titik = folium.FeatureGroup(name="📍 Titik Lokasi")
for _, row in df_titik.iterrows():
    if row['Tipe'] == 'Kopdes': color, icon_name = 'red', 'shopping-cart'
    elif row['Tipe'] == 'Kompetitor': color, icon_name = 'gray', 'store' 
    elif row['Tipe'] == 'Ibadah': color, icon_name = 'purple', 'mosque'
    elif row['Tipe'] == 'Pendidikan': color, icon_name = 'blue', 'graduation-cap'
    else: color, icon_name = 'orange', 'info-sign'
    folium.Marker([row['Lat'], row['Lon']], popup=row['Nama'], tooltip=row['Nama'], icon=folium.Icon(color=color, icon=icon_name, prefix='fa')).add_to(fg_titik)
fg_titik.add_to(m)

# D. KK
fg_kk = folium.FeatureGroup(name="🏠 Sebaran KK")
for kk in [{"rt": "RT 01", "lat": -2.5470048044081603, "lon": 115.38605043441721, "jumlah": 45, "status": "Belum Anggota"}, {"rt": "RT 02", "lat": -2.543714199988048, "lon": 115.38752158024147, "jumlah": 60, "status": "Belum Anggota"},{"rt": "RT 03", "lat": -2.5338558346823, "lon": 115.38840995325627, "jumlah": 60, "status": "Belum Anggota"},{"rt": "RT 04", "lat": -2.540825054261586, "lon": 115.38758945140503, "jumlah": 60, "status": "Belum Anggota"},{"rt": "RT 05", "lat": -2.531939534327363, "lon": 115.39147009558388, "jumlah": 60, "status": "Belum Anggota"},{"rt": "RT 06", "lat": -2.536459251689519, "lon": 115.39903435642793, "jumlah": 60, "status": "Anggota"},{"rt": "RT 07", "lat": -2.5361229642131318, "lon": 115.4016682856589, "jumlah": 60, "status": "Anggota"}]:
    folium.CircleMarker(location=[kk['lat'], kk['lon']], radius=kk['jumlah'] / 5, color='red' if kk['status']=='Belum Anggota' else 'green', fill=True).add_to(fg_kk)
fg_kk.add_to(m)

# E. Jalan
fg_jalan = folium.FeatureGroup(name="🛣️ Jalan")
folium.PolyLine(locations=[[-2.5350, 115.3980], [-2.5330, 115.4010]], color="red", weight=4, dash_array='10, 10').add_to(fg_jalan)
fg_jalan.add_to(m)

# ==========================================
# 5. TAMPILKAN PETA
# ==========================================
st.subheader("🗺️ Peta Analisis Strategis")
folium.LayerControl(collapsed=False).add_to(m)
st_folium(m, width=1200, height=650, returned_objects=[])

# ==========================================
# 6. INSIGHT & GRAFIK
# ==========================================
st.markdown("---")
st.subheader("📊 Data Statistik Kependudukan")
if stats:
    if 'pendidikan' in stats:
        st.bar_chart(data=stats['pendidikan'], x='Tingkat Pendidikan', y='Jumlah', color='#2ca02c', horizontal=True)
    if 'pekerjaan' in stats:
        st.bar_chart(data=stats['pekerjaan'][stats['pekerjaan']['Jumlah'] > 0], x='Kategori', y='Jumlah', color='#d62728', horizontal=True)

# ==========================================
# 8. TOMBOL DOWNLOAD PDF & KIRIM WA
# ==========================================
st.markdown("---")
st.subheader("📥 Unduh & Bagikan Laporan")

def buat_pdf_laporan(teks_pdf):
    pdf = FPDF()
    pdf.add_page()
    
    # 1. JUDUL
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, txt="LAPORAN LENGKAP STRATEGI KOPDES", ln=True, align='C')
    pdf.cell(200, 10, txt="Kopdes Merah Putih Desa Ayuang", ln=True, align='C')
    pdf.ln(5)
    
    # 2. GAMBAR PETA
    if os.path.exists("peta_kopdes.png"):
        y_sebelum_gambar = pdf.get_y()
        pdf.image("peta_kopdes.png", x=10, y=y_sebelum_gambar, w=190) 
        pdf.set_y(y_sebelum_gambar + 120) 
    else:
        pdf.set_font("Arial", 'I', 10)
        pdf.cell(200, 10, txt="[Gambar peta tidak ditemukan]", ln=True, align='C')
        pdf.ln(10)
    
    # 3. RINGKASAN EKSEKUTIF
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, txt="A. Ringkasan Eksekutif", ln=True)
    pdf.set_font("Arial", size=11)
    
    teks_bersih = teks_pdf.replace("**", "").replace("###", "").replace("* ", "- ").replace("📌", "")
    pdf.multi_cell(0, 6, txt=teks_bersih)
    pdf.ln(10) 
    
    # 4. DATA WILAYAH & FASILITAS
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, txt="B. Data Wilayah & Fasilitas", ln=True)
    pdf.set_font("Arial", size=11)
    
    jml_kompetitor = len(df_titik[df_titik['Tipe'] == 'Kompetitor'])
    jml_pendidikan = len(df_titik[df_titik['Tipe'] == 'Pendidikan'])
    jml_ibadah = len(df_titik[df_titik['Tipe'] == 'Ibadah'])
    
    teks_wilayah = (
        f"- Luas Desa: 2.70 km2\n"
        f"- Total Penduduk: 1.866 Jiwa\n"
        f"- Titik Kompetitor Terdeteksi: {jml_kompetitor} Warung/Toko\n"
        f"- Fasilitas Pendidikan: {jml_pendidikan} Sekolah\n"
        f"- Fasilitas Ibadah: {jml_ibadah} Masjid\n"
    )
    pdf.multi_cell(0, 6, txt=teks_wilayah)
    pdf.ln(5)

    # 5. DATA STATISTIK
    if 'pendidikan' in stats and 'pekerjaan' in stats:
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, txt="C. Data Statistik Kependudukan", ln=True)
        pdf.set_font("Arial", size=11)
        
        top_pendidikan = stats['pendidikan'].nlargest(3, 'Jumlah')
        teks_pendidikan = "Tingkat Pendidikan Terbanyak:\n"
        for _, row in top_pendidikan.iterrows():
            teks_pendidikan += f"- {row['Tingkat Pendidikan']}: {row['Jumlah']} Jiwa\n"
            
        top_pekerjaan = stats['pekerjaan'].nlargest(3, 'Jumlah')
        teks_pekerjaan = "Mata Pencaharian Terbanyak:\n"
        for _, row in top_pekerjaan.iterrows():
            teks_pekerjaan += f"- {row['Kategori']}: {row['Jumlah']} Jiwa\n"
            
        pdf.multi_cell(0, 6, txt=teks_pendidikan + "\n" + teks_pekerjaan)
    
    # 6. FOOTER
    pdf.ln(10)
    pdf.set_font("Arial", 'I', 9)
    pdf.cell(0, 10, txt="Dicetak secara otomatis dari Dashboard Kopdes Ayuang.", align='C')
    
    return bytes(pdf.output())

# Tentukan teks yang akan dimasukkan ke PDF
col_btn1, col_btn2 = st.columns([1, 2])
with col_btn1:
    st.download_button(
        label="📥 Download Laporan PDF",
        data=buat_pdf_laporan(teks_ringkasan_akhir),
        file_name="Laporan_Kopdes_Ayuang.pdf",
        mime="application/pdf",
        type="primary"
    )
with col_btn2:
    st.markdown(f'<a href="https://wa.me/6287882522811?text=Halo+Bapak+Kades,+Laporan+PDF+siap+diunduh." target="_blank"><button style="background-color: #25D366; color: white; padding: 10px 24px; border: none; border-radius: 5px; cursor: pointer; width: 100%; font-weight: bold;">📲 Kirim Ringkasan ke WA Kades</button></a>', unsafe_allow_html=True)
