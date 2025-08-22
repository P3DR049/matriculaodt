import streamlit as st
from PIL import Image
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import io, os, math, zipfile

st.set_page_config(page_title="Overlay PNG em PDFs", page_icon="🖼️", layout="wide")

st.title("🖼️ Overlay de PNG em PDFs (lotes)")
st.caption("Envie um PNG e vários PDFs. O sistema aplica a imagem sobre as páginas escolhidas.")

# Uploads
png_file = st.file_uploader("Imagem PNG", type=["png"])
pdf_files = st.file_uploader("Arquivos PDF", type=["pdf"], accept_multiple_files=True)

# Configurações
col1, col2, col3 = st.columns(3)
with col1:
    scale_pct = st.slider("Escala (% da largura da página)", 1, 100, 35)
with col2:
    opacity = st.slider("Opacidade (%)", 0, 100, 85)
with col3:
    pos = st.selectbox("Posição", ["centro", "topo-esquerda", "topo-direita", "base-esquerda", "base-direita"])

apply_to = st.radio("Aplicar em:", ["Todas as páginas", "Primeira página", "Última página"], horizontal=True)
batch_size = st.number_input("Tamanho do lote", 1, 300, 100)
suffix = st.text_input("Sufixo do arquivo de saída", "_overlay")

# Funções auxiliares
def build_watermark(png_bytes, w, h, scale_pct, opacity, pos):
    img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    if opacity < 100:
        r,g,b,a = img.split()
        a = a.point(lambda px: int(px * (opacity/100)))
        img = Image.merge("RGBA",(r,g,b,a))

    iw, ih = img.size
    final_w = (scale_pct/100.0) * w
    scale = final_w / iw
    final_h = ih * scale
    ir = ImageReader(img)

    if pos == "centro": x,y = (w-final_w)/2, (h-final_h)/2
    elif pos == "topo-esquerda": x,y = 0, h-final_h
    elif pos == "topo-direita": x,y = w-final_w, h-final_h
    elif pos == "base-esquerda": x,y = 0, 0
    else: x,y = w-final_w, 0

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(w,h))
    c.drawImage(ir, x,y, width=final_w, height=final_h, mask="auto")
    c.showPage(); c.save()
    return buf.getvalue()

def overlay(png_bytes, pdf_bytes, scale_pct, opacity, pos, scope):
    reader = PdfReader(io.BytesIO(pdf_bytes))
    writer = PdfWriter()
    for i,page in enumerate(reader.pages):
        w,h = float(page.mediabox.width), float(page.mediabox.height)
        apply_here = (scope=="Todas as páginas") or (scope=="Primeira página" and i==0) or (scope=="Última página" and i==len(reader.pages)-1)
        if apply_here:
            wm_bytes = build_watermark(png_bytes,w,h,scale_pct,opacity,pos)
            wm = PdfReader(io.BytesIO(wm_bytes)).pages[0]
            page.merge_page(wm)
        writer.add_page(page)
    out = io.BytesIO(); writer.write(out); return out.getvalue()

# Processamento
if st.button("▶️ Processar", type="primary") and png_file and pdf_files:
    png_bytes = png_file.read()
    results = []
    total = len(pdf_files)
    num_batches = math.ceil(total/batch_size)
    progress = st.progress(0.0, text=f"0/{total} PDFs...")

    for b in range(num_batches):
        start,end = b*batch_size, min((b+1)*batch_size,total)
        for idx,up in enumerate(pdf_files[start:end],start=1):
            pdf_bytes = up.read()
            out = overlay(png_bytes,pdf_bytes,scale_pct,opacity,pos,apply_to)
            out_name = os.path.splitext(up.name)[0]+suffix+".pdf"
            results.append((out_name,out))
        progress.progress(end/total, text=f"{end}/{total} PDFs...")

    st.success(f"✅ Concluído: {len(results)} PDFs processados")

    if len(results)==1:
        st.download_button("⬇️ Baixar PDF", data=results[0][1], file_name=results[0][0], mime="application/pdf")
    else:
        zbuf = io.BytesIO()
        with zipfile.ZipFile(zbuf,"w") as zf:
            for name,data in results: zf.writestr(name,data)
        st.download_button("⬇️ Baixar todos (ZIP)", data=zbuf.getvalue(), file_name="saida.zip", mime="application/zip")
