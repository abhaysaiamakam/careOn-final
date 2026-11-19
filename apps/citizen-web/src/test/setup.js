import '@testing-library/jest-dom';

// Ensure localStorage mock is present in node test environment
if (typeof window !== 'undefined' && (!window.localStorage || !window.localStorage.clear)) {
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
  Object.defineProperty(window, 'localStorage', {
    value: mockStorage,
    writable: true,
  });
  global.localStorage = mockStorage;
}
