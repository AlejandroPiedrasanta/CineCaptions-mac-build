# CineCaptions · By Cinema Productions
# 1_codigo/compat_av.py — puente para usar PyAV 19 con faster-whisper 1.2.1 (que aun llama a av.open(metadata_errors=...)).
"""PyAV 19 quito el argumento `metadata_errors` de `av.open`, y faster-whisper 1.2.1
(audio.py) todavia lo pasa: sin este puente NINGUNA transcripcion funciona.
`aplicar()` envuelve `av.open` para descartar ese argumento. Es idempotente y no
hace nada si la version de PyAV todavia lo acepta. Llamarlo ANTES de usar
faster_whisper (decode_audio / WhisperModel.transcribe)."""


def aplicar():
    try:
        import av
    except Exception:
        return
    if getattr(av.open, '_cinecaptions_compat', False):
        return
    abrir = av.open

    def abrir_compat(*args, **kwargs):
        try:
            return abrir(*args, **kwargs)
        except TypeError:
            if 'metadata_errors' not in kwargs:
                raise
            kwargs.pop('metadata_errors')
            return abrir(*args, **kwargs)

    abrir_compat._cinecaptions_compat = True
    av.open = abrir_compat
