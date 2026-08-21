import '@testing-library/jest-dom';

// Mock Three.js for tests
jest.mock('three', () => ({
  Scene: jest.fn(),
  PerspectiveCamera: jest.fn(),
  WebGLRenderer: jest.fn(() => ({
    setSize: jest.fn(),
    setPixelRatio: jest.fn(),
    render: jest.fn(),
    dispose: jest.fn(),
    domElement: document.createElement('canvas'),
  })),
  OrbitControls: jest.fn(),
  HemisphereLight: jest.fn(),
  DirectionalLight: jest.fn(),
  Fog: jest.fn(),
  Group: jest.fn(),
  Mesh: jest.fn(),
  BufferGeometry: jest.fn(),
  BufferAttribute: jest.fn(),
  Line: jest.fn(),
  Points: jest.fn(),
  PointsMaterial: jest.fn(),
  LineBasicMaterial: jest.fn(),
  MeshPhongMaterial: jest.fn(),
  PlaneGeometry: jest.fn(),
  ConeGeometry: jest.fn(),
  BoxGeometry: jest.fn(),
  SphereGeometry: jest.fn(),
  RingGeometry: jest.fn(),
  Color: jest.fn(),
  MathUtils: {
    degToRad: jest.fn((deg) => deg * (Math.PI / 180)),
  },
  TOUCH: {
    ROTATE: 'rotate',
    DOLLY_PAN: 'dolly-pan',
  },
}));

// Mock ResizeObserver
global.ResizeObserver = jest.fn(() => ({
  observe: jest.fn(),
  unobserve: jest.fn(),
  disconnect: jest.fn(),
}));

// Mock requestAnimationFrame
global.requestAnimationFrame = jest.fn((cb) => setTimeout(cb, 16));
global.cancelAnimationFrame = jest.fn();
