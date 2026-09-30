# Tap Morse

A small Morse-code experiment that listens to taps on a laptop body. One tap
becomes a dot and a quick double tap becomes a dash. After a short pause, the
app resolves the current Morse sequence and writes the letter on screen.

## Setup

You will need Python 3 and a laptop microphone.

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Start the app from the repository root:

```sh
.venv/bin/python morse_app.py
```

macOS may ask for microphone access for the terminal application. Allow it in
**System Settings → Privacy & Security → Microphone**, then restart the app.

## Controls

| Input | Result |
| ----- | ------ |
| Single tap | Dot (`.`) |
| Quick double tap | Dash (`-`) |
| Brief pause | Resolve the current letter |
| Clear button | Clear the screen |

The app waits briefly before showing a single tap so it has time to check for a
second tap. It does not add word spaces automatically.

## Tuning

The settings near the top of `morse_app.py` are the useful ones to adjust:

- `TAP_THRESHOLD` controls how loud a tap must be.
- `DOUBLE_TAP_SECONDS` controls how close two taps need to be for a dash.
- `LETTER_PAUSE_SECONDS` controls when a Morse sequence becomes a letter.

The current setup uses 1–8 kHz tap energy and short 1,024-sample audio blocks
to make double taps easier to recognize.

## Tests

```sh
.venv/bin/python -m unittest -v
```

## AI Usage

I used an AI coding assistant to help debug the tap timing and clean up this
README.
