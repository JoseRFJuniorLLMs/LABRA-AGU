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
        if ext in ['txt', 'csv']:
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

def _extract_audio_text(file_path: str, ext: str) -> str:
    import speech_recognition as sr
    
    # Se for video, extrair audio primeiro
    if ext in ['mp4', 'avi']:
        try:
            from moviepy.editor import VideoFileClip
            logging.info(f"Extraindo áudio do vídeo {file_path}")
            video = VideoFileClip(file_path)
            
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_audio:
                temp_audio_path = temp_audio.name
                
            video.audio.write_audiofile(temp_audio_path, logger=None)
            video.close()
            
            result = _extract_audio_text(temp_audio_path, 'wav')
            os.remove(temp_audio_path)
            return result
        except ImportError:
            logging.error("Biblioteca moviepy não instalada. Instale para suporte a vídeos.")
            return ""
        except Exception as e:
            logging.error(f"Erro ao extrair áudio de vídeo: {e}")
            return ""
            
    elif ext == 'mp3':
        try:
            from pydub import AudioSegment
            logging.info(f"Convertendo {file_path} de MP3 para WAV")
            audio = AudioSegment.from_mp3(file_path)
            
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_wav:
                temp_wav_path = temp_wav.name
                
            audio.export(temp_wav_path, format="wav")
            
            result = _extract_audio_text(temp_wav_path, 'wav')
            os.remove(temp_wav_path)
            return result
        except ImportError:
            logging.error("Biblioteca pydub não instalada. Instale para suporte a MP3.")
            return ""
        except Exception as e:
            logging.error(f"Erro ao converter MP3: {e}")
            return ""
            
    elif ext == 'wav':
        logging.info(f"Transcrevendo áudio {file_path}")
        recognizer = sr.Recognizer()
        try:
            with sr.AudioFile(file_path) as source:
                audio_data = recognizer.record(source)
                # Utiliza o Google Web Speech API como fallback offline genérico/fácil
                # Obs: Em produção, usar Whisper ou uma API melhor
                text = recognizer.recognize_google(audio_data, language="pt-BR")
                return text
        except sr.UnknownValueError:
            logging.warning("SpeechRecognition não conseguiu entender o áudio.")
            return ""
        except sr.RequestError as e:
            logging.error(f"Erro no serviço do SpeechRecognition: {e}")
            return ""
        except Exception as e:
            logging.error(f"Erro ao transcrever arquivo WAV: {e}")
            return ""
            
    return ""
