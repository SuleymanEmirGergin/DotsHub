# SDK 54 Smoke Test Checklist

Date: 2026-02-09
Target: `mobile` (Expo SDK 54)

## Automated checks (completed)

1. `npx expo-doctor` -> pass (`17/17 checks passed`)
2. `npx tsc --noEmit` -> pass
3. `CI=1 npx expo export --platform web` -> pass (`dist` exported)

## Manual smoke flow (Expo Go 54)

1. Start app with `npx expo start`.
Expected: Metro starts, QR is shown, app opens in Expo Go 54 without red screen.

2. Intro screen load.
Expected: Intro content renders, continue action moves into triage flow.

3. Headache happy path.
Input sequence:
- First message: `Bas agrim var`
- Question 1 answer: `Evet`
- Question 2 answer: `Evet`
Expected:
- Follow-up questions appear.
- Result screen opens with recommended specialty and urgency badge.

4. Summary screen + share.
Action: Tap `Doktora Gosterilecek Ozet`, then `Ozeti Paylas`.
Expected:
- Summary content renders (symptoms, Q/A history, disclaimer).
- Native share sheet opens without crash.

5. Emergency path.
Input: `Gogus agrisi var, nefes darligi ve terleme yasiyorum`
Expected:
- Emergency banner/instructions appear.
- Chat input is disabled in emergency state.

6. Restart flow.
Action: Tap `Yeni Analiz Baslat`.
Expected:
- Store resets and app returns to initial screen.

## Regression spot-checks

1. Router navigation between `/`, `/result`, `/summary` works.
2. Keyboard interaction in chat input works on device.
3. No layout break on narrow screens (small Android width).
