import sys
import os

sys.path.insert(0, "/system/apps/desk")
os.chdir("/system/apps/desk")

from badgeware import screen, Image, PixelFont, io, brushes, shapes, run, display
import machine

# -- Constants --
TIMEOUT_MS = 5 * 60 * 1000  # 5 minutes in milliseconds
BACKLIGHT_ON = 1.0
BACKLIGHT_OFF = 0.0
IMAGE_PATH = "assets/image.png"

# -- Pre-created brushes (avoid per-frame allocations) --
BLACK = brushes.color(0, 0, 0)
ERROR_RED = brushes.color(255, 100, 100)
ERROR_GRAY = brushes.color(180, 180, 180)

# -- VBUS detection setup --
# On the Tufty 2350, VBUS detect is GPIO12 (Pin.board.VBUS_DETECT),
# NOT GPIO24 (which is used by the CYW43 WiFi chip).
vbus_pin = None
try:
    vbus_pin = machine.Pin(machine.Pin.board.VBUS_DETECT, machine.Pin.IN)
except (AttributeError, TypeError):
    try:
        vbus_pin = machine.Pin(12, machine.Pin.IN)
    except Exception:
        pass


def _has_usb_power():
    """Return True if USB power (VBUS) is present."""
    if vbus_pin is not None:
        return vbus_pin.value() == 1
    # Last-resort fallback: use is_charging (may miss full-battery-on-USB)
    try:
        from badgeware import is_charging
        return is_charging()
    except ImportError:
        return True


# -- State --
screen_on = True
usb_absent_ms = 0  # Accumulated ms without USB (wrap-safe via ticks_delta)
initialized = False

# -- Load resources --
screen.font = PixelFont.load("/system/assets/fonts/nope.ppf")

image = None
error = None
try:
    image = Image.load(IMAGE_PATH)
except Exception as e:
    error = str(e)


def _set_backlight(level):
    """Set display backlight. level: 0.0 (off) to 1.0 (full)."""
    display.backlight(level)


def init():
    global screen_on, usb_absent_ms, initialized
    initialized = True
    screen_on = True
    usb_absent_ms = 0
    _set_backlight(BACKLIGHT_ON)


def update():
    global screen_on, usb_absent_ms, initialized

    # Handle case where init() was not called
    if not initialized:
        init()

    usb_present = _has_usb_power()

    if usb_present:
        usb_absent_ms = 0
        if not screen_on:
            screen_on = True
            _set_backlight(BACKLIGHT_ON)
    else:
        # Accumulate time without USB using ticks_delta (wrap-safe)
        usb_absent_ms += io.ticks_delta
        if screen_on and usb_absent_ms >= TIMEOUT_MS:
            screen_on = False
            _set_backlight(BACKLIGHT_OFF)

    # Skip rendering when screen is off (saves CPU)
    if not screen_on:
        return

    screen.brush = BLACK
    screen.clear()

    if image is not None:
        x = max(0, (160 - image.width) // 2)
        y = max(0, (120 - image.height) // 2)
        screen.blit(image, x, y)
    elif error:
        screen.brush = ERROR_RED
        screen.text("No image found", 10, 50)
        screen.brush = ERROR_GRAY
        screen.text("Add image.png to", 10, 65)
        screen.text("apps/desk/assets/", 10, 77)


def on_exit():
    _set_backlight(BACKLIGHT_ON)


if __name__ == "__main__":
    run(update)
