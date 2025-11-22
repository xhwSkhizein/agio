"""
Text chunking utilities for knowledge processing
"""

import re


class TextChunker:
    """
    Text chunker with semantic-aware splitting.
    
    Splits text into chunks while preserving sentence boundaries
    and maintaining overlap for context continuity.
    """
    
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
    
    def _split_sentences(self, text: str) -> list[str]:
        """Split text into sentences."""
        # Simple sentence splitter (can be improved with spaCy/nltk)
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if s.strip()]
    
    def chunk_text(self, text: str) -> list[str]:
        """
        Chunk text into overlapping segments.
        
        Args:
            text: Text to chunk
        
        Returns:
            List of text chunks
        """
        sentences = self._split_sentences(text)
        chunks = []
        current_chunk = []
        current_size = 0
        
        for sentence in sentences:
            sentence_size = len(sentence)
            
            # If adding this sentence exceeds chunk_size, save current chunk
            if current_size + sentence_size > self.chunk_size and current_chunk:
                chunks.append(" ".join(current_chunk))
                
                # Calculate overlap: keep last N characters worth of sentences
                overlap_size = 0
                overlap_sentences = []
                for s in reversed(current_chunk):
                    if overlap_size + len(s) > self.chunk_overlap:
                        break
                    overlap_sentences.insert(0, s)
                    overlap_size += len(s)
                
                current_chunk = overlap_sentences
                current_size = overlap_size
            
            current_chunk.append(sentence)
            current_size += sentence_size
        
        # Add final chunk
        if current_chunk:
            chunks.append(" ".join(current_chunk))
        
        return chunks
    
    def chunk_documents(self, documents: list[str]) -> list[tuple[str, int]]:
        """
        Chunk multiple documents.
        
        Args:
            documents: List of documents
        
        Returns:
            List of (chunk, doc_index) tuples
        """
        all_chunks = []
        for doc_idx, doc in enumerate(documents):
            chunks = self.chunk_text(doc)
            for chunk in chunks:
                all_chunks.append((chunk, doc_idx))
        
        return all_chunks
