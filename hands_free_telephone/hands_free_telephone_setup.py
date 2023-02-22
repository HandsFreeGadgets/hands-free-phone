#! /usr/bin/env python
import argparse
import subprocess
import sys


DESCRIPTION = "Setupprogram für Sprachassistant für Telefonie."
WHISPER_MODEL_PARAM = 'zu ladendes OpenAI Whisper Modell'
COQUI_TTS_PARAM = 'zu ladendes Coqui TTS Modell'


def __call__(programs: str):
    process = subprocess.Popen(programs, stdout=subprocess.PIPE, shell=True)
    for c in iter(lambda: process.stdout.read(1), b""):
        sys.stdout.buffer.write(c)
    process.wait()


def setup():
    parser = argparse.ArgumentParser(prog=__file__, description=DESCRIPTION)
    parser.add_argument('-whisper_model', dest='whisper_model', type=str, help=WHISPER_MODEL_PARAM, default="medium",
                        choices=["tiny", "base", "small", "medium", "large"])
    parser.add_argument('-coqui_model', type=str, dest='coqui_model', help=COQUI_TTS_PARAM, default='tts_models/de/css10/vits-neon')
    args = parser.parse_args()

    __call__("whisper --language de --model {} doesnotexist".format(args.whisper_model))
    __call__("tts --text 'Das habe ich nicht verstanden.' --model_name {}"
             " --out_path /tmp/coqui.wav".format(args.coqui_model))


if __name__ == '__main__':
    setup()
