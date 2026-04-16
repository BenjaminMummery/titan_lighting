# code.py — Stage 1: White pulse → orange marker/strip (trail look, static)
#          Stage 2: Spin-up (slow) with trail
#          Stage 3: Spin-up (medium) with trail (longer ramp)
#          Stage 4: FAST accel to full speed → THEN slow ramp all LEDs orange + twinkle + trail
#          Stage 5: FINALE — amber/orange → white-hot peak → cooldown → fade to black
#                    + TRAIL-ONLY TAIL (keeps moving, then finally stops)
# FIX: Stage 5 no longer "stops then restarts" — fade keeps constant low spin,
#      tail is the ONLY place speed ramps down to 0.
# Adafruit PropMaker Feather RP2040 • EXTERNAL_POWER / EXTERNAL_NEOPIXELS / EXTERNAL_BUTTON

import math
import random
import time

import board
import digitalio
import neopixel

# -------------------------------------------------------------------------
# Hardware setup
# -------------------------------------------------------------------------
power = digitalio.DigitalInOut(board.EXTERNAL_POWER)
power.switch_to_output(value=True)

PIXEL_PIN = board.EXTERNAL_NEOPIXELS
LEDS_PER_STRIP = 70
NUM_STRIPS = 3
TOTAL_LEDS = LEDS_PER_STRIP * NUM_STRIPS

pixels = neopixel.NeoPixel(
    PIXEL_PIN,
    TOTAL_LEDS,
    brightness=1.0,
    auto_write=False,
)

button = digitalio.DigitalInOut(board.EXTERNAL_BUTTON)
button.switch_to_input(pull=digitalio.Pull.UP)

# -------------------------------------------------------------------------
# States
# -------------------------------------------------------------------------
IDLE = 0
STAGE1 = 1
STAGE2 = 2
STAGE3 = 3
STAGE4 = 4
STAGE5 = 5

# -------------------------------------------------------------------------
# Tuning
# -------------------------------------------------------------------------
FRAME_DELAY_S = 0.02

WHITE = (255, 255, 255)

# Stage 1: all LEDs pulse white up then down
WHITE_PULSE_DURATION_S = 2.2
WHITE_MAX = 0.90  # 0..1

# Orange / amber base (Stage 4 colour)
ORANGE = (255, 40, 0)

# Spin direction
DIRECTION = +1

# Trail (for stages 1/2/3/4/5)
TRAIL_LENGTH = 7
TRAIL_SHARPNESS = 1.6
TRAIL_GAIN = 0.55

# Stage 2 (slow)
STAGE2_RAMP_S = 4.0
STAGE2_START_SPEED = 0.0
STAGE2_TARGET_SPEED = 60.0

# Stage 3 (medium) — longer ramp so it doesn’t feel “done” too soon
STAGE3_RAMP_S = 5.0
STAGE3_START_SPEED = 60.0
STAGE3_TARGET_SPEED = 140.0

# Stage 4 (full)
FULL_SPEED = 250
STAGE4_ACCEL_S = 0.45
STAGE4_MIN_START_SPEED = 140

STAGE4_GLOW_DELAY_S = 1.0
STAGE4_GLOW_RAMP_S = 7.0
GLOW_MAX = 0.18

TWINKLE_RATE_MAX = 18
TWINKLE_GAIN_MIN = 0.08
TWINKLE_GAIN_MAX = 0.35

# ---------------- Stage 5: BUILD → WHITE-HOT PEAK → COOLDOWN → FADE → TRAIL TAIL ----------------
STAGE5_BLEND_S = 0.6

STAGE5_BUILD_S = 3.6
STAGE5_PEAK_S = 0.30
STAGE5_COOL_S = 7.0

# Low spin speed for the “dying coils” part
STAGE5_END_SPEED = 25.0

# Brightness envelope (white-hot)
STAGE5_BASE_MIN = 0.22
STAGE5_BASE_MAX = 1.00

# Shift towards white earlier & over longer window (smoother)
STAGE5_WHITE_SHIFT_START = 0.35
STAGE5_WHITE_SHIFT_END = 0.98

# Subtle "thrum" pulse (very gentle)
STAGE5_THRUM_HZ = 1.25
STAGE5_THRUM_DEPTH = 0.06

# Ember floor then fade to 0
STAGE5_EMBER_LEVEL = 0.04
STAGE5_FADEOUT_S = 4.0

# Extra “trail-only” spin time after base is black
STAGE5_TRAIL_TAIL_S = 2
STAGE5_TRAIL_ONLY_GAIN = 0.18

# Exponential feel controls
STAGE5_BUILD_EXP = 4.2
STAGE5_WHITE_EXP = 3.2


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------
def clear():
    pixels.fill((0, 0, 0))
    pixels.show()


def clamp01(x):
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else x


def lerp(a, b, t):
    t = clamp01(t)
    return a + (b - a) * t


def lerp_color(c1, c2, t):
    t = clamp01(t)
    return (
        int(lerp(c1[0], c2[0], t)),
        int(lerp(c1[1], c2[1], t)),
        int(lerp(c1[2], c2[2], t)),
    )


def scale_color(rgb, gain):
    gain = clamp01(gain)
    return (int(rgb[0] * gain), int(rgb[1] * gain), int(rgb[2] * gain))


def add_color(c1, c2):
    return (min(255, c1[0] + c2[0]), min(255, c1[1] + c2[1]), min(255, c1[2] + c2[2]))


def button_pressed(debounce_s=0.05, release_poll_s=0.01):
    if button.value:
        return False
    time.sleep(debounce_s)
    if button.value:
        return False
    while not button.value:
        time.sleep(release_poll_s)
    return True


def tri_pulse_0_1(t):
    t = clamp01(t)
    return 2.0 * t if t < 0.5 else 2.0 * (1.0 - t)


def ease_in_out_cubic(x):
    x = clamp01(x)
    return 4 * x**3 if x < 0.5 else 1 - pow(-2 * x + 2, 3) / 2


def ease_out_cubic(x):
    x = clamp01(x)
    return 1 - (1 - x) ** 3


def exp_ramp(x, exp):
    x = clamp01(x)
    return x**exp


def choose_locked_positions_even(pos):
    base = float(random.randint(0, LEDS_PER_STRIP - 1))
    step = LEDS_PER_STRIP / NUM_STRIPS
    for s in range(NUM_STRIPS):
        pos[s] = (base + step * s) % LEDS_PER_STRIP


def spin_step(dt, speed):
    for s in range(NUM_STRIPS):
        locked_pos[s] = (locked_pos[s] + DIRECTION * speed * dt) % LEDS_PER_STRIP


def draw_trail_for_strip(strip_index, head_pos, color):
    base = strip_index * LEDS_PER_STRIP
    head = int(head_pos) % LEDS_PER_STRIP

    pixels[base + head] = add_color(pixels[base + head], color)

    for t in range(1, TRAIL_LENGTH + 1):
        fade = (1.0 - (t / (TRAIL_LENGTH + 1))) ** TRAIL_SHARPNESS
        tail_gain = TRAIL_GAIN * fade
        c = scale_color(color, tail_gain)
        idx = (head - t) % LEDS_PER_STRIP
        pixels[base + idx] = add_color(pixels[base + idx], c)


def render_marker_with_trail(now, positions, base_fill=(0, 0, 0)):
    pixels.fill(base_fill)
    raw = (math.sin(2 * math.pi * 1.6 * now) + 1.0) / 2.0
    gain = 0.08 + (0.55 - 0.08) * (raw**1.6)
    marker_color = scale_color(ORANGE, gain)
    for s in range(NUM_STRIPS):
        draw_trail_for_strip(s, positions[s], marker_color)
    pixels.show()


def spin_update(now, ramp_s, start_speed, target_speed):
    global last_time, locked_ready, current_speed

    if not locked_ready:
        choose_locked_positions_even(locked_pos)
        locked_ready = True

    dt = now - last_time
    last_time = now

    elapsed = now - stage_start
    ramp = ease_in_out_cubic(elapsed / ramp_s)
    speed = start_speed + (target_speed - start_speed) * ramp
    current_speed = speed

    spin_step(dt, speed)
    render_marker_with_trail(now, locked_pos, base_fill=(0, 0, 0))


# -------------------------------------------------------------------------
# Stage 4
# -------------------------------------------------------------------------
stage4_start_speed = STAGE4_MIN_START_SPEED
stage4_last_glow_ramp = 0.0


def stage4_update(now):
    global last_time, locked_ready, current_speed, stage4_last_glow_ramp

    if not locked_ready:
        choose_locked_positions_even(locked_pos)
        locked_ready = True

    dt = now - last_time
    last_time = now
    elapsed = now - stage_start

    accel_ramp = ease_out_cubic(elapsed / STAGE4_ACCEL_S)
    speed = stage4_start_speed + (FULL_SPEED - stage4_start_speed) * accel_ramp
    current_speed = speed
    spin_step(dt, speed)

    glow_t = elapsed - (STAGE4_ACCEL_S + STAGE4_GLOW_DELAY_S)
    glow_ramp = ease_out_cubic(glow_t / STAGE4_GLOW_RAMP_S) if glow_t > 0 else 0.0
    stage4_last_glow_ramp = glow_ramp

    base_color = scale_color(ORANGE, GLOW_MAX * glow_ramp)
    pixels.fill(base_color)

    raw = (math.sin(2 * math.pi * 1.6 * now) + 1.0) / 2.0
    gain = 0.08 + (0.55 - 0.08) * (raw**1.6)
    marker_color = scale_color(ORANGE, gain)
    for s in range(NUM_STRIPS):
        draw_trail_for_strip(s, locked_pos[s], marker_color)

    twinkles_this_frame = int(TWINKLE_RATE_MAX * glow_ramp)
    for _ in range(twinkles_this_frame):
        idx = random.randint(0, TOTAL_LEDS - 1)
        tg = random.uniform(TWINKLE_GAIN_MIN, TWINKLE_GAIN_MAX) * glow_ramp
        pixels[idx] = add_color(pixels[idx], scale_color(ORANGE, tg))

    pixels.show()


# -------------------------------------------------------------------------
# Stage 5 (exponential build + fade + trail-only tail)
# -------------------------------------------------------------------------
stage5_start_speed = FULL_SPEED
stage5_start_glow_level = 0.0


def stage5_update(now):
    global last_time, locked_ready, current_speed, state

    if not locked_ready:
        choose_locked_positions_even(locked_pos)
        locked_ready = True

    dt = now - last_time
    last_time = now
    e = now - stage_start

    blend = ease_out_cubic(e / STAGE5_BLEND_S)

    t_build_end = STAGE5_BUILD_S
    t_peak_end = STAGE5_BUILD_S + STAGE5_PEAK_S
    t_cool_end = STAGE5_BUILD_S + STAGE5_PEAK_S + STAGE5_COOL_S
    t_fade_end = t_cool_end + STAGE5_FADEOUT_S
    t_tail_end = t_fade_end + STAGE5_TRAIL_TAIL_S

    base_level = stage5_start_glow_level
    speed = stage5_start_speed
    coil_rgb = ORANGE

    thrum = 1.0 + STAGE5_THRUM_DEPTH * math.sin(2 * math.pi * STAGE5_THRUM_HZ * now)

    trail_only = False

    if e < t_build_end:
        p = e / STAGE5_BUILD_S
        p_exp = exp_ramp(p, STAGE5_BUILD_EXP)

        env = STAGE5_BASE_MIN + (STAGE5_BASE_MAX - STAGE5_BASE_MIN) * p_exp
        base_level = env * thrum

        if p <= STAGE5_WHITE_SHIFT_START:
            wt = 0.0
        elif p >= STAGE5_WHITE_SHIFT_END:
            wt = 1.0
        else:
            wt = (p - STAGE5_WHITE_SHIFT_START) / (
                STAGE5_WHITE_SHIFT_END - STAGE5_WHITE_SHIFT_START
            )
        wt = exp_ramp(wt, STAGE5_WHITE_EXP)
        coil_rgb = lerp_color(ORANGE, WHITE, wt)

        speed = stage5_start_speed * (0.96 + 0.10 * p_exp)

    elif e < t_peak_end:
        q = (e - t_build_end) / STAGE5_PEAK_S
        q_e = ease_out_cubic(q)

        coil_rgb = WHITE
        base_level = STAGE5_BASE_MAX * (1.00 - 0.08 * q_e) * thrum
        speed = stage5_start_speed * (1.05 - 0.08 * q_e)

    elif e < t_cool_end:
        r = (e - t_peak_end) / STAGE5_COOL_S
        r_e = ease_out_cubic(r)

        coil_rgb = lerp_color(WHITE, ORANGE, r_e)

        max_cool_level = STAGE5_BASE_MAX * 0.85
        base_level = STAGE5_EMBER_LEVEL + (max_cool_level - STAGE5_EMBER_LEVEL) * (
            1.0 - r_e
        )
        base_level *= max(0.85, thrum)

        speed = stage5_start_speed + (STAGE5_END_SPEED - stage5_start_speed) * r_e

    elif e < t_fade_end:
        # FINAL FADE: base fades to 0, but spin stays constant (no stop-before-tail)
        f = (e - t_cool_end) / STAGE5_FADEOUT_S
        f_e = ease_out_cubic(f)

        coil_rgb = ORANGE
        base_level = STAGE5_EMBER_LEVEL * (1.0 - f_e)

        # <<< key fix: keep spinning at low speed during fade
        speed = STAGE5_END_SPEED

        thrum = 1.0

    elif e < t_tail_end:
        # TRAIL-ONLY TAIL: base is black, trail keeps moving then coasts to 0
        tt = (e - t_fade_end) / STAGE5_TRAIL_TAIL_S
        tt_e = ease_out_cubic(tt)

        coil_rgb = ORANGE
        base_level = 0.0
        speed = STAGE5_END_SPEED * (1.0 - tt_e)
        thrum = 1.0
        trail_only = True

    else:
        state = IDLE
        clear()
        return

    # Blend from Stage4 entry level -> Stage5 base (smooth handoff)
    base_level = (1.0 - blend) * stage5_start_glow_level + blend * base_level
    base_level = clamp01(base_level)

    current_speed = speed
    spin_step(dt, speed)

    pixels.fill(scale_color(coil_rgb, base_level))

    if trail_only:
        marker_gain = STAGE5_TRAIL_ONLY_GAIN
    else:
        marker_gain = clamp01(0.25 + 0.95 * (base_level / max(0.01, STAGE5_BASE_MAX)))

    marker = scale_color(coil_rgb, marker_gain)
    for s in range(NUM_STRIPS):
        draw_trail_for_strip(s, locked_pos[s], marker)

    pixels.show()


# -------------------------------------------------------------------------
# Runtime state
# -------------------------------------------------------------------------
state = IDLE
stage_start = time.monotonic()
last_time = time.monotonic()

locked_ready = False
locked_pos = [0.0, 0.0, 0.0]
current_speed = 0.0


# -------------------------------------------------------------------------
# Stage 1
# -------------------------------------------------------------------------
def stage1_update(now):
    global locked_ready, current_speed

    elapsed = now - stage_start
    if elapsed < WHITE_PULSE_DURATION_S:
        t = elapsed / WHITE_PULSE_DURATION_S
        pixels.fill(scale_color(WHITE, tri_pulse_0_1(t) * WHITE_MAX))
        pixels.show()
        return

    if not locked_ready:
        choose_locked_positions_even(locked_pos)
        locked_ready = True

    current_speed = 0.0
    render_marker_with_trail(now, locked_pos, base_fill=(0, 0, 0))


# -------------------------------------------------------------------------
# Main loop
# -------------------------------------------------------------------------
print("Boot OK — waiting for button")
clear()

while True:
    if button_pressed():
        state = (state + 1) % 6
        stage_start = time.monotonic()
        last_time = time.monotonic()
        print("State:", state)

        if state == STAGE1:
            locked_ready = False

        if state == STAGE4:
            stage4_start_speed = max(current_speed, STAGE4_MIN_START_SPEED)

        if state == STAGE5:
            stage5_start_speed = max(current_speed, FULL_SPEED)
            stage5_start_glow_level = GLOW_MAX * stage4_last_glow_ramp

        if state == IDLE:
            clear()

    now = time.monotonic()

    if state == IDLE:
        time.sleep(FRAME_DELAY_S)
        continue
    elif state == STAGE1:
        stage1_update(now)
    elif state == STAGE2:
        spin_update(now, STAGE2_RAMP_S, STAGE2_START_SPEED, STAGE2_TARGET_SPEED)
    elif state == STAGE3:
        spin_update(now, STAGE3_RAMP_S, STAGE3_START_SPEED, STAGE3_TARGET_SPEED)
    elif state == STAGE4:
        stage4_update(now)
    elif state == STAGE5:
        stage5_update(now)

    time.sleep(FRAME_DELAY_S)
