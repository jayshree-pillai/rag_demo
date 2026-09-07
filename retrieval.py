"""
Embed query
→ retrieve Top-K
→ build token-controlled context
"""

import numpy as np


def retrieve_top_k(query, chunks, embed_fn, k):
    query_vector = embed_fn([query])[0]

    def cosine_similarity(chunk):
        chunk_vector = chunk["embedding"]

        return np.dot(query_vector, chunk_vector) / (
            np.linalg.norm(chunk_vector) *
            np.linalg.norm(query_vector)
        )

    return sorted(
        chunks,
        key=cosine_similarity,
        reverse=True,
    )[:k]


def build_context(chunks, max_words=500):
    context = []
    words_used = 0

    for chunk in chunks:
        text = chunk["text"]
        word_count = len(text.split())

        if words_used + word_count > max_words:
            break

        context.append(f'[{chunk["chunk_id"]}] {text}')
        words_used += word_count

    return "\n\n".join(context)


def build_prompt(query, context):
    return f"""
Answer the question using only the provided context.

If the answer is not in the context, say:
"I do not have enough information."

Cite supporting chunks using their chunk IDs.

Context:
{context}

Question:
{query}
"""