#!/usr/bin/env python3
import argparse
import atexit
import os
import sys
from contextlib import ExitStack
from pathlib import Path

from importlib_resources import files, as_file

from speech_recognition.speech_recognition import listen

# ReSpeaker USB Mic Array
# CHANNELS = 6
# Jabra UC 750 and others
CHANNELS = 1

KEYWORDS = ("telefon",)

RASA_URL = "http://localhost:5005"

PLEASE_WAIT = None

MISUNDERSTOOD = None

LOG_LEVEL = 'DEBUG'

TECHNICAL_PROBLEM = "Ein technischer Fehler ist aufgetreten."
DESCRIPTION = "Sprachassistant für Telefonie."
STT_PARAM = 'Speech-To-Text Modul'
TTS_PARAM = 'Text-To-Speech Modul'
STT_MODEL_PARAM = 'Speech-To-Text Modell. coqui: model.tflite, ibm: de-DE_BroadbandModel, whisper: large | medium | small | base | tiny'
LANG_PARAM = 'Speech-To-Text Sprache. whipser: de, ms: de-DE, google: de'
TTS_MODEL_PARAM = 'Text-To-Speech Modell. coqui: tts_models/de/css10/vits-neon, ms: de-DE-ElkeNeural, ibm: de-DE_BirgitVoice'
MIC_THRESHOLD_PARAM = 'Mikrofon Intensität für Stille'
STT_CREDENTIALS_PARAM = 'Speech-To-Text Zugangsdaten'
TTS_CREDENTIALS_PARAM = 'Text-To-Speech Zugangsdaten'
KEYWORD_MODEL_PARAM = 'Vosk Schlüsselwort Modell'
KEYWORD_PARAM = 'Das Schlüsselwort'
COQUI_SCORER_PARAM = 'Coqui Scorer'
TECHNICAL_PROBLEM_PARAM = 'Satz, der wiedergegeben wird bei technischen Problemem'
PLEASE_WAIT_PARAM = 'Satz, der wiedergegeben wird beim Warten. Standardmäßig nur Piepen'
MISUNDERSTOOD_PARAM = 'Satz, der wiedergegeben wird beim Warten. Standardmäßig nur Piepen'
LOG_LEVEL_PARAM = 'Loglevel: INFO, DEBUG'

COQUI_SPEECH_MODEL_DIR = 'coqui'
VOSK_SPEECH_MODEL_DIR = 'vosk'


def listen_for_telephone():
    if os.getenv('LOCAL'):
        config_path = os.getcwd() + '/.config'
        data_path = os.getcwd() + "/hands_free_telephone"
    else:
        config_path = str(Path.home()) + "/hands_free_telephone"
        file_manager = ExitStack()
        atexit.register(file_manager.close)
        ref = files('hands_free_telephone')
        data_path = file_manager.enter_context(as_file(ref)).name

    os.makedirs(config_path, exist_ok=True)

    parser = argparse.ArgumentParser(
        prog=__file__,
        description=DESCRIPTION)

    parser.add_argument('--stt_mode', type=str, help=STT_PARAM, default='ms',
                        choices=["coqui", "ms", "ibm", "google",
                                 "whisper"])
    parser.add_argument('--tts_mode', type=str, help=TTS_PARAM, default='coqui',
                        choices=["coqui", "ms", "ibm", "google"])
    parser.add_argument('--stt_model', type=str, help=STT_MODEL_PARAM, default='medium')
    parser.add_argument('--lang', type=str, help=LANG_PARAM, default='de-DE')
    parser.add_argument('--tts_model', type=str, help=TTS_MODEL_PARAM, default='tts_models/de/css10/vits-neon')
    parser.add_argument('--mic_threshold', type=float, help=MIC_THRESHOLD_PARAM, default=0.005)
    parser.add_argument('--stt_credentials', type=str, help=STT_CREDENTIALS_PARAM, default="ms-azure.json",
                        choices=["ms-azure.json", "google-cloud.json", "ibm-stt-cloud.json"])
    parser.add_argument('--tts_credentials', type=str, help=TTS_CREDENTIALS_PARAM, default="ms-azure.json",
                        choices=["ms-azure.json", "google-cloud.json", "ibm-tts-cloud.json"])
    parser.add_argument('--keyword_model', type=str, help=KEYWORD_MODEL_PARAM)
    parser.add_argument('--keyword', type=str, help=KEYWORD_PARAM)
    parser.add_argument('--coqui_scorer', type=str, help=COQUI_SCORER_PARAM)
    parser.add_argument('--technical_problem', type=str, help=TECHNICAL_PROBLEM_PARAM)
    parser.add_argument('--misunderstood', type=str, help=MISUNDERSTOOD_PARAM)
    parser.add_argument('--please_wait', type=str, help=PLEASE_WAIT_PARAM)
    parser.add_argument('--log_level', type=str, help=LOG_LEVEL_PARAM)
    args = parser.parse_args()
    keywords = KEYWORDS
    if args.keyword:
        keywords = (args.keyword, )
    keyword_model = data_path + '/' + VOSK_SPEECH_MODEL_DIR
    if args.keyword_model:
        keyword_model = args.keyword_model
    coqui_scorer = data_path + '/' + COQUI_SPEECH_MODEL_DIR + '/kenlm.scorer'
    if args.coqui_scorer:
        coqui_scorer = args.coqui_scorer
    technical_problem = TECHNICAL_PROBLEM
    if args.technical_problem:
        technical_problem = args.technical_problem
    misunderstood = MISUNDERSTOOD
    if args.misunderstood:
        misunderstood = args.misunderstood
    please_wait = PLEASE_WAIT
    if args.please_wait:
        please_wait = args.please_wait
    log_level = LOG_LEVEL
    if args.log_level:
        log_level = args.log_level

    stt_model = data_path + '/' + COQUI_SPEECH_MODEL_DIR + '/' + args.stt_model if args.stt_mode == 'coqui' else None
    if 'stt_model' in sys.argv[1:] and args.stt_model:
        stt_model = args.stt_model

    listen(stt_mode=args.stt_mode, tts_mode=args.tts_mode, keywords=keywords, stt_credentials_json=config_path + '/' +
                                                                                                   args.stt_credentials,
           tts_credentials_json=config_path + '/' + args.tts_credentials,
           config_path=config_path,
           stt_model=stt_model,
           lang=args.lang,
           tts_model=args.tts_model,
           keyword_model=keyword_model,
           scorer=coqui_scorer,
           technical_problem=technical_problem, please_wait=please_wait, mic_threshold=args.mic_threshold,
           rasa_url=RASA_URL, log_level=log_level, channels=CHANNELS, misunderstood=misunderstood
           )


if __name__ == '__main__':
    listen_for_telephone()
