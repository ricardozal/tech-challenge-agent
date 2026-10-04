// Only place that reads the build environment (tests/architecture/test_web_boundaries.py).
export const AGENT_URL: string = import.meta.env.VITE_AGENT_URL ?? 'http://localhost:8001'
export const ACTIONS_URL: string = import.meta.env.VITE_ACTIONS_URL ?? 'http://localhost:8000'
