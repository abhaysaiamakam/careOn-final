import '@testing-library/jest-dom';

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

  // Mock WebSocket
  window.WebSocket = class MockWebSocket {
    constructor(url) {
      this.url = url;
      this.readyState = 1; // OPEN
      setTimeout(() => {
        if (this.onopen) this.onopen({ type: 'open' });
      }, 10);
    }
    send() {}
    close() {
      this.readyState = 3;
      if (this.onclose) this.onclose({ type: 'close' });
    }
  };
}

global.localStorage = mockStorage;
