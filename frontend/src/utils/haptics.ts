/**
 * Lightweight haptic feedback using the Vibration API.
 * No-ops silently on devices/browsers that don't support it.
 */

export function hapticLight() {
  navigator.vibrate?.(10);
}

export function hapticMedium() {
  navigator.vibrate?.(20);
}

export function hapticHeavy() {
  navigator.vibrate?.([30, 10, 30]);
}
