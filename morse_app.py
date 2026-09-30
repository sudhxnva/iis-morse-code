import queue

import numpy as np

LETTER_PAUSE_SECONDS = 0.75
DOUBLE_TAP_SECONDS = 0.3
TAP_DEBOUNCE_SECONDS = 0.08
MORSE_BLOCK_SIZE = 1024
SAMPLE_RATE = 48_000
INPUT_DEVICE = None
TAP_THRESHOLD = -95
TAP_BANDS = ((1_000, 2_000), (2_000, 4_000), (4_000, 8_000))

MORSE_CODE = {
    ".-": "A", "-...": "B", "-.-.": "C", "-..": "D", ".": "E",
    "..-.": "F", "--.": "G", "....": "H", "..": "I", ".---": "J",
    "-.-": "K", ".-..": "L", "--": "M", "-.": "N", "---": "O",
    ".--.": "P", "--.-": "Q", ".-.": "R", "...": "S", "-": "T",
    "..-": "U", "...-": "V", ".--": "W", "-..-": "X", "-.--": "Y",
    "--..": "Z",
}


class MorseWriter:
    def __init__(self):
        self.cells = []
        self.current_sequence = ""

    def add_symbol(self, symbol):
        self.current_sequence += symbol

    def resolve_letter(self):
        if not self.current_sequence:
            return
        letter = MORSE_CODE.get(self.current_sequence, "?")
        self.cells.append((letter, self.current_sequence))
        self.current_sequence = ""

    def clear(self):
        self.cells = []
        self.current_sequence = ""


class TapDecoder:
    def __init__(self, double_tap_seconds=DOUBLE_TAP_SECONDS):
        self.double_tap_seconds = double_tap_seconds
        self.pending_tap_time = None

    def add_tap(self, timestamp):
        if self.pending_tap_time is None:
            self.pending_tap_time = timestamp
            return []
        if timestamp - self.pending_tap_time <= self.double_tap_seconds:
            self.pending_tap_time = None
            return [("-", timestamp)]

        result = [(".", self.pending_tap_time)]
        self.pending_tap_time = timestamp
        return result

    def flush(self, timestamp):
        if self.pending_tap_time is None:
            return []
        if timestamp - self.pending_tap_time < self.double_tap_seconds:
            return []

        result = [(".", self.pending_tap_time)]
        self.pending_tap_time = None
        return result


def tap_detected(samples):
    samples = samples - np.mean(samples)
    window = np.hanning(len(samples))
    spectrum = np.fft.rfft(samples * window)
    frequencies = np.fft.rfftfreq(len(samples), 1 / SAMPLE_RATE)
    magnitudes = 20 * np.log10(np.maximum(np.abs(spectrum) / np.sum(window), 1e-10))
    energy = np.mean([
        np.mean(magnitudes[(frequencies >= low) & (frequencies < high)])
        for low, high in TAP_BANDS
    ])
    return energy > TAP_THRESHOLD


def run_morse_app():
    try:
        import matplotlib.pyplot as plt
        from matplotlib.animation import FuncAnimation
        from matplotlib.widgets import Button
        import sounddevice as sd
    except ImportError:
        print("Install dependencies first: python3 -m pip install -r requirements.txt")
        return

    writer = MorseWriter()
    decoder = TapDecoder()
    audio_queue = queue.Queue(maxsize=10)
    listening = False
    last_symbol_time = None
    last_detected_time = float("-inf")
    tap_armed = True

    def callback(indata, frames, time_info, status):
        if status:
            print(status)
        try:
            audio_queue.put_nowait((time_info.inputBufferAdcTime, indata[:, 0].copy()))
        except queue.Full:
            audio_queue.get_nowait()
            audio_queue.put_nowait((time_info.inputBufferAdcTime, indata[:, 0].copy()))

    fig, ax = plt.subplots(figsize=(11, 6))
    fig.subplots_adjust(top=0.78)
    status = fig.text(0.05, 0.84, "Press Start to begin", color="dimgray")

    def redraw():
        ax.clear()
        ax.set_axis_off()
        x, y = 0.05, 0.82
        cells = writer.cells + [("?", writer.current_sequence)]
        for letter, symbols in cells:
            width = max(0.06, 0.025 * len(symbols) + 0.03)
            if x + width > 0.94:
                x, y = 0.05, y - 0.2
            ax.text(x + width / 2, y, letter, ha="center", va="center",
                    fontsize=20, family="monospace")
            ax.text(x + width / 2, y - 0.08, symbols, ha="center", va="center",
                    fontsize=13, color="dimgray", family="monospace")
            x += width + 0.025
        fig.canvas.draw_idle()

    def start(_event):
        nonlocal listening
        listening = True
        status.set_text("Listening: tap = dot · quick double tap = dash")

    def clear(_event):
        nonlocal decoder, last_symbol_time
        writer.clear()
        decoder = TapDecoder()
        last_symbol_time = None
        redraw()

    start_ax = fig.add_axes([0.72, 0.86, 0.1, 0.06])
    clear_ax = fig.add_axes([0.83, 0.86, 0.1, 0.06])
    start_button = Button(start_ax, "Start")
    clear_button = Button(clear_ax, "Clear")
    start_button.on_clicked(start)
    clear_button.on_clicked(clear)

    def update(_frame):
        nonlocal last_detected_time, last_symbol_time, tap_armed
        blocks = []
        while True:
            try:
                blocks.append(audio_queue.get_nowait())
            except queue.Empty:
                break

        latest_audio_time = None

        def add_symbols(symbols):
            nonlocal last_symbol_time
            for symbol, symbol_time in symbols:
                writer.add_symbol(symbol)
                last_symbol_time = symbol_time
            if symbols:
                redraw()

        if listening:
            for block_time, block in blocks:
                latest_audio_time = block_time
                if not tap_detected(block):
                    tap_armed = True
                    continue
                if not tap_armed or block_time - last_detected_time < TAP_DEBOUNCE_SECONDS:
                    continue
                tap_armed = False
                last_detected_time = block_time
                add_symbols(decoder.add_tap(block_time))

            if latest_audio_time is not None:
                add_symbols(decoder.flush(latest_audio_time))

        if (
            listening
            and writer.current_sequence
            and decoder.pending_tap_time is None
            and last_symbol_time is not None
            and latest_audio_time is not None
            and latest_audio_time - last_symbol_time >= LETTER_PAUSE_SECONDS
        ):
            writer.resolve_letter()
            last_symbol_time = None
            redraw()

        return ()

    redraw()
    stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        blocksize=MORSE_BLOCK_SIZE,
        channels=1,
        device=INPUT_DEVICE,
        callback=callback,
    )
    with stream:
        animation = FuncAnimation(fig, update, interval=50, cache_frame_data=False)
        plt.show()


if __name__ == "__main__":
    run_morse_app()
