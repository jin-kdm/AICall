import type {
  AudioGenerationResult,
  ApiNode,
  ApiEdge,
  Scenario,
  ScenarioListItem,
} from '../types';

const API_BASE = import.meta.env.VITE_API_BASE || '/api';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options?.headers },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API Error ${res.status}: ${text}`);
  }
  return res.json();
}

export const api = {
  listScenarios: () => request<ScenarioListItem[]>('/scenarios'),

  getScenario: (id: number) => request<Scenario>(`/scenarios/${id}`),

  createScenario: (data: { name: string; description?: string }) =>
    request<Scenario>('/scenarios', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  updateScenario: (
    id: number,
    data: {
      name?: string;
      description?: string;
      twilio_phone_number?: string;
    },
  ) =>
    request<Scenario>(`/scenarios/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  deleteScenario: (id: number) =>
    request<{ ok: boolean }>(`/scenarios/${id}`, { method: 'DELETE' }),

  updateNodes: (scenarioId: number, nodes: ApiNode[]) =>
    request<{ ok: boolean }>(`/scenarios/${scenarioId}/nodes`, {
      method: 'PUT',
      body: JSON.stringify({ nodes }),
    }),

  updateEdges: (scenarioId: number, edges: ApiEdge[]) =>
    request<{ ok: boolean }>(`/scenarios/${scenarioId}/edges`, {
      method: 'PUT',
      body: JSON.stringify({ edges }),
    }),

  generateAudio: (scenarioId: number) =>
    request<AudioGenerationResult>(`/scenarios/${scenarioId}/generate-audio`, {
      method: 'POST',
    }),
};
