/**
 * CareOn Citizen — PWA Lifecycle & Push Service
 */

let deferredPrompt = null;
const installListeners = new Set();

export function initPWA(onUpdateAvailable) {
  if (typeof window === 'undefined') return;

  // 1. Capture beforeinstallprompt for Microsoft PWA Builder and Chromium browsers
  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredPrompt = e;
    notifyInstallListeners(true);
  });

  window.addEventListener('appinstalled', () => {
    deferredPrompt = null;
    notifyInstallListeners(false);
    console.log('CareOn Citizen was successfully installed.');
  });

  // 2. Register Service Worker
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker
        .register('/sw.js')
        .then((registration) => {
          console.log('CareOn ServiceWorker registered with scope:', registration.scope);

          // Check for worker updates
          registration.addEventListener('updatefound', () => {
            const installingWorker = registration.installing;
            if (!installingWorker) return;
            installingWorker.addEventListener('statechange', () => {
              if (installingWorker.state === 'installed' && navigator.serviceWorker.controller) {
                console.log('New CareOn Citizen update available.');
                if (onUpdateAvailable) onUpdateAvailable();
              }
            });
          });
        })
        .catch((err) => {
          console.warn('ServiceWorker registration skipped or failed:', err);
        });
    });
  }
}

function notifyInstallListeners(canInstall) {
  installListeners.forEach((listener) => listener(canInstall));
}

export function subscribeInstallState(callback) {
  installListeners.add(callback);
  callback(Boolean(deferredPrompt));
  return () => installListeners.delete(callback);
}

export async function promptInstall() {
  if (!deferredPrompt) {
    return { outcome: 'unavailable' };
  }
  deferredPrompt.prompt();
  const { outcome } = await deferredPrompt.userChoice;
  deferredPrompt = null;
  notifyInstallListeners(false);
  return { outcome };
}

export function isStandalone() {
  if (typeof window === 'undefined') return false;
  return (
    window.matchMedia('(display-mode: standalone)').matches ||
    window.navigator.standalone === true
  );
}

export async function requestPushPermission() {
  if (!('Notification' in window)) {
    return { supported: false, permission: 'unsupported' };
  }
  const permission = await Notification.requestPermission();
  return { supported: true, permission };
}
