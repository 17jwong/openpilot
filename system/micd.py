#!/usr/bin/env python3
import numpy as np
import threading

from cereal import messaging
from openpilot.common.retry import retry
from openpilot.common.swaglog import cloudlog
from openpilot.common.params import Params


FFT_SAMPLES = 1280
REFERENCE_SPL = 2e-5  # newtons/m^2
SAMPLE_BUFFER = 1280  # (80ms)
SAMPLE_RATE = 16000


def calculate_spl(measurements):
  # https://www.engineeringtoolbox.com/sound-pressure-d_711.html
  sound_pressure = np.sqrt(np.mean(measurements ** 2))  # RMS of amplitudes
  if sound_pressure > 0:
    sound_pressure_level = 20 * np.log10(sound_pressure / REFERENCE_SPL)  # dB
  else:
    sound_pressure_level = 0
  return sound_pressure, sound_pressure_level


def apply_a_weighting(measurements: np.ndarray) -> np.ndarray:
  # Generate a Hanning window of the same length as the audio measurements
  measurements_windowed = measurements * np.hanning(len(measurements))

  # Calculate the frequency axis for the signal
  freqs = np.fft.fftfreq(measurements_windowed.size, d=1 / SAMPLE_RATE)

  # Calculate the A-weighting filter
  # https://en.wikipedia.org/wiki/A-weighting
  A = 12194 ** 2 * freqs ** 4 / ((freqs ** 2 + 20.6 ** 2) * (freqs ** 2 + 12194 ** 2) * np.sqrt((freqs ** 2 + 107.7 ** 2) * (freqs ** 2 + 737.9 ** 2)))
  A /= np.max(A)  # Normalize the filter

  # Apply the A-weighting filter to the signal
  return np.abs(np.fft.ifft(np.fft.fft(measurements_windowed) * A))


class Mic:
  def __init__(self):
    self.pm = messaging.PubMaster(['microphone', 'microphoneRaw'])
    self.indata_ready_event = threading.Event()

    self.measurements = np.empty(0)

    self.sound_pressure = 0
    self.sound_pressure_weighted = 0
    self.sound_pressure_level_weighted = 0
    self.frame_index = 0
    self.frame_index_last = 0
    self.raw_sample = np.empty(SAMPLE_BUFFER, dtype=np.float32)
    self.params = Params()
    self.listening_allowed = False

  def update(self):
    self.listening_allowed = self.params.get_bool("VoiceControl")
    msg = messaging.new_message('microphone', valid=True)
    msg.microphone.soundPressure = float(self.sound_pressure)
    msg.microphone.soundPressureWeighted = float(self.sound_pressure_weighted)

    msg.microphone.soundPressureWeightedDb = float(self.sound_pressure_level_weighted)

    self.pm.send('microphone', msg)

    msg = messaging.new_message('microphoneRaw', valid=True)
    self.indata_ready_event.wait(.9)
    msg.microphoneRaw.rawSample =  np.int16(self.raw_sample * 32767).tobytes()
    msg.microphoneRaw.frameIndex = self.frame_index
    if not (self.frame_index_last == self.frame_index or
            self.frame_index - self.frame_index_last == SAMPLE_BUFFER):
      cloudlog.info(f'skipped {(self.frame_index - self.frame_index_last)//SAMPLE_BUFFER-1} samples')

    self.frame_index_last = self.frame_index
    self.pm.send('microphoneRaw', msg)
    self.indata_ready_event.clear()
    
  def callback(self, indata, frames, time, status):
    """
    Using amplitude measurements, calculate an uncalibrated sound pressure and sound pressure level.
    Then apply A-weighting to the raw amplitudes and run the same calculations again.

    Logged A-weighted equivalents are rough approximations of the human-perceived loudness.
    """

    self.measurements = np.concatenate((self.measurements, indata[:, 0]))

    while self.measurements.size >= FFT_SAMPLES:
      measurements = self.measurements[:FFT_SAMPLES]

      self.sound_pressure, _ = calculate_spl(measurements)
      measurements_weighted = apply_a_weighting(measurements)
      self.sound_pressure_weighted, self.sound_pressure_level_weighted = calculate_spl(measurements_weighted)

      self.measurements = self.measurements[FFT_SAMPLES:]
    
    self.frame_index += frames
    if self.listening_allowed:
      self.raw_sample = indata[:, 0].copy()
    self.indata_ready_event.set()

  @retry(attempts=7, delay=3)
  def get_stream(self, sd):
    # reload sounddevice to reinitialize portaudio
    sd._terminate()
    sd._initialize()
    return sd.InputStream(channels=1, samplerate=SAMPLE_RATE, callback=self.callback, blocksize=SAMPLE_BUFFER)

  def micd_thread(self):
    # sounddevice must be imported after forking processes
    import sounddevice as sd

    with self.get_stream(sd) as stream:
      cloudlog.info(f"micd stream started: {stream.samplerate=} {stream.channels=} {stream.dtype=} {stream.device=}, {stream.blocksize=}")
      while True:
        self.update()


def main():
  mic = Mic()
  mic.micd_thread()


if __name__ == "__main__":
  main()
