# app/langgraph_nodes/doc_rag_node.py
from app.chroma.chroma_client import ChromaClient
import re

DEFAULT_RELEVANCE_THRESHOLD = float(
    # default threshold (distance-based). Lower = more similar for many chroma setups.
    # Tune this if your chroma returns similarity scores (0..1) instead of distances.
    0.45
)

def _clean_text_for_ui(text: str, max_sentences: int = 3) -> str:
    if not text:
        return ""
    text = re.sub(r'\s+', ' ', text).strip()
    sentences = re.split(r'(?<=[\.\!\?])\s+', text)
    dedup = []
    prev = None
    for s in sentences:
        s = s.strip()
        if not s: continue
        if s == prev: continue
        dedup.append(s)
        prev = s
    short = " ".join(dedup[:max_sentences])
    if len(short) > 600:
        short = short[:600].rsplit(' ', 1)[0] + "…"
    return short

class DocRAGNode:
    def __init__(self):
        self.chroma = ChromaClient()

    def _normalize_hits(self, hits):
        """
        Convert chroma result shapes (dict/list) into list of dicts:
        [{'text': str, 'metadata': dict, 'distance': float | None, 'score': float | None}, ...]
        """
        out = []
        if hits is None:
            return out

        # Newer chroma often returns dict with keys: 'documents', 'metadatas', 'distances'
        if isinstance(hits, dict):
            docs = hits.get('documents') or hits.get('documents', [])
            metadatas = hits.get('metadatas') or hits.get('metadatas', [])
            distances = hits.get('distances') or hits.get('distances', [])
            # often these are lists-of-lists (for batch queries). handle both
            docs_list = docs[0] if docs and isinstance(docs[0], list) else docs
            metas_list = metadatas[0] if metadatas and isinstance(metadatas[0], list) else metadatas
            dists_list = distances[0] if distances and isinstance(distances[0], list) else distances

            for i, doc in enumerate(docs_list):
                md = (metas_list[i] if metas_list and i < len(metas_list) else {}) if metas_list else {}
                dist = (dists_list[i] if dists_list and i < len(dists_list) else None) if distances else None
                out.append({'text': doc, 'metadata': md, 'distance': dist, 'score': None})
            return out

        # If it's a list of objects (older versions), try to extract fields
        if isinstance(hits, list):
            for item in hits:
                if isinstance(item, dict):
                    text = item.get('document') or item.get('text') or item.get('documents') or item.get('content') or item.get('payload') or item.get('raw') or str(item)
                    meta = item.get('metadata') or item.get('metadatas') or item.get('meta') or {}
                    dist = item.get('distance') or item.get('score') or None
                    out.append({'text': text, 'metadata': meta, 'distance': dist, 'score': item.get('score', None)})
                else:
                    out.append({'text': str(item), 'metadata': {}, 'distance': None, 'score': None})
            return out

        # fallback - wrap raw
        out.append({'text': str(hits), 'metadata': {}, 'distance': None, 'score': None})
        return out

    def _is_relevant(self, normalized_hits, threshold = DEFAULT_RELEVANCE_THRESHOLD):
        """
        Heuristic to decide if any hit is relevant:
         - if distances present and numeric: prefer distance < threshold (lower is better for many setups)
         - if scores present and numeric: prefer score > (1 - threshold)
         - if neither present, rely on presence of text and non-empty metadata
        """
        if not normalized_hits:
            return False

        for h in normalized_hits:
            d = h.get('distance')
            s = h.get('score')
            text = (h.get('text') or "").strip()
            if d is not None:
                try:
                    # assume lower is better (distance); tune threshold per your chroma
                    if float(d) < threshold:
                        return True
                except Exception:
                    pass
            if s is not None:
                try:
                    # assume higher is better for 'score' (0..1)
                    if float(s) > (1.0 - threshold):
                        return True
                except Exception:
                    pass
            # fallback: if any non-empty text found, consider it weakly relevant
            if text and len(text) > 30:
                return True
        return False

    def run(self, query: str, context: dict) -> dict:
        # Query chroma
        try:
            hits = self.chroma.semantic_search(collection_name='brochures', query=query, n_results=3)
        except Exception as e:
            return {'answer': f'Chroma query failed: {e}', 'provenance': None}

        normalized = self._normalize_hits(hits)

        # Decide relevance
        relevant = self._is_relevant(normalized)

        if not relevant:
            # Not confident — politely decline
            return {'answer': "Sorry — I can't find an answer to that in your uploaded documents.", 'provenance': None}

        # Build a short synthesized answer from top hits: take text, clean and concat a couple of sentences
        pieces = []
        for h in normalized[:3]:
            t = (h.get('text') or "")
            if not t:
                continue
            clean = _clean_text_for_ui(t, max_sentences=2)
            if clean:
                pieces.append(clean)

        # dedupe and produce small paragraph
        seen = set()
        final_sentences = []
        for p in pieces:
            if p in seen:
                continue
            final_sentences.append(p)
            seen.add(p)
        answer_paragraph = " ".join(final_sentences)[:1200].strip()
        if not answer_paragraph:
            return {'answer': "Sorry — I couldn't synthesize an answer from the documents.", 'provenance': None}

        # Short, user-friendly answer (no provenance)
        return {'answer': answer_paragraph, 'provenance': normalized}
