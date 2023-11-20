import asyncio
import datetime
import importlib
import importlib.resources
import json
import logging
import logging.config
import math
import os
import platform
import random
import string
import struct
import time
from builtins import int, max
from datetime import datetime
from logging import Logger
from pathlib import Path
from time import sleep
from typing import List, Tuple

import miniaudio
import numpy as np
import pyaudio
import requests
import vosk
import yaml
import whisper
from TTS.api import TTS
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator
from ibm_watson import TextToSpeechV1
from ibm_watson.speech_to_text_v1 import SpeechToTextV1
from google.cloud import speech, texttospeech
from google.oauth2.service_account import Credentials
import azure.cognitiveservices.speech as speechsdk
from azure.cognitiveservices.speech import AudioDataStream, StreamStatus
from azure.cognitiveservices.speech.audio import PushAudioInputStream, AudioStreamFormat
from cachetools import TTLCache
from jinja2.runtime import new_context
from pydub import AudioSegment, playback
if platform.machine() != 'aarch64':
    from stt import Model

#: The keyword length in seconds for recognition
KEYWORD_LENGTH = 2

#: Silence limit in seconds. The max amount of seconds where only silence is recorded. When this time passes the
#: utterance is considered as being finished.
SILENCE_LIMIT = 2

#: Frames per chunk
FRAMES_PER_CHUNK = 16000

# Sample rate
SAMPLE_RATE=16000

#: Seconds of audio to keep in a sliding window of the record audio.
AUDIO_RECORD_BUFFER_WINDOW = 20

#: The sample width (here 16 bits) for an audio sample
SAMPLE_WIDTH = 2

tts_cache = TTLCache(maxsize=50, ttl=3600 * 24)

DEFAULT_LOG_CONFIG = """version: 1
formatters:
  simple:
    format: '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
  full:
    format: '%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(filename)s:%(funcName)s:%(lineno)d - %(message)s'
handlers:
  console:
    class: logging.StreamHandler
    level: DEBUG
    formatter: simple
    stream: ext://sys.stdout
  file:
    class: logging.handlers.RotatingFileHandler
    level: DEBUG
    formatter: full
    filename: {1}
    backupCount: 14
loggers:
  {0}:
    level: {2}
    handlers: [console, file]
    propagate: no
root:
  level: INFO
  handlers: [console, file]
"""

logger: Logger = None


def __get_log_dir__(config_path: str):
    return config_path + "/log"


def __config_logger__(config_path: str, log_level: str = 'INFO'):
    log_config_file = config_path + "/log.yaml"
    log_dir = __get_log_dir__(config_path)
    log_filename = log_dir + "/log.txt"

    os.makedirs(log_dir, exist_ok=True)
    if not os.path.isfile(log_config_file) or os.path.getsize(log_config_file) == 0:
        with open(log_config_file, mode='w', encoding='utf-8') as logfile:
            logfile.write(DEFAULT_LOG_CONFIG.format(__name__, log_filename, log_level))
    else:
        with open(log_config_file, 'r+', encoding='utf-8') as logfile:
            new_content = logfile.read().format(__name__, log_filename, log_level)
            logfile.seek(0)
            logfile.write(new_content)
    with open(log_config_file, 'r', encoding='utf-8') as logfile:
        log_config = yaml.safe_load(logfile.read())
        logging.config.dictConfig(log_config)
    global logger
    logger = logging.getLogger(__name__)


def __customer_id__() -> str:
    return Path("/etc/machine-id").read_text().strip()


async def play_text(mode: str, preloaded: any, model: str, lang: str, text: str, tts_credentials_json: str):
    if text not in tts_cache:
        with open(tts_credentials_json) as f:
            auth = json.load(f)
        if mode == 'coqui':
            # wav = preloaded.tts_to_file(text=text)
            wav = preloaded.tts(text=text)
            wav = np.array(wav)
            wav_norm = wav * (32767 / max(0.01, np.max(np.abs(wav))))
            wav_norm = wav_norm.astype(np.int16)
            tts_cache[text] = wav_norm.tobytes()
        elif mode == 'ibm':
            authenticator = IAMAuthenticator(auth['apikey'])
            text_to_speech = TextToSpeechV1(
                authenticator=authenticator
            )
            text_to_speech.set_service_url('https://api.eu-de.text-to-speech.watson.cloud.ibm.com')
            text_to_speech.set_default_headers({'x-watson-learning-opt-out': "true",
                                                'X-Watson-Metadata': "customer_id={}".format(__customer_id__())})
            response = text_to_speech.synthesize(
                text, voice=model,
                accept='audio/mp3'
            )
            if 200 != response.get_status_code():
                logger.warning("Error getting transcription: %s", response)
                return
            # cache
            tts_cache[text] = response.get_result().content
        elif mode == 'google':
            client = texttospeech.TextToSpeechClient(
                credentials=Credentials.from_service_account_file(tts_credentials_json))
            synthesis_input = texttospeech.SynthesisInput(text=text)
            voice = texttospeech.VoiceSelectionParams(
                language_code=lang, ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL
            )
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3
            )
            response = client.synthesize_speech(
                input=synthesis_input, voice=voice, audio_config=audio_config
            )
            # cache
            tts_cache[text] = response.audio_content
        elif mode == 'ms':
            speech_config = speechsdk.SpeechConfig(subscription=auth['api-key'],
                                                   region="westeurope")
            # Opus not decoded in aarhc64 with miniaudio
            speech_config.set_speech_synthesis_output_format(
                speechsdk.SpeechSynthesisOutputFormat.Audio16Khz64KBitRateMonoMp3)
            speech_config.speech_synthesis_voice_name = model
            speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=None)
            speech_synthesis_result = speech_synthesizer.speak_text_async(text).get()
            audio_content = bytes(64000)
            stream = AudioDataStream(speech_synthesis_result)
            audio_size = stream.read_data(audio_content)
            if stream.status != StreamStatus.AllData:
                logger.warning("Error getting transcription: %s", stream.cancellation_details)
                return
            tts_cache[text] = audio_content[:audio_size]
        else:
            raise RuntimeError('No supported TTS python module found.')
    if mode != 'coqui':
        audio = miniaudio.decode(data=tts_cache[text], nchannels=1, sample_rate=48000)
        segment = AudioSegment(data=audio.samples, sample_width=audio.sample_width, frame_rate=audio.sample_rate,
                           channels=audio.nchannels)
    else:
        segment = AudioSegment(data=tts_cache[text], sample_width=2, frame_rate=22050,
                               channels=1)
    playback.play(segment)


async def play_file(file: str):
    audio_data = importlib.resources.read_binary('speech_recognition', file)
    audio = miniaudio.decode(data=audio_data, nchannels=2, sample_rate=48000)
    segment = AudioSegment(data=audio.samples, sample_width=audio.sample_width, frame_rate=audio.sample_rate,
                           channels=audio.nchannels)
    playback.play(segment)


#: Records the audio samples for transcription
audio_samples: List = None


def __audio_callback__(in_data, frame_count, time_info, status_flags):
    channels = int(len(in_data) / (SAMPLE_WIDTH * frame_count))
    bytes_in_data = bytes(in_data)
    first_channel = bytes(
        [bytes_in_data[i] for i, _ in enumerate(bytes_in_data) if (i // SAMPLE_WIDTH) % channels == 0])
    audio_samples.append(first_channel)
    return None, pyaudio.paContinue


def metadata_to_string(metadata) -> str:
    return ''.join(token.text for token in metadata.tokens)


def metadata_to_start_time(metadata, keywords: List[str]) -> float:
    text = metadata_to_string(metadata)
    for keyword in keywords:
        if keyword in text:
            start_index = text.index(keyword)
            return metadata.tokens[start_index].start_time
    return ValueError('Keyword not found in text: {}'.format(text))


def listen(stt_mode: str, tts_mode: str,
           stt_model: str, tts_model: str,
           lang: str,
           keyword_model: str,
           mic_threshold: float, keywords: Tuple[str, ...],
           stt_credentials_json: str, tts_credentials_json: str,
           config_path: str, technical_problem: str,
           cloud_model_customization: str = None, grammar: str = None,
           please_wait: str = None, misunderstood: str = None,
           rasa_url: str = 'http://localhost:5006',
           scorer: str = None, log_level: str = 'INFO', channels: int = 1
           ):
    """
    Listens for a speech command. It will listen for given keywords and delegate the complete speech recognition to
    the IBM cloud speech service. The keyword length is assumed to be within a time frame of #KEYWORD_LENGTH and
    the complete command must be less than #AUDIO_RECORD_BUFFER_WINDOW.

    :param stt_mode: The Speech to Text engine to use: 'coqui', 'whisper', 'ms', 'ibm', 'google'.
    :param tts_mode: The Text To Speech engine to use: 'coqui', 'ms', 'ibm', 'google'.
    :param stt_model: The Coqui STT, Whisper or IBM model to load for speech recognition. The Coqui model must be trained with 16000 Hz. Possible values for Whisper are 'large', 'medium', 'small', 'base', 'tiny'
    :param tts_model: The Coqui TTS model to load for offline production.
    :param lang: The Speech to text language: E.g.: 'de-DE', 'de'
    :param mic_threshold: The microphone threshold level which is above noise. See the function #audio_intensity.
    :param keyword_model: The Vosk keyword model to load.
    :param scorer: The Coqui scorer
    :param keywords: The keywords to use to trigger speech recognition.
    :param stt_credentials_json: The STT credentials as JSON. For MS create a JSON file with a 'api-key' key.
    :param tts_credentials_json: The TTS JSON credentials as JSON.  For MS create a JSON file with a 'api-key' key.
    :param config_path: The config path where to store (log) configuration.
    :param rasa_url: The Rasa server URL.
    :param technical_problem: text for saying "Technical Problem".
    :param cloud_model_customization: The model customization to use with the cloud model STT provider.
    :param grammar: The grammar to use with the cloud model STT provider.
    :param please_wait: Text for saying "Please Wait".
    :param misunderstood: text for saying "I have misunderstood this". Used when the script has recognized a keyword, but it turned out it was none.
    :param log_level: The log level. Use DEBUG for verbose output.
    :param channels: The channels to record. In case of the ReSpeaker USB Mic Array these are 6 channels
    (when using the default firmware), only the first channel is used for ASR.
    """
    os.makedirs(config_path, exist_ok=True)
    __config_logger__(config_path, log_level=log_level)

    stt_preloaded = None
    if stt_mode == 'coqui':
        stt_preloaded = Model(stt_model)
        stt_preloaded.setBeamWidth(1024)
        stt_preloaded.enableExternalScorer(scorer)
    elif stt_mode == 'whisper':
        stt_preloaded = whisper.load_model(stt_model)

    tts_preloaded = None
    if tts_mode == 'coqui':
        tts_preloaded = TTS(model_name=tts_model, progress_bar=False)

    p = pyaudio.PyAudio()
    audio_stream = p.open(format=pyaudio.get_format_from_width(SAMPLE_WIDTH), channels=channels, rate=SAMPLE_RATE,
                          input=True,
                          frames_per_buffer=FRAMES_PER_CHUNK, stream_callback=__audio_callback__)
    chunks_per_second = SAMPLE_RATE / FRAMES_PER_CHUNK
    global audio_samples
    audio_samples = []

    vosk_model = vosk.Model(keyword_model)
    vosk_rec = vosk.KaldiRecognizer(vosk_model, SAMPLE_RATE)
    vosk_rec.SetWords(True)
    vosk_rec.SetMaxAlternatives(0)

    samples_key_word = int(math.ceil(chunks_per_second * KEYWORD_LENGTH))

    while audio_stream.is_active():
        try:
            # take the program start into account where this can be still empty
            if len(audio_samples) > 0:
                # take last n seconds and run interference on keywords
                start_sub_samples = len(audio_samples) - samples_key_word
                if start_sub_samples <= 0:
                    continue
                processing_end_sample = len(audio_samples)
                inference_data = b"".join(audio_samples[start_sub_samples:min(start_sub_samples+samples_key_word, 
                                                                              processing_end_sample)])
                start_time_keyword = 0
                if vosk_rec.AcceptWaveform(inference_data):
                    as_json = json.loads(vosk_rec.Result())
                    text = as_json['text']
                    if text:
                        logger.debug('Keyword recognition: %s' % as_json)
                else:
                    as_json = json.loads(vosk_rec.PartialResult())
                    text = as_json['partial']
                    if text:
                        logger.debug('Partial keyword recognition: %s' % as_json)
                        if len(set(keywords).intersection(text.split())) > 0:
                            vosk_rec.Reset()
                if len(audio_samples) > 0 and len(set(keywords).intersection(text.split())) > 0 \
                        or text.startswith(keywords):
                    logger.info('Understood keyword phrase: %s', text)
                    # remove unneeded prequel before keyword
                    # minus 1 sample to get potential important pre-audio information if word recognition is on the edge
                    skip_samples = start_sub_samples + int(chunks_per_second * math.floor(start_time_keyword)) - 1
                    if skip_samples < 0:
                        skip_samples = 0
                    [audio_samples.pop(0) for x in range(skip_samples)]

                    # wait until silence or max time has elapsed
                    while audio_stream.is_active():
                        start_slide_window = len(audio_samples) - int(
                            math.ceil(chunks_per_second * SILENCE_LIMIT)) + samples_key_word-1
                        logger.debug('start slide window %d', start_slide_window)
                        if start_slide_window < 0:
                            start_slide_window = 0
                        slide_window = b''.join(list(audio_samples)[start_slide_window:])
                        __log_audio__(slide_window, SAMPLE_RATE, channels, SAMPLE_WIDTH, config_path, 'rms')
                        mic_level = __get_rms__(slide_window, SAMPLE_WIDTH)
                        if len(audio_samples) > 0 and (
                                mic_level < mic_threshold or len(audio_samples) >= AUDIO_RECORD_BUFFER_WINDOW):
                            logger.debug('Mic level: %f, samples: %d' % (mic_level, len(audio_samples)))
                            # create copy to manipulate audio samples
                            current_audio_samples = list(audio_samples.copy())
                            # remove silence part from end
                            __remove_silence__(_audio_samples=current_audio_samples, mic_threshold=mic_threshold,
                                               sample_width=SAMPLE_WIDTH, sample_rate=SAMPLE_RATE, channels=1)
                            samples = b''.join(current_audio_samples)
                            if log_level == 'DEBUG':
                                # save audio
                                __log_audio__(data=samples, sample_rate=SAMPLE_RATE, channels=1,
                                              sample_width=SAMPLE_WIDTH, config_path=config_path)
                            logger.debug('Sending %d bytes (%d sec) for recognition', len(samples),
                                         len(samples) / SAMPLE_RATE / SAMPLE_WIDTH)
                            try:
                                __recognize_command__(stt_mode=stt_mode, stt_model=stt_model, 
                                                      stt_preloaded=stt_preloaded,
                                                      tts_mode=tts_mode, tts_model=tts_model,
                                                      tts_preloaded=tts_preloaded,
                                                      lang=lang,
                                                      stt_credentials_json=stt_credentials_json,
                                                      tts_credentials_json=tts_credentials_json,
                                                      data=samples,
                                                      sample_rate=SAMPLE_RATE, channels=1,
                                                      cloud_model_customization=cloud_model_customization,
                                                      grammar=grammar,
                                                      keywords=keywords, rasa_url=rasa_url,
                                                      please_wait=please_wait, misunderstood=misunderstood)
                            finally:
                                audio_samples.clear()
                            break
                        else:
                            sleep(1)
                else:
                    sleep(1)
                    # remove all samples included in the speech recognition already evaluated
                    [audio_samples.pop(0) for _ in range(processing_end_sample - max(samples_key_word-1, 0))]
        except Exception as e:
            logging.exception("Technical problem: %s", str(e))
            try:
                asyncio.run(play_text(tts_mode, tts_preloaded, tts_model, lang=lang, text=technical_problem,
                                      tts_credentials_json=tts_credentials_json))
            except Exception as e2:
                logging.exception("Problem: %s while reporting technical problem: %s", str(e2), str(e))

    audio_stream.close()
    p.terminate()


SILENCE_SAFETY_FRAMES = 5


def __remove_silence__(_audio_samples: List[bytes], mic_threshold: float, sample_rate: int, channels: int,
                       sample_width: int):
    # how much is 100 ms
    chunk_size = int(channels * sample_rate * sample_width * 0.1)
    # remove silence from end
    for j, sample in reversed(list(enumerate(_audio_samples))):
        chunks = [sample[i:i + chunk_size] for i in range(0, len(sample), chunk_size)]
        silence_offset = len(chunks)
        for chunk in reversed(chunks):
            mic_level = __get_rms__(chunk, sample_width=sample_width)
            if mic_level < mic_threshold:
                silence_offset -= 1
            else:
                break
        # add some safety frame after
        chunks = chunks[:min(len(chunks), silence_offset + SILENCE_SAFETY_FRAMES)]
        _audio_samples[j] = b''.join(chunks)
        # stop removing frames if end of silence
        if len(chunks) > 0:
            break
    _audio_samples[:] = [x for x in _audio_samples if len(x) > 0]


def __log_audio__(data: bytes, sample_rate: int, channels: int, sample_width: int, config_path: str,
                  prefix: str = None):
    segment = AudioSegment(data=data, sample_width=sample_width, frame_rate=sample_rate, channels=channels)
    log_dir = __get_log_dir__(config_path)
    now = datetime.now()
    dt_string = now.strftime("%Y-%m-%d_%H:%M:%S:%f")
    if prefix:
        dt_string = prefix + dt_string
    segment.export(format="wav", out_f=log_dir + '/' + dt_string + '.wav')


def __compress_audio__(data: bytes, sample_rate: int, channels: int, sample_width: int) -> str:
    segment = AudioSegment(data=data, sample_width=sample_width, frame_rate=sample_rate, channels=channels)
    encoded = segment.export(format="flac")
    with encoded as f:
        contents = f.read()
    return contents


def __recognize_command__(stt_mode: str, stt_preloaded: any, stt_model: str, lang: str,
                          tts_mode: str, tts_preloaded: any, tts_model: str,
                          stt_credentials_json: str, tts_credentials_json: str, data: bytes,
                          sample_rate: int, channels: int,
                          cloud_model_customization: str, grammar: str,
                          keywords: List[str], rasa_url: str,
                          please_wait: str = None, misunderstood: str = None
                          ):
    if please_wait:
        asyncio.run(play_text(tts_mode, tts_preloaded, tts_model, lang, text=please_wait, tts_credentials_json=tts_credentials_json))
    else:
        asyncio.run(play_file('input_ok_1_clean.wav'))
    text = None
    if stt_mode == 'coqui':
        inference_data = np.frombuffer(data, dtype='int16')
        metadata = stt_preloaded.sttWithMetadata(inference_data)
        text = metadata_to_string(metadata.transcripts[0])
        logger.info("Received Coqui transcript: %s", text)
        logger.debug("Received Coqui metadata: %s", metadata)
    elif stt_mode == 'whisper':
        audio = np.frombuffer(data, np.int16).flatten().astype(np.float32) / 32768.0
        audio = whisper.pad_or_trim(audio)
        # make log-Mel spectrogram and move to the same device as the model
        mel = whisper.log_mel_spectrogram(audio).to(stt_preloaded.device)
        # decode the audio
        options = whisper.DecodingOptions(language=lang)
        text = whisper.decode(stt_preloaded, mel, options)
        logger.info("Received Whisper transcript: %s", text)
    else:
        # all other online services take compressed data
        data = __compress_audio__(data, sample_rate, 1, SAMPLE_WIDTH)
        if stt_mode == 'ibm':
            from ibm_cloud_sdk_core.authenticators import IAMAuthenticator
            from ibm_watson import TextToSpeechV1
            from ibm_watson.speech_to_text_v1 import SpeechToTextV1
            with open(stt_credentials_json) as f:
                auth = json.load(f)
            authenticator = IAMAuthenticator(auth['apikey'])
            speech_to_text = SpeechToTextV1(
                authenticator=authenticator
            )
            speech_to_text.set_service_url('https://api.eu-de.speech-to-text.watson.cloud.ibm.com')
            speech_to_text.set_default_headers({'x-watson-learning-opt-out': "true",
                                                'X-Watson-Metadata': "customer_id={}".format(__customer_id__())})
            response = speech_to_text.recognize(
                audio=data,
                content_type='audio/flac',
                model=stt_model,
                keywords=keywords,
                keywords_threshold=0.9,
                # not working for German
                smart_formatting=True,
                background_audio_suppression=0.5,
                max_alternatives=1,
                end_of_phrase_silence_time=2,
                language_customization_id=cloud_model_customization,
                grammar_name=grammar
            )
            if not (200 <= response.get_status_code() < 300):
                logger.warning("Error getting transcription: %s", response)
                return
            results = response.get_result()
            if len(results) > 0 and results['results']:
                confidence = 0.0
                for result in results['results']:
                    new_confidence = float(result['alternatives'][0]['confidence'])
                    if new_confidence > confidence:
                        confidence = new_confidence
                        text = result['alternatives'][0]['transcript']
                logger.info("Received transcript: %s", text)
                logger.debug("Received response: %s", response)
                if not confidence >= 0.7:
                    logger.info("Confidence too low: %s", text)
                    text = None
            else:
                logger.warning("Speech not recognized: %s", results if results else '(empty)')
        elif stt_mode == 'google':
            client = speech.SpeechClient(
                credentials=Credentials.from_service_account_file(stt_credentials_json))
            audio = speech.RecognitionAudio(content=data)
            config = speech.RecognitionConfig(encoding=speech.RecognitionConfig.AudioEncoding.FLAC,
                                              sample_rate_hertz=sample_rate,
                                              language_code=lang,
                                              audio_channel_count=channels
                                              )
            # Detects speech in the audio file
            response = client.recognize(config=config, audio=audio)
            if len(response.results) > 0:
                text = response.results[0].alternatives[0].transcript
                logger.info("Received Google transcript: %s", text)
                logger.info("Received Google response: %s", response)
            else:
                logger.warning("Received unsuccessful Google response: %s", response)
        elif stt_mode == 'ms':
            with open(stt_credentials_json) as f:
                auth = json.load(f)
            speech_config = speechsdk.SpeechConfig(subscription=auth['api-key'],
                                                   region="westeurope",
                                                   speech_recognition_language=lang)
            stream = PushAudioInputStream(stream_format=
                                          AudioStreamFormat(compressed_stream_format=speechsdk.AudioStreamContainerFormat.FLAC))
            audio_input = speechsdk.AudioConfig(stream=stream)
            stream.write(data)
            stream.close()
            speech_recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_input)

            speech_recognizer.start_continuous_recognition()
            done = False

            def stop_recognition(evt):
                logger.debug("Stopped MS Azure recognition: %s", evt)
                nonlocal done
                done = True

            def recognized(evt):
                logger.info("Recognized MS Azure transcript: %s", evt)
                nonlocal text
                if not text:
                    text = ""
                else:
                    text += " "
                text += evt.result.text

            speech_recognizer.recognized.connect(recognized)
            speech_recognizer.session_stopped.connect(stop_recognition)
            speech_recognizer.canceled.connect(stop_recognition)
            while not done:
                time.sleep(.5)
            speech_recognizer.stop_continuous_recognition()
        else:
            raise RuntimeError('No supported STT provided.')

    if text:
        pass
        # __handle_command__(command=text, keywords=keywords, rasa_url=rasa_url,
        #                    tts_credentials_json=tts_credentials_json, tts_mode=tts_mode,
        #                    tts_preloaded=tts_preloaded, tts_model=tts_model, tts_lang=lang,
        #                    misunderstood=misunderstood)
    else:
        if misunderstood:
            asyncio.run(play_text(tts_mode, tts_preloaded, tts_model, lang, misunderstood, tts_credentials_json=tts_credentials_json))
        else:
            asyncio.run(play_file('denybeep1.wav'))


def __handle_command__(command: str, keywords: List[str], rasa_url: str,
                       tts_mode: str, tts_preloaded: any, tts_model: str, tts_lang: str,
                       tts_credentials_json: str, misunderstood: str = None):
    command = command.lower()
    if not any(keyword in command for keyword in keywords):
        if misunderstood:
            asyncio.run(play_text(tts_mode, tts_preloaded, tts_model, tts_lang, misunderstood, tts_credentials_json=tts_credentials_json))
        else:
            asyncio.run(play_file('denybeep1.wav'))
        return

    # remove words before keyword
    for keyword in keywords:
        found_index = command.find(keyword)
        if found_index >= 0:
            command = command[found_index:]
            # remove first word = keyword
            keyword_separated = command.split(' ', 1)
            if len(keyword_separated) > 1:
                command = keyword_separated[1]
    if len(command) == 0:
        return
    conversation_id = ''.join(random.choice(string.ascii_letters + string.digits) for i in range(16))
    request = {
        "text": command,
        "sender": "user"
    }
    response = requests.post(rasa_url + "/conversations/{}/messages".format(conversation_id), json=request)
    if response.status_code != 200:
        raise IOError("Error talking to RASA server: {}".format(response.content))
    message = response.json()
    logger.info("Recognized intent: %s | entities: %s", message["latest_message"]["intent"],
                message["latest_message"]["entities"])
    response = requests.post(rasa_url + "/conversations/{}/predict".format(conversation_id))
    if response.status_code != 200:
        raise IOError("Error talking to RASA server: {}".format(response.content))
    message = response.json()
    logger.info("Identified action: %s | policy: %s | confidence: %s", message["scores"][0], message["policy"],
                message["confidence"])
    # trigger action
    request = {
        "name": message["scores"][0]['action'],
        "policy": message["policy"],
        "confidence": message["confidence"]
    }
    response = requests.post(rasa_url + "/conversations/{}/execute".format(conversation_id), json=request)
    if response.status_code != 200:
        raise IOError("Error talking to RASA server: {}".format(response.content))
    message = response.json()
    if message['messages']:
        text = message["messages"][0]["text"]
        logger.info("Received message response: %s", text)
        asyncio.run(play_text(tts_mode, tts_preloaded, tts_model, tts_lang, text, tts_credentials_json=tts_credentials_json))


SHORT_NORMALIZE = (1.0 / 32768.0)


def __get_rms__(block: bytes, sample_width: int) -> float:
    # RMS amplitude is defined as the square root of the
    # mean over time of the square of the amplitude.

    if SAMPLE_WIDTH == 2:
        normalize_factor = SHORT_NORMALIZE
    else:
        raise ValueError('Sample width {} not supported'.format(sample_width))

    # we will get one short out for each
    # two chars in the string.
    count = len(block) / sample_width
    _format = "%dh" % count
    shorts = struct.unpack(_format, block)

    # iterate over the block.
    sum_squares = 0.0
    for sample in shorts:
        # sample is a signed short in +/- 32768.
        # normalize it to 1.0
        n = sample * normalize_factor
        sum_squares += n * n
    if count == 0:
        return 0
    return math.sqrt(sum_squares / count)
