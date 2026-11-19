# CareOn Citizen — Microsoft PWA Builder & Packaging Guide

This guide details how to validate, package, and distribute the **CareOn Citizen** Progressive Web Application using **Microsoft PWA Builder** (https://pwabuilder.com) for Google Play (Android), Microsoft Store (Windows), and Apple iOS.

---

## 1. PWA Builder Verification Audit

CareOn Citizen meets all PWA Builder criteria:

| PWA Criteria | Status | Implementation Details |
| :--- | :--- | :--- |
| **Web App Manifest** | **PASS** | Valid `manifest.webmanifest` & `manifest.json` located at `/` with `name`, `short_name`, `start_url`, `display: standalone`, `theme_color: #D92D3A`, `background_color: #FFFFFF`. |
| **Icons & Maskable** | **PASS** | PNG icons: `icon-192.png` (192×192), `icon-512.png` (512×512), `icon-maskable.png` (512×512 maskable with safe zone), `apple-touch-icon.png` (180×180). |
| **Service Worker** | **PASS** | Production service worker `sw.js` with static precaching, cache invalidation, update detection (`skipWaiting`), and offline fallback. |
| **Offline Support** | **PASS** | Complete offline navigation handling via `/offline.html` and local draft management without false transmission promises. |
| **Security & HTTPS** | **PASS** | Strict exclusion of private `/api/` emergency data from service worker disk caching; secure token handling in web storage. |

---

## 2. Packaging Workflow Using PWA Builder

### Step 1: Deploy to HTTPS
Deploy `apps/citizen-web/dist` to an HTTPS origin (e.g. `https://citizen.careon.org` or Cloudflare Pages / Vercel / Nginx).

### Step 2: Run PWA Builder Audit
1. Navigate to [pwabuilder.com](https://www.pwabuilder.com).
2. Enter your deployed URL: `https://citizen.careon.org`.
3. Verify that all 3 sections (**Manifest**, **Service Worker**, **Security**) achieve a **Green Score (100/100)**.

### Step 3: Generate Platform Packages

#### A. Android (Google Play Store — Trusted Web Activity)
1. In PWA Builder, click **Package for Android**.
2. Provide Android package options:
   - **Package ID:** `org.careon.citizen`
   - **App Name:** `CareOn Citizen`
   - **Launcher Name:** `CareOn`
   - **Theme / Nav Bar Color:** `#D92D3A`
   - **Signing Key:** Generate a new key or use an existing Google Play Upload Key.
3. Download the generated `.zip` containing:
   - `app-release.aab` (Android App Bundle for Google Play Console upload)
   - `assetlinks.json` (Place at `https://citizen.careon.org/.well-known/assetlinks.json` for Digital Asset Links domain verification)

#### B. Windows (Microsoft Store — MSIX)
1. Click **Package for Windows**.
2. Enter Windows publisher details and Publisher Display Name (`CareOn Emergency Operating System`).
3. Download the signed `.msix` package ready for submission to Partner Center.

#### C. Apple iOS & iPadOS
- **Direct PWA Installation:** On iOS Safari, tap **Share** -> **Add to Home Screen**. The app launches in full-screen standalone mode with splash screen and badge support.
- **App Store WebKit Wrapper:** Click **Package for iOS** to download an Xcode project container with WKWebView configured for App Store distribution.

---

## 3. Platform-Specific Limitations & Guidelines

### Geolocation
- **Foreground:** High-precision GPS acquisition is supported across all platforms with user permission.
- **Background Execution:** PWAs cannot maintain continuous background GPS tracking when the screen is locked or browser is backgrounded. CareOn Citizen explicitly acquires location in foreground when filing the report.

### Push Notifications
- **Android & Desktop (Chrome/Edge):** Fully supported via standard Web Push API (`PushManager` & service worker `push` event).
- **iOS (Safari 16.4+):** Supported *only* after the user adds the PWA to their Home Screen and grants permission. Standard Safari browser tabs do not fire web push.

### Offline Drafts
- Stored emergency drafts remain strictly local to device storage (`localStorage` / IndexedDB).
- Drafts older than 24 hours are marked stale.
- The app strictly prevents automated silent submissions: the citizen must review and confirm transmission once internet connectivity returns.
