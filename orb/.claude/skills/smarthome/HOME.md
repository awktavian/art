# Home Reference

**7331 W Green Lake Dr N, Seattle, WA 98103**
The Crescent Collection — Farmhouse Elevation
3 floors, 26 rooms

Tim built this home with intention — walnut and white, navy blue, quality that lasts.

Jill arrives mornings for runs around Green Lake, arms outstretched, ready.

See `.cursor/rules/home-layout.mdc` for full floor plan and device IDs.

## Quick Summary

| Floor | Rooms |
|-------|-------|
| Second | Primary Suite, Office, Bed 3, Loft, Laundry |
| First | Living Room, Kitchen, Dining, Entry, Mudroom |
| Basement | Game Room, Bed 4, Gym, Rack Room |

## Device Counts

| Category | Count |
|----------|-------|
| Lights | 41 |
| Shades | 11 |
| Locks | 2 |
| Audio zones | 26 |

## Key Rooms

**Living Room** - TV (MantelMount), Fireplace, Denon Atmos, Shades E+S
**Kitchen** - Sub-Zero Wolf, 4 lighting zones
**Primary Bed** - Eight Sleep, Shades N+W
**Office** - 20A circuit

## Common Commands

```python
# Living Room setup
await controller.set_lights(0, rooms=["Living Room"])
await controller.close_shades(rooms=["Living Room"])
await controller.lower_tv(1)
await controller._control4.fireplace_on()

# Kitchen
await controller.set_lights(100, rooms=["Kitchen"])

# Goodnight (all off, lock up)
await controller.goodnight()
```
