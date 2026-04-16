import time

import board
import digitalio

from neopixel import NeoPixel

# --------------------------------------------------------------------------------------
# Adjustable Parameters
# --------------------------------------------------------------------------------------

# LEDs
N_LEDS_PER_STRIP: int = 215
N_STRIPS: int = 1
BRIGHTNESS: float = 1.0
FRAME_DELAY_SECONDS: float = 0.02

# Initial state
state: int = 0

# Ignition


# --------------------------------------------------------------------------------------
# Board Setup
# --------------------------------------------------------------------------------------

power: digitalio.DigitalInOut = digitalio.DigitalInOut(board.EXTERNAL_POWER)
power.switch_to_output(value=True)

# --------------------------------------------------------------------------------------
# Button Setup
# --------------------------------------------------------------------------------------

button = digitalio.DigitalInOut(board.EXTERNAL_BUTTON)
button.switch_to_input(pull=digitalio.Pull.UP)

# --------------------------------------------------------------------------------------
# Lightstrip Setup
# --------------------------------------------------------------------------------------

pixels = NeoPixel(
    pin=board.EXTERNAL_NEOPIXELS,
    n=(N_LEDS_TOTAL := N_LEDS_PER_STRIP * N_STRIPS),
    auto_write=False,
)

# --------------------------------------------------------------------------------------
# Colours Setup
# --------------------------------------------------------------------------------------

WHITE = (255, 255, 255)
ORANGE = (255, 40, 0)

# --------------------------------------------------------------------------------------
# States Setup
# --------------------------------------------------------------------------------------


state_names: dict[int, str] = {
    (STATE_OFF := 0): "OFF",
    (STATE_IDLE := 1): "IDLE",
}

N_STATES: int = len(state_names)

# Time to spend in each state
state_timing: dict[int, int] = {
    STATE_OFF: 1,
    STATE_IDLE: 5,
}


# --------------------------------------------------------------------------------------
# Main Loop
# --------------------------------------------------------------------------------------

t_start: float = time.monotonic()
while True:
    now: float = time.monotonic()

    # Change state
    if now - t_start >= state_timing[state]:
        state = (state + 1) % N_STATES
        t_start = time.monotonic()
        print(f"STATUS: {state_names[state]}")

    # Call the appropriate updater for the current stage
    match state:
        case STATE_OFF:
            pixels.fill((0, 0, 0))
            pixels.show()
        case _:
            raise NotImplementedError(f"State: {state}")

    time.sleep(FRAME_DELAY_SECONDS)
