#! /usr/bin/env python
import argparse

import pyaudio

from speech_recognition.speech_recognition import FRAMES_PER_CHUNK, SAMPLE_WIDTH, __get_rms__


DESCRIPTION = "Programm zur Bestimmung des Pegels des Mikrofones beim Sprechen."


def audio_intensity():
    parser = argparse.ArgumentParser(
        prog=__file__,
        description=DESCRIPTION)
    parser.parse_args()
    __measure__(16000)


def __measure__(sample_rate: int, num_samples: int = 10) -> float:
    """ Gets average audio intensity of your mic sound. You can use it to get
        average intensities while you're talking and/or silent. The average
        is the avg of the largest 20% intensities recorded.
        Taken from https://github.com/jeysonmc/python-google-speech-scripts/blob/master/stt_google.py
    """

    print("Getting intensity values from mic.")
    p = pyaudio.PyAudio()

    stream = p.open(format=pyaudio.get_format_from_width(SAMPLE_WIDTH),
                    channels=1,
                    rate=sample_rate,
                    input=True,
                    frames_per_buffer=FRAMES_PER_CHUNK)

    values = [__get_rms__(stream.read(FRAMES_PER_CHUNK), SAMPLE_WIDTH)
              for x in range(num_samples)]

    values = sorted(values, reverse=True)
    r = sum(values[:int(num_samples * 0.2)]) / int(num_samples * 0.2)
    print("Finished")
    print("Average audio intensity is %f" % r)
    stream.close()
    p.terminate()
    return r


if __name__ == '__main__':
    audio_intensity()

