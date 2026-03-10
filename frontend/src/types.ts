import type { Node, Edge } from '@xyflow/react';

export type NodeType = 'start' | 'end' | 'normal';

export interface ScenarioNodeData {
  label: string;
  script: string;
  nodeType: NodeType;
  hasAudio: boolean;
  [key: string]: unknown;
}

export type ScenarioNode = Node<ScenarioNodeData, 'scenario'>;

export interface ScenarioEdgeData {
  conditionLabel: string;
  [key: string]: unknown;
}

export type ScenarioEdge = Edge<ScenarioEdgeData>;

export interface ApiNode {
  id: string;
  label: string;
  script: string;
  node_type: NodeType;
  position_x: number;
  position_y: number;
  has_audio: boolean;
}

export interface ApiEdge {
  id: string;
  source_node_id: string;
  target_node_id: string;
  condition_label: string;
}

export interface Scenario {
  id: number;
  name: string;
  description: string | null;
  twilio_phone_number: string | null;
  nodes: ApiNode[];
  edges: ApiEdge[];
  created_at: string;
  updated_at: string;
}

export interface ScenarioListItem {
  id: number;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface AudioGenerationResult {
  generated: number;
  skipped: number;
  errors: { node_id: string; error: string }[];
}
