"""
AI Chat Topic Segmenter
Layer 1 of the Chat-to-Vault Pipeline

Takes unified markdown conversations (from AI-Chat-Export-Codex)
and splits them into individual topic pages, one per folder.

Uses SBERT embeddings to detect topic boundaries.
Outputs: one folder per topic, each containing a single markdown
page with YAML frontmatter and the raw conversation chunks
relevant to that topic.

Dependencies: sentence-transformers, sklearn, numpy
Install: pip install sentence-transformers scikit-learn numpy --break-system-packages

Usage:
  python chat_topic_segmenter.py <input_folder> <output_folder>
  python chat_topic_segmenter.py D:\CHAT_EXPORTS\parsed D:\CHAT_EXPORTS\segmented
"""

import os
import sys
import re
import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple

import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity


# --- Config ---
MODEL_NAME = "all-MiniLM-L6-v2"  # fast, good enough for topic boundaries
SIMILARITY_THRESHOLD = 0.35       # below this = new topic (tune after testing)
MIN_CHUNK_LINES = 3               # minimum lines to form a chunk
MAX_TOPIC_TITLE_LEN = 60          # truncate auto-generated titles
MERGE_THRESHOLD = 0.75            # above this = merge two topics


class TopicSegmenter:
    def __init__(self, model_name: str = MODEL_NAME):
        print(f"Loading SBERT model: {model_name}")
        self.model = SentenceTransformer(model_name)

    def parse_conversation(self, text: str) -> List[Dict]:
        """Parse a markdown conversation into speaker-tagged chunks."""
        chunks = []
        current_speaker = None
        current_lines = []

        for line in text.split('\n'):
            # Detect speaker changes (H: / A: / Human: / Assistant: / **David:** etc.)
            speaker_match = re.match(
                r'^(?:\*\*)?(?:H|Human|David|User|A|Assistant|Claude|AI)(?:\*\*)?[:\s]',
                line, re.IGNORECASE
            )

            if speaker_match:
                # Save previous chunk
                if current_lines and current_speaker:
                    chunk_text = '\n'.join(current_lines).strip()
                    if len(chunk_text) > 20:  # skip tiny fragments
                        chunks.append({
                            'speaker': current_speaker,
                            'text': chunk_text,
                            'line_count': len(current_lines)
                        })

                # Start new chunk
                if re.match(r'^(?:\*\*)?(?:H|Human|David|User)', line, re.IGNORECASE):
                    current_speaker = 'human'
                else:
                    current_speaker = 'assistant'
                current_lines = [line]
            else:
                current_lines.append(line)

        # Don't forget last chunk
        if current_lines and current_speaker:
            chunk_text = '\n'.join(current_lines).strip()
            if len(chunk_text) > 20:
                chunks.append({
                    'speaker': current_speaker,
                    'text': chunk_text,
                    'line_count': len(current_lines)
                })

        return chunks

    def detect_topics(self, chunks: List[Dict]) -> List[List[Dict]]:
        """Group chunks into topics based on semantic similarity."""
        if not chunks:
            return []

        # Get embeddings for each chunk
        texts = [c['text'][:512] for c in chunks]  # truncate for speed
        embeddings = self.model.encode(texts, show_progress_bar=False)

        # Detect topic boundaries by comparing adjacent chunks
        topics = []
        current_topic = [chunks[0]]

        for i in range(1, len(chunks)):
            sim = cosine_similarity(
                embeddings[i-1].reshape(1, -1),
                embeddings[i].reshape(1, -1)
            )[0][0]

            if sim < SIMILARITY_THRESHOLD and len(current_topic) >= MIN_CHUNK_LINES:
                # Topic boundary detected
                topics.append(current_topic)
                current_topic = [chunks[i]]
            else:
                current_topic.append(chunks[i])

        if current_topic:
            topics.append(current_topic)

        # Merge very similar topics (same topic revisited later)
        topics = self._merge_similar_topics(topics, embeddings, chunks)

        return topics

    def _merge_similar_topics(self, topics, embeddings, chunks):
        """Merge topics that are semantically similar (revisited topics)."""
        if len(topics) <= 1:
            return topics

        # Get topic-level embeddings (average of chunk embeddings)
        topic_embeddings = []
        chunk_idx = 0
        for topic in topics:
            topic_embs = []
            for _ in topic:
                if chunk_idx < len(embeddings):
                    topic_embs.append(embeddings[chunk_idx])
                chunk_idx += 1
            if topic_embs:
                topic_embeddings.append(np.mean(topic_embs, axis=0))

        # Find pairs to merge
        merged = list(range(len(topics)))  # track merge targets
        for i in range(len(topic_embeddings)):
            for j in range(i + 1, len(topic_embeddings)):
                if merged[j] != j:
                    continue  # already merged
                sim = cosine_similarity(
                    topic_embeddings[i].reshape(1, -1),
                    topic_embeddings[j].reshape(1, -1)
                )[0][0]
                if sim > MERGE_THRESHOLD:
                    merged[j] = i  # merge j into i

        # Build merged topic list
        result = {}
        for idx, target in enumerate(merged):
            if target not in result:
                result[target] = []
            result[target].extend(topics[idx])

        return list(result.values())

    def generate_topic_title(self, topic_chunks: List[Dict]) -> str:
        """Generate a title from the first human message in the topic."""
        for chunk in topic_chunks:
            if chunk['speaker'] == 'human':
                # Take first meaningful line
                text = chunk['text']
                # Strip speaker prefix
                text = re.sub(r'^(?:\*\*)?(?:H|Human|David|User)(?:\*\*)?[:\s]*', '', text)
                # Take first sentence or first N chars
                first_line = text.split('\n')[0].strip()
                if len(first_line) > MAX_TOPIC_TITLE_LEN:
                    first_line = first_line[:MAX_TOPIC_TITLE_LEN].rsplit(' ', 1)[0]
                # Clean for folder name
                clean = re.sub(r'[<>:"/\\|?*]', '', first_line)
                clean = clean.strip('. ')
                if clean:
                    return clean

        return f"topic_{hashlib.md5(topic_chunks[0]['text'].encode()).hexdigest()[:8]}"

    def write_topic(self, topic_chunks: List[Dict], output_dir: Path,
                    topic_idx: int, source_file: str, source_platform: str,
                    source_date: str):
        """Write a topic to its own folder as a markdown file."""
        title = self.generate_topic_title(topic_chunks)
        folder_name = f"{topic_idx:03d}_{title[:50]}"
        folder_name = re.sub(r'[<>:"/\\|?*]', '', folder_name)

        topic_dir = output_dir / folder_name
        topic_dir.mkdir(parents=True, exist_ok=True)

        # Build content
        content_lines = []
        for chunk in topic_chunks:
            speaker_label = "**David:**" if chunk['speaker'] == 'human' else "**AI:**"
            content_lines.append(f"{speaker_label}")
            content_lines.append(chunk['text'])
            content_lines.append("")

        content = '\n'.join(content_lines)
        word_count = len(content.split())
        chunk_count = len(topic_chunks)

        # YAML frontmatter
        yaml = f"""---
title: "{title}"
uuid: "chat-{hashlib.md5(content.encode()).hexdigest()[:12]}"
date_created: "{datetime.now().isoformat()}"
status: "raw"
classification: "chat_extract"
source:
  file: "{source_file}"
  platform: "{source_platform}"
  date: "{source_date}"
  topic_index: {topic_idx}
pipeline:
  stage: "segmented"
  segmented_at: "{datetime.now().isoformat()}"
  curated: false
  scored: false
  vault_integrated: false
stats:
  word_count: {word_count}
  chunk_count: {chunk_count}
  speakers: {list(set(c['speaker'] for c in topic_chunks))}
scores: {{}}
---

# {title}

"""

        md_path = topic_dir / f"{folder_name}.md"
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(yaml + content)

        return str(md_path)


def segment_folder(input_folder: str, output_folder: str):
    """Process all markdown files in input folder."""
    segmenter = TopicSegmenter()
    input_path = Path(input_folder)
    output_path = Path(output_folder)
    output_path.mkdir(parents=True, exist_ok=True)

    md_files = list(input_path.rglob('*.md'))
    print(f"Found {len(md_files)} markdown files to process")

    total_topics = 0
    manifest = []

    for md_file in md_files:
        print(f"\nProcessing: {md_file.name}")

        with open(md_file, 'r', encoding='utf-8', errors='replace') as f:
            text = f.read()

        # Try to detect platform from filename or content
        platform = "unknown"
        for p in ['claude', 'chatgpt', 'gemini', 'deepseek', 'kimi', 'grok']:
            if p in md_file.name.lower() or p in text[:500].lower():
                platform = p
                break

        # Parse and segment
        chunks = segmenter.parse_conversation(text)
        if not chunks:
            print(f"  No parseable chunks found, skipping")
            continue

        topics = segmenter.detect_topics(chunks)
        print(f"  Found {len(topics)} topics in {len(chunks)} chunks")

        # Create subfolder for this conversation
        conv_folder = output_path / md_file.stem
        conv_folder.mkdir(parents=True, exist_ok=True)

        for idx, topic in enumerate(topics):
            path = segmenter.write_topic(
                topic, conv_folder, idx,
                source_file=md_file.name,
                source_platform=platform,
                source_date=datetime.now().strftime('%Y-%m-%d')
            )
            manifest.append({
                'source': md_file.name,
                'topic_index': idx,
                'title': segmenter.generate_topic_title(topic),
                'chunks': len(topic),
                'path': path
            })
            total_topics += 1

    # Write manifest
    manifest_path = output_path / '_MANIFEST.json'
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*60}")
    print(f"DONE: {total_topics} topics extracted from {len(md_files)} conversations")
    print(f"Manifest: {manifest_path}")


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python chat_topic_segmenter.py <input_folder> <output_folder>")
        print("Example: python chat_topic_segmenter.py D:\\CHAT_EXPORTS\\parsed D:\\CHAT_EXPORTS\\segmented")
        sys.exit(1)

    segment_folder(sys.argv[1], sys.argv[2])
