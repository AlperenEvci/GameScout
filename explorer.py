import streamlit as st
import faiss
import pickle
import json
import numpy as np
from sentence_transformers import SentenceTransformer


# -------------------
# Dosyaları Yükle
# -------------------
FAISS_PATH = "vector_db/bg3_knowledge.faiss"
META_PATH_PKL = "vector_db/bg3_knowledge_metadata.pkl"
META_PATH_JSON = "vector_db/metadata.json"

# Metadata dosyası olarak pkl ya da json kullan
try:
    with open(META_PATH_PKL, "rb") as f:
        metadata = pickle.load(f)
except:
    with open(META_PATH_JSON, "r", encoding="utf-8") as f:
        metadata = json.load(f)

# FAISS index yükle
index = faiss.read_index(FAISS_PATH)

# Model yükle
model = SentenceTransformer("all-MiniLM-L6-v2")

# -------------------
# Streamlit UI
# -------------------
st.title("🔍 GameScout VectorDB Explorer")

query = st.text_input("🧠 Sorgu girin", "")
top_k = st.slider("🔢 Kaç sonuç dönsün?", 1, 10, 3)

if query:
    # Sorguyu vektöre dönüştür
    query_vector = model.encode([query])
    
    # Vektör veritabanında arama yap
    D, I = index.search(np.array(query_vector).astype("float32"), top_k)
    
    # Sonuçları göster
    st.subheader("🎯 Eşleşen Sonuçlar:")
    
    # Bulunan her sonuç için
    for i, idx in enumerate(I[0]):
        if idx != -1:  # Geçerli bir indeks ise
            doc = metadata[idx]
            
            # Başlık
            st.markdown(f"### 🧾 {doc.get('title', 'Başlık Yok')}")
            
            # URL varsa göster
            if 'url' in doc:
                st.markdown(f"[🔗 Kaynak Link]({doc['url']})")
            
            # Benzerlik skoru
            similarity = 1.0 / (1.0 + D[0][i])  # Mesafeyi benzerlik skoruna çevir
            st.progress(float(similarity))
            st.text(f"Benzerlik: {similarity:.2f}")
            
            # İçerik
            content = doc.get("content", "İçerik Yok")
            st.text_area("📚 İçerik", content[:600] + ("..." if len(content) > 600 else ""), 
                         height=200, key=f"text_{i}")
            
            # Etiketler
            if 'tags' in doc and doc['tags']:
                st.markdown(f"**Etiketler:** {', '.join(doc['tags'])}")
                
            st.markdown("---")
    
    # Sonuç bulunamazsa bilgi ver
    if len(I[0]) == 0 or all(idx == -1 for idx in I[0]):
        st.info("Bu sorgu için eşleşen sonuç bulunamadı.")
else:
    st.info("Bilgi almak için yukarıya bir sorgu girin.")

