import os
import zipfile
import tempfile
import logging

def extract_text_from_file(file_path: str) -> str:
    """
    Roteador inteligente para extrair texto de vários formatos.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")

    ext = file_path.lower().split('.')[-1]

    try:
        if ext in ['txt', 'csv', 'log']:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()

        elif ext == 'pdf':
            import pdfplumber
            text = ""
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            return text

        elif ext == 'docx':
            import docx
            doc = docx.Document(file_path)
            return "\n".join([para.text for para in doc.paragraphs])

        elif ext == 'zip':
            text = ""
            with tempfile.TemporaryDirectory() as temp_dir:
                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)
                    for root, _, files in os.walk(temp_dir):
                        for file in files:
                            extracted_file_path = os.path.join(root, file)
                            logging.info(f"Extraindo de arquivo dentro do ZIP: {file}")
                            text += extract_text_from_file(extracted_file_path) + "\n\n"
            return text

        elif ext in ['mp3', 'wav', 'mp4', 'avi']:
            return _extract_audio_text(file_path, ext)

        else:
            logging.warning(f"Formato não suportado para extração: {ext}")
            return ""

    except Exception as e:
        logging.error(f"Erro ao extrair texto de {file_path}: {e}")
        return ""

# Cache do modelo Whisper (carregar uma vez por processo é caro).
_WHISPER_CACHE = {}


def _whisper_model(size: str):
    if size not in _WHISPER_CACHE:
        from faster_whisper import WhisperModel
        # CPU int8 por defeito (corre em qualquer máquina); device/compute
        # configuráveis por env para acelerar em GPU quando disponível.
        device = os.environ.get("LABRA_WHISPER_DEVICE", "cpu")
        compute = os.environ.get("LABRA_WHISPER_COMPUTE", "int8")
        _WHISPER_CACHE[size] = WhisperModel(size, device=device, compute_type=compute)
    return _WHISPER_CACHE[size]


def _extract_audio_text(file_path: str, ext: str) -> str:
    """
    Transcrição de áudio/vídeo 100% LOCAL via faster-whisper.

    REGRA DE PRIVACIDADE (LGPD / sigilo): dado de processo — escutas,
    depoimentos, audiências — NUNCA sai da máquina. Não há chamada a serviço
    externo (a versão anterior enviava o áudio para a Google Web Speech API).
    O faster-whisper decodifica mp3/wav/mp4/avi diretamente (via ffmpeg), logo
    não é preciso converter formatos à mão.

    Configurável por env:
      LABRA_WHISPER_MODEL   (tiny|base|small|medium|large-v3; default 'small')
      LABRA_WHISPER_DEVICE  (cpu|cuda; default 'cpu')
      LABRA_WHISPER_COMPUTE (int8|int8_float16|float16; default 'int8')
    """
    try:
        model = _whisper_model(os.environ.get("LABRA_WHISPER_MODEL", "small"))
    except ImportError:
        logging.error(
            "faster-whisper não instalado — transcrição local indisponível. "
            "Instale: pip install faster-whisper")
        return ""
    try:
        logging.info(f"Transcrevendo localmente (Whisper): {file_path}")
        segments, _info = model.transcribe(file_path, language="pt", vad_filter=True)
        return " ".join(seg.text.strip() for seg in segments).strip()
    except Exception as e:
        logging.error(f"Erro na transcrição local de {file_path}: {e}")
        return ""
