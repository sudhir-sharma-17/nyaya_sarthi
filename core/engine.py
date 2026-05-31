import numpy as np
import json
import os
import chromadb
from chromadb.config import Settings as ChromaSettings
from typing import List, Dict, Any
from sklearn.cluster import AgglomerativeClustering
from app.config import settings

try:
    from sentence_transformers import SentenceTransformer
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False

class MockEmbedding:
    def encode(self, texts):
        return np.zeros((len(texts), 384)) # Standard dimension for all-MiniLM-L6-v2

class EngineRoom:
    def __init__(self):
        if HAS_SENTENCE_TRANSFORMERS:
            try:
                self.embed_model = SentenceTransformer(settings.EMBEDDING_MODEL)
            except Exception as e:
                print(f"Embedding Model Load Failed: {e}. Using Mock.")
                self.embed_model = MockEmbedding()
        else:
            print("Sentence Transformers not found. Using Mock.")
            self.embed_model = MockEmbedding()
        
        # Initialize ChromaDB
        self.chroma_path = settings.CHROMA_DB_PATH
        os.makedirs(self.chroma_path, exist_ok=True)
        
        self.client = chromadb.PersistentClient(path=self.chroma_path)
        self.collection = self.client.get_or_create_collection(
            name="judicial_cases",
            metadata={"hnsw:space": "cosine"}
        )

    def get_embeddings(self, texts: List[str]) -> np.ndarray:
        if not texts: return np.array([])
        return self.embed_model.encode(texts)

    def cluster_cases(self, embeddings: np.ndarray, ids: List[int]) -> Dict[int, List[int]]:
        """Group cases using semantic similarity. Uses Agglomerative for better control on small sets."""
        if len(embeddings) < 2: return {0: ids}
        
        # Determine number of clusters dynamically or use a distance threshold
        # n_clusters=None + distance_threshold=0.5 for semantic similarity grouping
        model = AgglomerativeClustering(
            n_clusters=None, 
            distance_threshold=0.6, 
            metric='cosine', 
            linkage='average'
        )
        labels = model.fit_predict(embeddings)
        
        clusters = {}
        for idx, label in enumerate(labels):
            l = int(label)
            if l not in clusters: clusters[l] = []
            clusters[l].append(ids[idx])
        return clusters

    def add_to_vector_store(self, case_id: int, text: str, metadata: Dict[str, Any]):
        embedding = self.get_embeddings([text]).tolist()
        
        # Flatten metadata for ChromaDB (no nested dicts allowed)
        flat_metadata = {}
        for k, v in metadata.items():
            if isinstance(v, (dict, list)):
                flat_metadata[k] = json.dumps(v)
            else:
                flat_metadata[k] = v

        self.collection.add(
            ids=[str(case_id)],
            embeddings=embedding,
            metadatas=[flat_metadata],
            documents=[text]
        )

    def search_similar(self, query: str, limit: int = 5):
        embedding = self.get_embeddings([query]).tolist()
        try:
            count = self.collection.count()
            actual_limit = min(limit, max(count, 1))
        except Exception:
            actual_limit = limit
        results = self.collection.query(
            query_embeddings=embedding,
            n_results=actual_limit
        )
        return results

    def search_similar_filtered(self, query: str, limit: int = 5, allowed_ids: List[str] = None):
        """Search only among vectors with IDs in allowed_ids (session isolation)."""
        embedding = self.get_embeddings([query]).tolist()
        
        if not allowed_ids:
            return self.search_similar(query, limit)

        # ChromaDB supports `where_document` and `where` filters.
        # IDs must be filtered via `ids` parameter at get() level, or via where clause.
        # Most reliable approach: fetch all allowed IDs and rank by similarity manually.
        try:
            fetched = self.collection.get(
                ids=allowed_ids,
                include=["embeddings", "metadatas", "documents"]
            )
        except Exception:
            return self.search_similar(query, limit)

        if not fetched or not fetched.get("ids"):
            return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}

        q_emb = np.array(embedding[0])
        stored_embs = np.array(fetched["embeddings"])  # shape: (n, dim)

        # Compute cosine distances
        norms = np.linalg.norm(stored_embs, axis=1)
        norms[norms == 0] = 1
        q_norm = np.linalg.norm(q_emb) or 1
        similarities = np.dot(stored_embs, q_emb) / (norms * q_norm)
        distances = 1 - similarities  # cosine distance

        top_k = min(limit, len(fetched["ids"]))
        top_indices = np.argsort(distances)[:top_k]

        return {
            "ids": [[fetched["ids"][i] for i in top_indices]],
            "documents": [[fetched["documents"][i] for i in top_indices]],
            "metadatas": [[fetched["metadatas"][i] for i in top_indices]],
            "distances": [[float(distances[i]) for i in top_indices]]
        }

    def chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        words = text.split()
        chunks = []
        for i in range(0, len(words), chunk_size - overlap):
            chunk = " ".join(words[i:i + chunk_size])
            if chunk:
                chunks.append(chunk)
        return chunks

    def semantic_search_chunks(self, query: str, text: str, top_k: int = 3) -> List[str]:
        chunks = self.chunk_text(text)
        if not chunks:
            return []
            
        chunk_embeddings = self.get_embeddings(chunks)
        query_embedding = self.get_embeddings([query])[0]
        
        # Calculate cosine similarity manually using numpy
        norms_chunks = np.linalg.norm(chunk_embeddings, axis=1)
        norm_query = np.linalg.norm(query_embedding)
        
        # Prevent division by zero
        norms_chunks[norms_chunks == 0] = 1
        norm_query = norm_query if norm_query != 0 else 1
        
        similarities = np.dot(chunk_embeddings, query_embedding) / (norms_chunks * norm_query)
        
        # Get top k indices
        top_indices = np.argsort(similarities)[::-1][:top_k]
        return [chunks[i] for i in top_indices]

engine_room = EngineRoom()

