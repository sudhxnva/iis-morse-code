import queue

import numpy as np

CLAP_BANDS = ((1_000, 2_000), (2_000, 4_000), (4_000, 8_000))
SAMPLE_RATE = 48_000
BLOCK_SIZE = 4096
INPUT_DEVICE = None
CLAP_THRESHOLD = -70


def compute_spectrum(samples, sample_rate):
    samples = samples - np.mean(samples)
    window = np.hanning(len(samples))
    spectrum = np.fft.rfft(samples * window)
    frequencies = np.fft.rfftfreq(len(samples), 1 / sample_rate)
    magnitudes = np.abs(spectrum) / np.sum(window)
    return frequencies, 20 * np.log10(np.maximum(magnitudes, 1e-10))


def band_energy(frequencies, magnitudes, low_frequency, high_frequency):
    band = (frequencies >= low_frequency) & (frequencies < high_frequency)
    return np.mean(magnitudes[band])


def detect_clap(frequencies, magnitudes, threshold):
    energies = [band_energy(frequencies, magnitudes, *band) for band in CLAP_BANDS]
    energy = np.mean(energies)
    return energy > threshold, energy


def classify_block(samples, sample_rate, threshold):
    frequencies, magnitudes = compute_spectrum(samples, sample_rate)
    detected, energy = detect_clap(frequencies, magnitudes, threshold)
    return frequencies, magnitudes, detected, energy


def state_label(detected):
    return "Clap" if detected else "No Interaction"


def run_detector():
    try:
        import matplotlib.pyplot as plt
        from matplotlib.animation import FuncAnimation
        import sounddevice as sd
    except ImportError:
        print("Install dependencies first: python3 -m pip install -r requirements.txt")
        return

    audio_queue = queue.Queue(maxsize=10)

    def callback(indata, frames, time_info, status):
        if status:
            print(status)
        try:
            audio_queue.put_nowait(indata[:, 0].copy())
        except queue.Full:
            audio_queue.get_nowait()
            audio_queue.put_nowait(indata[:, 0].copy())

    fig, ax = plt.subplots(figsize=(11, 6))
    frequencies = np.fft.rfftfreq(BLOCK_SIZE, 1 / SAMPLE_RATE)
    line, = ax.plot(frequencies, np.full(len(frequencies), -100.0))
    label = ax.text(0.02, 0.95, "No Interaction", transform=ax.transAxes,
                    va="top", fontsize=14)
    energy_text = ax.text(0.02, 0.87, "Band energy: -- dB", transform=ax.transAxes,
                          va="top")

    ax.set_title("Clap Detector")
    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel("Amplitude (dB)")
    ax.set_xlim(0, 10_000)
    ax.set_ylim(-100, 0)
    ax.grid(alpha=0.3)

    def update(_frame):
        latest_block = None
        while True:
            try:
                latest_block = audio_queue.get_nowait()
            except queue.Empty:
                break

        if latest_block is not None:
            frequencies, magnitudes, detected, energy = classify_block(
                latest_block, SAMPLE_RATE, CLAP_THRESHOLD
            )
            line.set_data(frequencies, magnitudes)
            label.set_text(state_label(detected))
            energy_text.set_text(f"Band energy: {energy:.1f} dB")

        return line, label, energy_text

    print(sd.query_devices())
    print("Close the plot window or press Ctrl+C to stop.")
    stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        blocksize=BLOCK_SIZE,
        channels=1,
        device=INPUT_DEVICE,
        callback=callback,
    )

    with stream:
        animation = FuncAnimation(fig, update, interval=50, blit=True,
                                  cache_frame_data=False)
        plt.show()


if __name__ == "__main__":
    run_detector()
