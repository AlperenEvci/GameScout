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
    query_vector = model.encode([query])
    D, I = index.search(np.array(query_vector).astype("float32"), top_k)

    st.subheader("🎯 Eşleşen Sonuçlar:")
    for idx in I[0]:
        doc = metadata[idx]
        st.markdown(f"### 🧾 {doc.get('title', 'No Title')}")
    if 'url' in doc:
        st.markdown(f"[🔗 Kaynak Link]({doc['url']})")
    st.text_area("📚 İçerik", doc.get("content", "No Content")[:600] + "…", height=200, key=f"text_{idx}")
    st.markdown("---")

