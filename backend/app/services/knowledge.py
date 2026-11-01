"""Text extraction, chunking, and lightweight bilingual keyword retrieval."""

import re
from io import BytesIO

from sqlalchemy.orm import Session

from ..models import ConfigItem, KnowledgeChunk

SUPPORTED_SUFFIXES = {'.txt', '.md', '.csv', '.json', '.pdf'}


def extract_text(filename: str, data: bytes) -> str:
    suffix = '.' + filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError('仅支持 TXT、MD、CSV、JSON 和文本型 PDF')
    if not data:
        raise ValueError('文件为空')
    if suffix == '.pdf':
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise ValueError('服务端未安装 pypdf，请先安装 backend/requirements.txt') from exc
        try:
            reader = PdfReader(BytesIO(data))
            text = '\n'.join(page.extract_text() or '' for page in reader.pages)
        except Exception as exc:
            raise ValueError('PDF 无法解析，请检查文件是否损坏或加密') from exc
    else:
        text = ''
        for encoding in ('utf-8-sig', 'gb18030'):
            try:
                text = data.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        if not text:
            raise ValueError('文本编码无法识别')
    text = text.strip()
    if not text:
        raise ValueError('未提取到文字；扫描版 PDF 暂不支持')
    return text[:300_000]


def chunk_text(text: str, size: int = 700, overlap: int = 80) -> list[str]:
    clean = re.sub(r'\r\n?', '\n', text).strip()
    paragraphs = [part.strip() for part in re.split(r'\n{2,}', clean) if part.strip()]
    chunks = []
    buffer = ''
    for paragraph in paragraphs:
        if buffer and len(buffer) + len(paragraph) + 1 > size:
            chunks.append(buffer)
            buffer = ''
        if len(paragraph) > size:
            if buffer:
                chunks.append(buffer)
                buffer = ''
            step = size - overlap
            chunks.extend(paragraph[start:start + size] for start in range(0, len(paragraph), step))
        else:
            buffer = (buffer + '\n' + paragraph).strip()
    if buffer:
        chunks.append(buffer)
    return chunks


def search_chunks(db: Session, query: str, knowledge_id: int | None = None, limit: int = 8) -> list[dict]:
    tokens = list(dict.fromkeys(re.findall(r'[\u4e00-\u9fff]|[a-z0-9_.-]{2,}', query.lower())))
    if not tokens:
        return []
    rows = db.query(KnowledgeChunk, ConfigItem).join(
        ConfigItem, KnowledgeChunk.knowledge_id == ConfigItem.id
    ).filter(ConfigItem.category == 'knowledge', ConfigItem.status == '已启用')
    if knowledge_id is not None:
        rows = rows.filter(KnowledgeChunk.knowledge_id == knowledge_id)
    hits = []
    for chunk, base in rows.all():
        lower = chunk.content.lower()
        score = sum(lower.count(token) for token in tokens)
        if score:
            hits.append({'chunk_id': chunk.id, 'document_id': chunk.document_id,
                         'knowledge_id': base.id, 'knowledge_name': base.name,
                         'content': chunk.content, 'score': score})
    return sorted(hits, key=lambda item: item['score'], reverse=True)[:limit]
