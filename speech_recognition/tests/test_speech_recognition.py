import unittest
from copy import copy

from pydub import AudioSegment

from speech_recognition.speech_recognition.speech_recognition import __remove_silence__

unittest.TestLoader.sortTestMethodsUsing = None


class MyTestCase(unittest.TestCase):

    def test_remove_silence(self):
        test_wav = AudioSegment.from_wav("2020-12-27_00:43:12.wav")
        samples = [copy(test_wav.raw_data)]
        __remove_silence__(samples, mic_threshold=0.01,
                                              sample_rate=test_wav.frame_rate,
                                              channels=test_wav.channels,
                                              sample_width=test_wav.sample_width)
        segment = AudioSegment(data=samples[0], sample_width=test_wav.sample_width, frame_rate=test_wav.frame_rate,
                               channels=test_wav.channels)
        segment.export('silenced.wav', format='wav')


if __name__ == '__main__':
    unittest.main()
