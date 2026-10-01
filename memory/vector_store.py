"""Vector Database Integration for ARA-1 Long-Term Memory.

Implements persistent ChromaDB storage conforming to Section A3.3 schema:
(id, content, embedding, ticker, source_type, date, confidence, verified, researcher_session).
Supports metadata filtering, similarity scoring, and offline fallback embeddings.
"""

from __future__ import annotations
import hashlib
import json
import logging
import math
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

import chromadb
from chromadb.config import Settings as ChromaSettings

from config.settings import get_settings
import threading

logger = logging.getLogger("ARA1.VectorStore")

_CHROMA_CLIENT_CACHE: Dict[str, Any] = {}
_CHROMA_LOCK = threading.Lock()


class ResearchDocument(BaseModel):
    """Schema for individual research documents stored in long-term memory."""
    id: str = Field(description="Unique identifier for the record (e.g. msft-10k-2024-item1a-001)")
    content: str = Field(description="Text content of the research finding or filing section")
    ticker: str = Field(description="Company ticker symbol (e.g. MSFT, AAPL, TSLA)")
    source_type: str = Field(description="Document type ('10-K', '10-Q', '8-K', 'earnings_call', 'news', 'analysis')")
    date: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="Filing date or publication date (ISO format)"
    )
    confidence: float = Field(default=0.90, ge=0.0, le=1.0, description="Confidence score (0.0 to 1.0)")
    verified: bool = Field(default=False, description="Whether verified by fact checker")
    researcher_session: str = Field(default="default_session", description="Session ID generating finding")
    source_url: Optional[str] = Field(default=None, description="Originating filing URL or accession number")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary supplementary tags")

    def to_chroma_metadata(self) -> Dict[str, Any]:
        """Flattens metadata to primitive types supported by ChromaDB."""
        meta: Dict[str, Any] = {
            "ticker": self.ticker.upper(),
            "source_type": self.source_type,
            "date": self.date,
            "confidence": float(self.confidence),
            "verified": int(self.verified),  # Chroma prefers int/str/float
            "researcher_session": self.researcher_session,
            "source_url": self.source_url or "",
        }
        for k, v in self.metadata.items():
            if isinstance(v, (str, int, float, bool)):
                meta[f"meta_{k}"] = v
        return meta


class SearchResult(BaseModel):
    """Envelope for vector search matches."""
    document: ResearchDocument
    similarity_score: float
    distance: float


class DocumentChunker:
    """Specialized financial document chunker supporting:
    1. Section-aware chunking for SEC filings (10-K, 10-Q, 8-K)
    2. Speaker-paired Q&A chunking for earnings call transcripts
    3. Context-prepended paragraph chunking for financial news and market analysis.
    """

    @staticmethod
    def _split_into_windows(
        text: str,
        chunk_size: int = 1200,
        overlap: int = 150
    ) -> List[str]:
        """Splits long text into overlapping chunks respecting sentence/paragraph boundaries."""
        text = text.strip()
        if not text:
            return []
        if len(text) <= chunk_size:
            return [text]

        chunks = []
        start = 0
        text_len = len(text)

        while start < text_len:
            end = min(start + chunk_size, text_len)
            if end < text_len:
                # Seek a natural break point (paragraph break, period, newline)
                break_point = -1
                search_zone = text[max(start, end - 150):end]
                for sep in ["\n\n", ".\n", ". ", "!\n", "! ", "?\n", "? ", "\n"]:
                    pos = search_zone.rfind(sep)
                    if pos != -1:
                        break_point = max(start, end - 150) + pos + len(sep)
                        break
                if break_point != -1 and break_point > start + 200:
                    end = break_point

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            if end >= text_len:
                break
            start = max(start + 1, end - overlap)

        return chunks

    @classmethod
    def chunk_sec_filing(
        cls,
        text: str,
        ticker: str,
        filing_type: str = "10-K",
        year: Optional[int] = None,
        filing_date: Optional[str] = None,
        source_url: Optional[str] = None,
        target_chunk_size: int = 950,
        chunk_overlap: int = 100,
    ) -> List[ResearchDocument]:
        """Segments SEC filings into section-aware semantic chunks.

        Identifies Item headers (e.g. Item 1: Business, Item 1A: Risk Factors,
        Item 7: MD&A, Item 8: Financial Statements) and creates chunks with section tags.
        """
        ticker_clean = ticker.strip().upper()
        clean_type = filing_type.replace(" ", "").replace("-", "")
        year_str = str(year) if year else datetime.now(timezone.utc).strftime("%Y")
        date_str = filing_date or datetime.now(timezone.utc).isoformat()

        # Regex detecting standard SEC Items: "ITEM 1.", "ITEM 1A.", "ITEM 7.", etc.
        item_pattern = re.compile(
            r"(?P<header>(?:PART\s+[I|V|X]+\s+)?ITEM\s+(?:1A|1B|7A|[1-9][0-4]?[A-Z]?)\.?\s*[-–—:]?\s*[^\n\r]{2,120})",
            re.IGNORECASE
        )

        matches = list(item_pattern.finditer(text))
        sections: List[Dict[str, Any]] = []

        if matches:
            for idx, match in enumerate(matches):
                header = match.group("header").strip()
                start_pos = match.start()
                end_pos = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
                section_body = text[match.end():end_pos].strip()

                # Clean section title
                clean_title = re.sub(r"\s+", " ", header)
                tag_match = re.search(r"ITEM\s+([0-9A-Z]+)", header, re.IGNORECASE)
                item_tag = tag_match.group(1).lower() if tag_match else f"sec{idx+1}"

                sections.append({
                    "title": clean_title,
                    "tag": f"item{item_tag}",
                    "content": section_body
                })
        else:
            # Fallback if no explicit item headers found: treat whole text as general disclosure
            sections.append({
                "title": f"{ticker_clean} {filing_type} Disclosure",
                "tag": "full",
                "content": text.strip()
            })

        documents: List[ResearchDocument] = []
        for sec in sections:
            sec_title = sec["title"]
            sec_tag = sec["tag"]
            sec_content = sec["content"]

            if not sec_content:
                continue

            windows = cls._split_into_windows(sec_content, chunk_size=target_chunk_size, overlap=chunk_overlap)
            total_windows = len(windows)

            for w_idx, win in enumerate(windows, start=1):
                doc_id = f"{ticker_clean.lower()}-{clean_type.lower()}-{year_str}-{sec_tag}-{w_idx:03d}"
                contextual_content = (
                    f"[{ticker_clean} {filing_type} ({year_str}) - {sec_title} (Part {w_idx}/{total_windows})]\n"
                    f"{win}"
                )
                doc = ResearchDocument(
                    id=doc_id,
                    content=contextual_content,
                    ticker=ticker_clean,
                    source_type=filing_type,
                    date=date_str,
                    confidence=0.98,  # SEC filings are Tier 1 primary sources
                    verified=True,
                    source_url=source_url,
                    metadata={
                        "section_title": sec_title,
                        "section_tag": sec_tag,
                        "chunk_index": w_idx,
                        "total_chunks": total_windows,
                        "source_tier": 1,
                    }
                )
                documents.append(doc)

        return documents

    @classmethod
    def chunk_earnings_transcript(
        cls,
        text: str,
        ticker: str,
        quarter: str,
        year: int,
        date: Optional[str] = None,
        source_url: Optional[str] = None,
        target_chunk_size: int = 1100,
        chunk_overlap: int = 100,
    ) -> List[ResearchDocument]:
        """Segments earnings call transcripts with Question & Answer pairing.

        Pairs Analyst Questions with Executive Answers into single chunks so that
        the question's context and the executive's quantitative answer stay unified.
        """
        ticker_clean = ticker.strip().upper()
        quarter_clean = quarter.strip().upper()
        year_str = str(year)
        date_str = date or datetime.now(timezone.utc).isoformat()

        documents: List[ResearchDocument] = []

        # Split text into Safe Harbor / Management Remarks vs Q&A
        qa_divider_pattern = re.compile(
            r"(?:question[s]?\s*(?:and|&)\s*answer[s]?\s*session|q\s*&\s*a\s*session|q&a)",
            re.IGNORECASE
        )
        parts = qa_divider_pattern.split(text, maxsplit=1)
        remarks_part = parts[0].strip() if parts else text
        qa_part = parts[1].strip() if len(parts) > 1 else ""

        # 1. Process Management Remarks (Prepared Remarks by CEO/CFO)
        if remarks_part:
            remarks_windows = cls._split_into_windows(
                remarks_part, chunk_size=target_chunk_size, overlap=chunk_overlap
            )
            for r_idx, win in enumerate(remarks_windows, start=1):
                doc_id = f"{ticker_clean.lower()}-transcript-{year_str}-{quarter_clean.lower()}-remarks-{r_idx:03d}"
                doc = ResearchDocument(
                    id=doc_id,
                    content=(
                        f"[{ticker_clean} {quarter_clean} {year_str} Earnings Call - Prepared Management Remarks "
                        f"(Part {r_idx}/{len(remarks_windows)})]\n{win}"
                    ),
                    ticker=ticker_clean,
                    source_type="earnings_call",
                    date=date_str,
                    confidence=0.95,
                    verified=True,
                    source_url=source_url,
                    metadata={
                        "quarter": quarter_clean,
                        "year": year,
                        "segment": "prepared_remarks",
                        "chunk_index": r_idx,
                        "source_tier": 2,
                    }
                )
                documents.append(doc)

        # 2. Process Q&A Session: Pair Analyst Questions with Executive Answers
        if qa_part:
            # Pattern matching speaker turn: e.g. "Operator:", "John Doe (Morgan Stanley):", "Satya Nadella:"
            speaker_pattern = re.compile(
                r"(?:\n|^)(?P<speaker>[A-Z][A-Za-z\s\.\,\(\)\-]+?)\s*:\s*",
                re.MULTILINE
            )
            turn_matches = list(speaker_pattern.finditer(qa_part))

            turns: List[Dict[str, str]] = []
            for idx, tm in enumerate(turn_matches):
                speaker = tm.group("speaker").strip()
                start_p = tm.end()
                end_p = turn_matches[idx + 1].start() if idx + 1 < len(turn_matches) else len(qa_part)
                turn_text = qa_part[start_p:end_p].strip()
                turns.append({"speaker": speaker, "text": turn_text})

            # Now pair Question turns with subsequent Executive Answer turns
            qa_pairs: List[Dict[str, Any]] = []
            curr_question: Optional[Dict[str, str]] = None
            curr_answers: List[Dict[str, str]] = []

            for turn in turns:
                spk_lower = turn["speaker"].lower()
                is_operator = "operator" in spk_lower
                # Analyst indicator: Contains firm name or question markers or is not executive
                is_analyst = (
                    "analyst" in spk_lower or
                    "(" in turn["speaker"] or
                    "question" in spk_lower or
                    (curr_question is None and not is_operator)
                )

                if is_operator:
                    continue

                if is_analyst and curr_answers:
                    # Save previous pair
                    qa_pairs.append({
                        "question": curr_question,
                        "answers": curr_answers
                    })
                    curr_question = turn
                    curr_answers = []
                elif is_analyst and curr_question is None:
                    curr_question = turn
                else:
                    # Executive answer
                    curr_answers.append(turn)

            if curr_question and curr_answers:
                qa_pairs.append({
                    "question": curr_question,
                    "answers": curr_answers
                })

            # If no formal speaker regex matches could be paired, chunk Q&A directly
            if not qa_pairs:
                qa_windows = cls._split_into_windows(
                    qa_part, chunk_size=target_chunk_size, overlap=chunk_overlap
                )
                for q_idx, win in enumerate(qa_windows, start=1):
                    doc_id = f"{ticker_clean.lower()}-transcript-{year_str}-{quarter_clean.lower()}-qa-{q_idx:03d}"
                    doc = ResearchDocument(
                        id=doc_id,
                        content=f"[{ticker_clean} {quarter_clean} {year_str} Earnings Call - Q&A Dialogue]\n{win}",
                        ticker=ticker_clean,
                        source_type="earnings_call",
                        date=date_str,
                        confidence=0.95,
                        verified=True,
                        source_url=source_url,
                        metadata={
                            "quarter": quarter_clean,
                            "year": year,
                            "segment": "qa_dialogue",
                            "chunk_index": q_idx,
                            "source_tier": 2,
                        }
                    )
                    documents.append(doc)
            else:
                for p_idx, pair in enumerate(qa_pairs, start=1):
                    q_spk = pair["question"]["speaker"] if pair["question"] else "Analyst"
                    q_body = pair["question"]["text"] if pair["question"] else ""
                    answers_body = "\n".join([f"{a['speaker']}: {a['text']}" for a in pair["answers"]])

                    full_dialogue = f"Question ({q_spk}):\n{q_body}\n\nAnswer:\n{answers_body}"
                    # If dialogue fits in one window
                    if len(full_dialogue) <= target_chunk_size:
                        doc_id = f"{ticker_clean.lower()}-transcript-{year_str}-{quarter_clean.lower()}-qa-{p_idx:03d}"
                        doc = ResearchDocument(
                            id=doc_id,
                            content=(
                                f"[{ticker_clean} {quarter_clean} {year_str} Earnings Call - Q&A Exchange #{p_idx}]\n"
                                f"{full_dialogue}"
                            ),
                            ticker=ticker_clean,
                            source_type="earnings_call",
                            date=date_str,
                            confidence=0.95,
                            verified=True,
                            source_url=source_url,
                            metadata={
                                "quarter": quarter_clean,
                                "year": year,
                                "segment": "qa_pair",
                                "analyst": q_spk,
                                "exchange_index": p_idx,
                                "source_tier": 2,
                            }
                        )
                        documents.append(doc)
                    else:
                        # Split while retaining question header
                        ans_windows = cls._split_into_windows(
                            answers_body,
                            chunk_size=max(600, target_chunk_size - len(q_body) - 100),
                            overlap=chunk_overlap
                        )
                        for sub_idx, aw in enumerate(ans_windows, start=1):
                            doc_id = f"{ticker_clean.lower()}-transcript-{year_str}-{quarter_clean.lower()}-qa-{p_idx:03d}-{sub_idx}"
                            doc = ResearchDocument(
                                id=doc_id,
                                content=(
                                    f"[{ticker_clean} {quarter_clean} {year_str} Earnings Call - Q&A #{p_idx} (Part {sub_idx}/{len(ans_windows)})]\n"
                                    f"Question ({q_spk}):\n{q_body}\n\nAnswer (Continued):\n{aw}"
                                ),
                                ticker=ticker_clean,
                                source_type="earnings_call",
                                date=date_str,
                                confidence=0.95,
                                verified=True,
                                source_url=source_url,
                                metadata={
                                    "quarter": quarter_clean,
                                    "year": year,
                                    "segment": "qa_pair_split",
                                    "analyst": q_spk,
                                    "exchange_index": p_idx,
                                    "part": sub_idx,
                                    "source_tier": 2,
                                }
                            )
                            documents.append(doc)

        return documents

    @classmethod
    def chunk_news_article(
        cls,
        title: str,
        text: str,
        ticker: str,
        publisher: str = "",
        date: Optional[str] = None,
        source_url: Optional[str] = None,
        target_chunk_size: int = 800,
        chunk_overlap: int = 80,
    ) -> List[ResearchDocument]:
        """Segments news and commentary prepended with headline, source publisher, and publication date."""
        ticker_clean = ticker.strip().upper()
        date_str = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        pub_clean = publisher.strip() or "Financial Press"
        clean_title = title.strip()

        hash_id = hashlib.md5(f"{clean_title}{ticker_clean}".encode("utf-8")).hexdigest()[:8]
        windows = cls._split_into_windows(text, chunk_size=target_chunk_size, overlap=chunk_overlap)
        total_w = len(windows)

        documents: List[ResearchDocument] = []
        for idx, win in enumerate(windows, start=1):
            doc_id = f"{ticker_clean.lower()}-news-{hash_id}-{idx:03d}"
            contextual_content = (
                f"[Headline: {clean_title} | Publisher: {pub_clean} | Date: {date_str} (Part {idx}/{total_w})]\n"
                f"{win}"
            )
            doc = ResearchDocument(
                id=doc_id,
                content=contextual_content,
                ticker=ticker_clean,
                source_type="news",
                date=date_str,
                confidence=0.85,  # News articles are Tier 3 secondary sources
                verified=False,
                source_url=source_url,
                metadata={
                    "headline": clean_title,
                    "publisher": pub_clean,
                    "chunk_index": idx,
                    "total_chunks": total_w,
                    "source_tier": 3,
                }
            )
            documents.append(doc)

        return documents



class EmbeddingGenerator:
    """Computes dense vector representations with OpenAI or deterministic offline fallback."""

    def __init__(self, dimension: int = 1536):
        self.settings = get_settings()
        self.dimension = dimension
        self.use_openai = self.settings.is_openai_configured() and not self.settings.MOCK_MODE

        if self.use_openai:
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=self.settings.OPENAI_API_KEY)
                logger.info(f"EmbeddingGenerator initialized with OpenAI ({self.settings.EMBEDDING_MODEL})")
            except Exception as e:
                logger.warning(f"Failed to initialize OpenAI embeddings: {e}. Falling back to offline generator.")
                self.use_openai = False
                self.client = None
        else:
            self.client = None

    def embed_text(self, text: str) -> List[float]:
        """Embeds a single text string."""
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embeds a batch of texts into normalized dense vectors."""
        if self.use_openai and self.client:
            try:
                res = self.client.embeddings.create(
                    model=self.settings.EMBEDDING_MODEL,
                    input=texts,
                )
                return [d.embedding for d in res.data]
            except Exception as e:
                logger.error(f"OpenAI embedding generation failed ({e}). Falling back to deterministic embedding.")

        # Deterministic offline pseudo-embedding generator
        embeddings = []
        for text in texts:
            vec = self._pseudo_embed(text)
            embeddings.append(vec)
        return embeddings

    def _pseudo_embed(self, text: str) -> List[float]:
        """Generates a stable, reproducible normalized vector of fixed dimension using feature hashing.

        When operating offline or in test environments, uses the hashing trick (term-frequency
        and morphological feature hashing) so that semantic similarity search correctly reflects
        shared terminology, quantitative numbers, and domain keywords without external APIs.
        """
        vec = [0.0] * self.dimension
        if not text:
            return vec

        # Tokenize and extract unigrams
        words = re.findall(r"[A-Za-z0-9\$\%]+", text.lower())
        if not words:
            return vec

        # Term frequency weighting with sublinear scaling
        word_counts: Dict[str, int] = {}
        for w in words:
            word_counts[w] = word_counts.get(w, 0) + 1

        for w, count in word_counts.items():
            # Term weight (1 + log(tf))
            weight = 1.0 + math.log(count)
            # Hash to dimension slot
            h_int = int(hashlib.md5(w.encode("utf-8")).hexdigest(), 16)
            slot = h_int % self.dimension
            sign = 1.0 if ((h_int >> 16) & 1) == 1 else -1.0
            vec[slot] += sign * weight

            # Also hash prefixes for morphological and word stem overlap
            if len(w) >= 4:
                prefix = w[:4]
                h_pre = int(hashlib.md5(prefix.encode("utf-8")).hexdigest(), 16)
                slot_pre = h_pre % self.dimension
                sign_pre = 1.0 if ((h_pre >> 16) & 1) == 1 else -1.0
                vec[slot_pre] += sign_pre * (weight * 0.5)

        # Normalize vector to unit length (L2 norm)
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [x / norm for x in vec]
        return vec


class FinancialVectorStore:
    """Manages persistent storage, metadata indexing, and retrieval of research chunks."""

    def __init__(
        self,
        persist_directory: Optional[str] = None,
        collection_name: Optional[str] = None,
    ):
        self.settings = get_settings()
        self.persist_dir = Path(persist_directory or self.settings.CHROMA_PERSIST_DIRECTORY)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.collection_name = collection_name or self.settings.CHROMA_COLLECTION_NAME

        self.embedder = EmbeddingGenerator(dimension=self.settings.EMBEDDING_DIMENSION)
        try:
            from agent.logger import get_agent_logger
            self.agent_logger = get_agent_logger()
        except Exception:
            self.agent_logger = None

        # Initialize ChromaDB persistent client (thread-safe singleton per path)
        path_str = str(self.persist_dir.resolve())
        with _CHROMA_LOCK:
            if path_str not in _CHROMA_CLIENT_CACHE:
                _CHROMA_CLIENT_CACHE[path_str] = chromadb.PersistentClient(
                    path=path_str,
                    settings=ChromaSettings(anonymized_telemetry=False)
                )
            self.chroma_client = _CHROMA_CLIENT_CACHE[path_str]
            self.collection = self.chroma_client.get_or_create_collection(
                name=self.collection_name,
                metadata={"description": "ARA-1 Long-Term Financial Research Memory"}
            )
        logger.info(f"Connected to ChromaDB collection '{self.collection_name}' at {self.persist_dir}")

    def add_document(self, doc: ResearchDocument) -> str:
        """Stores a single research document."""
        self.add_documents([doc])
        return doc.id

    def add_documents(self, docs: List[ResearchDocument]) -> List[str]:
        """Batches and persists multiple research documents with metadata."""
        if not docs:
            return []

        ids = [doc.id for doc in docs]
        contents = [doc.content for doc in docs]
        metadatas = [doc.to_chroma_metadata() for doc in docs]
        embeddings = self.embedder.embed_batch(contents)

        self.collection.upsert(
            ids=ids,
            documents=contents,
            metadatas=metadatas,
            embeddings=embeddings,
        )
        logger.info(f"Persisted {len(docs)} documents to vector store.")
        return ids

    def search(
        self,
        query: str,
        ticker: Optional[str] = None,
        source_type: Optional[str] = None,
        top_k: int = 4,
        min_confidence: float = 0.0,
    ) -> List[SearchResult]:
        """Performs semantic similarity search with optional metadata filtering."""
        if self.collection.count() == 0:
            return []

        query_embedding = self.embedder.embed_text(query)

        # Build metadata filter dictionary
        where_filter: Dict[str, Any] = {}
        conditions = []
        if ticker:
            conditions.append({"ticker": ticker.upper()})
        if source_type:
            conditions.append({"source_type": source_type})
        if min_confidence > 0.0:
            conditions.append({"confidence": {"$gte": min_confidence}})

        if len(conditions) == 1:
            where_filter = conditions[0]
        elif len(conditions) > 1:
            where_filter = {"$and": conditions}
        else:
            where_filter = None

        raw_results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where_filter,
            include=["documents", "metadatas", "distances"]
        )

        results: List[SearchResult] = []
        if not raw_results or not raw_results["ids"] or not raw_results["ids"][0]:
            return results

        ids = raw_results["ids"][0]
        documents = raw_results["documents"][0]
        metadatas = raw_results["metadatas"][0]
        distances = raw_results["distances"][0]

        for doc_id, text, meta, dist in zip(ids, documents, metadatas, distances):
            # Chroma distances with cosine metric: distance in [0, 2]
            # Normalized similarity score in [0.0, 1.0]
            similarity = max(0.0, min(1.0, 1.0 - (dist / 2.0)))

            doc = ResearchDocument(
                id=doc_id,
                content=text,
                ticker=meta.get("ticker", "UNKNOWN"),
                source_type=meta.get("source_type", "analysis"),
                date=meta.get("date", ""),
                confidence=float(meta.get("confidence", 0.9)),
                verified=bool(meta.get("verified", 0)),
                researcher_session=meta.get("researcher_session", ""),
                source_url=meta.get("source_url", ""),
            )
            results.append(
                SearchResult(
                    document=doc,
                    similarity_score=round(similarity, 4),
                    distance=round(dist, 4)
                )
            )

        return results

    def close(self) -> None:
        """Closes internal database connections to release file locks."""
        try:
            path_str = str(self.persist_dir.resolve())
            with _CHROMA_LOCK:
                if path_str in _CHROMA_CLIENT_CACHE:
                    del _CHROMA_CLIENT_CACHE[path_str]
            if hasattr(self.chroma_client, "_system"):
                self.chroma_client._system.stop()
        except Exception:
            pass

    def get_by_id(self, doc_id: str) -> Optional[ResearchDocument]:
        """Retrieves a document by its unique ID."""
        raw = self.collection.get(ids=[doc_id], include=["documents", "metadatas"])
        if not raw or not raw["ids"]:
            return None

        doc_id = raw["ids"][0]
        text = raw["documents"][0]
        meta = raw["metadatas"][0]

        return ResearchDocument(
            id=doc_id,
            content=text,
            ticker=meta.get("ticker", "UNKNOWN"),
            source_type=meta.get("source_type", "analysis"),
            date=meta.get("date", ""),
            confidence=float(meta.get("confidence", 0.9)),
            verified=bool(meta.get("verified", 0)),
            researcher_session=meta.get("researcher_session", ""),
            source_url=meta.get("source_url", ""),
        )

    def delete_by_id(self, doc_id: str) -> bool:
        """Deletes a document from the vector store."""
        self.collection.delete(ids=[doc_id])
        return True

    def delete_by_ticker(self, ticker: str) -> int:
        """Purges all stored chunks for a specific company ticker."""
        self.collection.delete(where={"ticker": ticker.upper()})
        return self.collection.count()

    def count(self, ticker: Optional[str] = None) -> int:
        """Returns the count of indexed chunks, optionally filtered by ticker."""
        if ticker:
            res = self.collection.get(where={"ticker": ticker.upper()}, include=[])
            return len(res["ids"])
        return self.collection.count()

    def clear(self) -> None:
        """Clears all records in the collection."""
        self.chroma_client.delete_collection(self.collection_name)
        self.collection = self.chroma_client.get_or_create_collection(self.collection_name)
        logger.info(f"Cleared vector store collection '{self.collection_name}'.")

    def ingest_filing(
        self,
        text: str,
        ticker: str,
        filing_type: str = "10-K",
        year: Optional[int] = None,
        filing_date: Optional[str] = None,
        source_url: Optional[str] = None,
        target_chunk_size: int = 950,
        chunk_overlap: int = 100,
    ) -> List[str]:
        """Ingests and persists an SEC filing using section-aware chunking."""
        chunks = DocumentChunker.chunk_sec_filing(
            text=text,
            ticker=ticker,
            filing_type=filing_type,
            year=year,
            filing_date=filing_date,
            source_url=source_url,
            target_chunk_size=target_chunk_size,
            chunk_overlap=chunk_overlap,
        )
        return self.add_documents(chunks)

    def ingest_transcript(
        self,
        text: str,
        ticker: str,
        quarter: str,
        year: int,
        date: Optional[str] = None,
        source_url: Optional[str] = None,
        target_chunk_size: int = 1100,
        chunk_overlap: int = 100,
    ) -> List[str]:
        """Ingests and persists an earnings call transcript with Q&A speaker pairing."""
        chunks = DocumentChunker.chunk_earnings_transcript(
            text=text,
            ticker=ticker,
            quarter=quarter,
            year=year,
            date=date,
            source_url=source_url,
            target_chunk_size=target_chunk_size,
            chunk_overlap=chunk_overlap,
        )
        return self.add_documents(chunks)

    def ingest_news(
        self,
        title: str,
        text: str,
        ticker: str,
        publisher: str = "",
        date: Optional[str] = None,
        source_url: Optional[str] = None,
        target_chunk_size: int = 800,
        chunk_overlap: int = 80,
    ) -> List[str]:
        """Ingests and persists a news/analysis article with context-prepended paragraphs."""
        chunks = DocumentChunker.chunk_news_article(
            title=title,
            text=text,
            ticker=ticker,
            publisher=publisher,
            date=date,
            source_url=source_url,
            target_chunk_size=target_chunk_size,
            chunk_overlap=chunk_overlap,
        )
        return self.add_documents(chunks)

