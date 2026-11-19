import '@testing-library/jest-dom';

// Ensure localStorage mock is present in node test environment
let store = {};
const mockStorage = {
  getItem: (key) => store[key] || null,
  setItem: (key, value) => {
    store[key] = String(value);
  },
  removeItem: (key) => {
    delete store[key];
  },
  clear: () => {
    store = {};
  },
};

if (typeof window !== 'undefined') {
  Object.defineProperty(window, 'localStorage', {
    value: mockStorage,
    writable: true,
  });
}
global.localStorage = mockStorage;

// Mock matchMedia
if (typeof window !== 'undefined') {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: (query) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }),
  });

  // Mock AudioContext
  window.AudioContext = class {
    createOscillator() {
      return {
        type: 'sine',
        frequency: { setValueAtTime: () => {} },
        connect: () => {},
        start: () => {},
        stop: () => {},
      };
    }
    createGain() {
      return {
        gain: {
          setValueAtTime: () => {},
          exponentialRampToValueAtTime: () => {},
        },
        connect: () => {},
      };
    }
    get currentTime() {
      return 0;
    }
    get destination() {
      return {};
    }
  };

  // Mock Geolocation
  navigator.geolocation = {
    watchPosition: (success) => {
      success({
        coords: {
          latitude: 12.9716,
          longitude: 77.5946,
          accuracy: 10,
          heading: 90,
          speed: 15,
        },
        timestamp: Date.now(),
      });
      return 1;
    },
    clearWatch: () => {},
    getCurrentPosition: (success) => {
      success({
        coords: {
          latitude: 12.9716,
          longitude: 77.5946,
          accuracy: 10,
          heading: 90,
          speed: 15,
        },
        timestamp: Date.now(),
      });
    },
  };
}
