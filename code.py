import time

import board
import digitalio

from neopixel import NeoPixel
from utils.maths import clamp
from utils.maths import wrap
from utils.colour import WHITE, RED, ORANGE, GREEN, colour_at_brightness, add_colours
# --------------------------------------------------------------------------------------
# Adjustable Parameters
# --------------------------------------------------------------------------------------

# LEDs
N_LEDS_PER_STRIP: int = 165
N_STRIPS: int = 1
BRIGHTNESS: float = 0.1
FPS: float = 50

# EFFECTS
TAIL_LENGTH: int = 5


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
pixels.brightness = BRIGHTNESS

# --------------------------------------------------------------------------------------
# Indicator LED Setup
# --------------------------------------------------------------------------------------

indicator = NeoPixel(board.NEOPIXEL, 1)
indicator.brightness = 0.1

# --------------------------------------------------------------------------------------
# Light Patterns
# --------------------------------------------------------------------------------------

def pulse(time: float) -> float:
    time = clamp(time)
    return 2.0 * time if time < 0.5 else 2.0 * (1.0 - time)

def spin_reactor(t_now: Seconds):
    global reactor_positions, time_of_last_update

    # Update reactor position
    d_t: Seconds = t_now - time_of_last_update
    d_rev = (reactor_rpm / 60) * d_t
    reactor_positions = [wrap(pos + d_rev, 0, ) for pos in reactor_positions]

    # Identify head pixels
    i_head_pixels = [int(N_LEDS_PER_STRIP*pos) for pos in reactor_positions]

    # Update the pixels
    pixels.fill((0,0,0))
    for i_head_pixel in i_head_pixels:
        pixels[i_head_pixel] = WHITE
        for i_tail_pixel in range(1, TAIL_LENGTH+1):
            tail_brightness = (1.0 - (i_tail_pixel) / (TAIL_LENGTH+1)) ** 1.6
            pixels[wrap(i_head_pixel-i_tail_pixel, 0, N_LEDS_TOTAL)] = colour_at_brightness(ORANGE, tail_brightness)

    time_of_last_update = t_now
    pixels.show()


# --------------------------------------------------------------------------------------
# States Setup
# --------------------------------------------------------------------------------------

# Human-readable state names
state_names: dict[int, str] = {
    (STATE_OFF := 0): "OFF",
    (STATE_IGNITION := 1): "IGNITION",
    (STATE_IDLE := 2): "IDLE",
}

# Time to spend in each state
state_timeout: dict[int, float|None] = {
    STATE_OFF: 1,
    STATE_IGNITION: 2.2,
    STATE_IDLE: None,
}

# State indicator colours
state_indicator_colours: dict[int, tuple[int,int,int]] = {
    STATE_OFF: RED,
    STATE_IGNITION: ORANGE,
    STATE_IDLE: GREEN,
}


N_STATES: int = len(state_names)

# IGNITION
def ignition_update(t_now: Seconds, t_stage_start: Seconds):
    t_in_stage = t_now - t_stage_start
    if t_in_stage > state_timeout[STATE_IGNITION]:
        raise RuntimeError(f"State IGNITION is supposed to last for {state_timeout[STATE_IGNITION]}s but {t_in_stage}s have elapsed.")
    pixels.fill(colour_at_brightness(WHITE, pulse(t_in_stage / state_timeout[STATE_IGNITION])))
    pixels.show()
    return
    
# IDLE
def idle_update(t_now: Seconds, t_stage_start: float):
    global reactor_rpm
    reactor_rpm = 60
    spin_reactor(t_now)
    return


# --------------------------------------------------------------------------------------
# Initial State
# --------------------------------------------------------------------------------------

Seconds = float
time_of_stage_start: Seconds = time.monotonic()
time_of_last_update: Seconds = time.monotonic()
reactor_positions: list[float] = [0.0 for _ in range(N_STRIPS)]
reactor_rpm: float = 0
state: int = 0


# --------------------------------------------------------------------------------------
# Main Loop
# --------------------------------------------------------------------------------------

def change_state(new_state: int):
    global state, time_of_stage_start
    state=new_state
    time_of_stage_start = time.monotonic()
    indicator.fill(state_indicator_colours[state])
    print(f"STATUS: {state_names[state]}")

change_state(0)

while True:
    time_now: float = time.monotonic()

    # Change state
    if state_timeout[state] is not None:
        if time_now - time_of_stage_start >= state_timeout[state]:
            change_state((state + 1) % N_STATES)

    # Call the appropriate updater for the current stage
    if state == STATE_OFF:
        pixels.fill((0, 0, 0))
        pixels.show()
    elif state == STATE_IGNITION:
        ignition_update(time_now, time_of_stage_start)
    elif state == STATE_IDLE:
        idle_update(time_now, time_of_stage_start)
    else:
        raise NotImplementedError("")

    time.sleep(1.0/FPS)
