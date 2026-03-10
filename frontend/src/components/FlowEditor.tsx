import { useCallback, useEffect, useState, useRef } from 'react';
import {
  ReactFlow,
  addEdge,
  useNodesState,
  useEdgesState,
  Controls,
  MiniMap,
  Background,
  type Connection,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import { CustomNode } from './CustomNode';
import { NodeEditPanel } from './NodeEditPanel';
import { EdgeEditPanel } from './EdgeEditPanel';
import { api } from '../api/client';
import type {
  ScenarioNode,
  ScenarioEdge,
  ScenarioNodeData,
  ApiNode,
  ApiEdge,
} from '../types';

const nodeTypes = { scenario: CustomNode };

function apiNodeToFlowNode(n: ApiNode): ScenarioNode {
  return {
    id: n.id,
    type: 'scenario',
    position: { x: n.position_x, y: n.position_y },
    data: {
      label: n.label,
      script: n.script,
      nodeType: n.node_type,
      hasAudio: n.has_audio,
    },
  };
}

function flowNodeToApiNode(n: ScenarioNode): ApiNode {
  return {
    id: n.id,
    label: n.data.label,
    script: n.data.script,
    node_type: n.data.nodeType,
    position_x: n.position?.x ?? 0,
    position_y: n.position?.y ?? 0,
    has_audio: n.data.hasAudio,
  };
}

function apiEdgeToFlowEdge(e: ApiEdge): ScenarioEdge {
  return {
    id: e.id,
    source: e.source_node_id,
    target: e.target_node_id,
    label: e.condition_label,
    data: { conditionLabel: e.condition_label },
    animated: true,
    style: { stroke: '#6b7280' },
  };
}

function flowEdgeToApiEdge(e: ScenarioEdge): ApiEdge {
  return {
    id: e.id,
    source_node_id: e.source,
    target_node_id: e.target,
    condition_label: e.data?.conditionLabel || (e.label as string) || '',
  };
}

interface Props {
  scenarioId: number;
  scenarioName: string;
  onPhoneUpdate: (phone: string) => void;
  twilioPhone: string;
}

export function FlowEditor({
  scenarioId,
  scenarioName,
  onPhoneUpdate,
  twilioPhone,
}: Props) {
  const [nodes, setNodes, onNodesChange] = useNodesState<ScenarioNode>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<ScenarioEdge>([]);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);
  const [isDirty, setIsDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [savePhase, setSavePhase] = useState('');
  const [statusMsg, setStatusMsg] = useState('');
  const nodeCounter = useRef(0);

  // Load scenario data
  useEffect(() => {
    api.getScenario(scenarioId).then((scenario) => {
      setNodes(scenario.nodes.map(apiNodeToFlowNode));
      setEdges(scenario.edges.map(apiEdgeToFlowEdge));
      setIsDirty(false);
      setSelectedNodeId(null);
      setSelectedEdgeId(null);
      nodeCounter.current = scenario.nodes.length;
    });
  }, [scenarioId, setNodes, setEdges]);

  const handleNodesChange = useCallback(
    (changes: Parameters<typeof onNodesChange>[0]) => {
      onNodesChange(changes);
      setIsDirty(true);
    },
    [onNodesChange],
  );

  const handleEdgesChange = useCallback(
    (changes: Parameters<typeof onEdgesChange>[0]) => {
      onEdgesChange(changes);
      setIsDirty(true);
    },
    [onEdgesChange],
  );

  const onConnect = useCallback(
    (connection: Connection) => {
      const id = `edge-${Date.now()}`;
      const newEdge: ScenarioEdge = {
        ...connection,
        id,
        label: '新しい条件',
        data: { conditionLabel: '新しい条件' },
        animated: true,
        style: { stroke: '#6b7280' },
      };
      setEdges((eds) => addEdge(newEdge, eds));
      setIsDirty(true);
    },
    [setEdges],
  );

  const onSave = useCallback(async () => {
    setSaving(true);
    setStatusMsg('');
    try {
      // Step 1: Save nodes and edges
      setSavePhase('保存中...');
      const apiNodes = nodes.map(flowNodeToApiNode);
      const apiEdges = edges.map(flowEdgeToApiEdge);
      await api.updateNodes(scenarioId, apiNodes);
      await api.updateEdges(scenarioId, apiEdges);
      setIsDirty(false);

      // Step 2: Auto-generate audio
      setSavePhase('音声生成中...');
      const result = await api.generateAudio(scenarioId);

      // Step 3: Build status message
      const parts: string[] = [];
      if (result.generated > 0) parts.push(`${result.generated}件生成`);
      if (result.skipped > 0) parts.push(`${result.skipped}件スキップ`);
      if (result.errors.length > 0)
        parts.push(`${result.errors.length}件エラー`);
      setStatusMsg(
        `保存・音声生成完了${parts.length > 0 ? ': ' + parts.join(', ') : ''}`,
      );

      // Step 4: Reload to update hasAudio flags
      const scenario = await api.getScenario(scenarioId);
      setNodes(scenario.nodes.map(apiNodeToFlowNode));
      setEdges(scenario.edges.map(apiEdgeToFlowEdge));
    } catch (e) {
      setStatusMsg(`保存エラー: ${e}`);
    } finally {
      setSaving(false);
      setSavePhase('');
    }
  }, [nodes, edges, scenarioId, setNodes, setEdges]);

  const onAddNode = useCallback(() => {
    nodeCounter.current += 1;
    const newNode: ScenarioNode = {
      id: `node-${Date.now()}-${nodeCounter.current}`,
      type: 'scenario',
      position: { x: 250, y: 100 + nodeCounter.current * 120 },
      data: {
        label: `ノード${nodeCounter.current}`,
        script: '',
        nodeType: 'normal',
        hasAudio: false,
      },
    };
    setNodes((nds) => [...nds, newNode]);
    setIsDirty(true);
  }, [setNodes]);

  const selectedNode = nodes.find((n) => n.id === selectedNodeId);
  const selectedEdge = edges.find((e) => e.id === selectedEdgeId);

  return (
    <div style={{ display: 'flex', flex: 1, height: '100%' }}>
      <div style={{ flex: 1, position: 'relative' }}>
        {/* Toolbar */}
        <div style={toolbarStyle}>
          <span style={{ fontWeight: 600, fontSize: 14 }}>{scenarioName}</span>
          <input
            style={{
              padding: '4px 8px',
              border: '1px solid #d1d5db',
              borderRadius: 4,
              fontSize: 12,
              width: 160,
            }}
            value={twilioPhone}
            onChange={(e) => onPhoneUpdate(e.target.value)}
            placeholder="Twilio電話番号"
          />
          <button onClick={onAddNode} style={toolbarBtnStyle}>
            + ノード追加
          </button>
          <button
            onClick={onSave}
            disabled={!isDirty || saving}
            style={{
              ...toolbarBtnStyle,
              background: isDirty ? '#3b82f6' : '#9ca3af',
              color: '#fff',
            }}
          >
            {saving ? savePhase || '保存中...' : '保存'}
          </button>
          {statusMsg && (
            <span style={{ fontSize: 12, color: '#6b7280' }}>{statusMsg}</span>
          )}
        </div>

        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={handleNodesChange}
          onEdgesChange={handleEdgesChange}
          onConnect={onConnect}
          onNodeClick={(_, node) => {
            setSelectedNodeId(node.id);
            setSelectedEdgeId(null);
          }}
          onEdgeClick={(_, edge) => {
            setSelectedEdgeId(edge.id);
            setSelectedNodeId(null);
          }}
          onPaneClick={() => {
            setSelectedNodeId(null);
            setSelectedEdgeId(null);
          }}
          nodeTypes={nodeTypes}
          fitView
          style={{ background: '#f8fafc' }}
        >
          <Controls />
          <MiniMap
            nodeStrokeWidth={3}
            style={{ background: '#f1f5f9' }}
          />
          <Background gap={16} size={1} />
        </ReactFlow>
      </div>

      {/* Right panel */}
      {selectedNode && (
        <NodeEditPanel
          data={selectedNode.data}
          onUpdate={(updates: Partial<ScenarioNodeData>) => {
            setNodes((nds) =>
              nds.map((n) =>
                n.id === selectedNodeId
                  ? { ...n, data: { ...n.data, ...updates } }
                  : n,
              ),
            );
            setIsDirty(true);
          }}
          onDelete={() => {
            setNodes((nds) => nds.filter((n) => n.id !== selectedNodeId));
            setEdges((eds) =>
              eds.filter(
                (e) =>
                  e.source !== selectedNodeId && e.target !== selectedNodeId,
              ),
            );
            setSelectedNodeId(null);
            setIsDirty(true);
          }}
        />
      )}
      {selectedEdge && !selectedNode && (
        <EdgeEditPanel
          conditionLabel={
            selectedEdge.data?.conditionLabel ||
            (selectedEdge.label as string) ||
            ''
          }
          onUpdate={(conditionLabel: string) => {
            setEdges((eds) =>
              eds.map((e) =>
                e.id === selectedEdgeId
                  ? {
                      ...e,
                      label: conditionLabel,
                      data: { ...e.data, conditionLabel },
                    }
                  : e,
              ),
            );
            setIsDirty(true);
          }}
          onDelete={() => {
            setEdges((eds) => eds.filter((e) => e.id !== selectedEdgeId));
            setSelectedEdgeId(null);
            setIsDirty(true);
          }}
        />
      )}
    </div>
  );
}

const toolbarStyle: React.CSSProperties = {
  position: 'absolute',
  top: 0,
  left: 0,
  right: 0,
  zIndex: 10,
  display: 'flex',
  alignItems: 'center',
  gap: 8,
  padding: '8px 16px',
  background: 'rgba(255,255,255,0.95)',
  borderBottom: '1px solid #e5e7eb',
  backdropFilter: 'blur(4px)',
};

const toolbarBtnStyle: React.CSSProperties = {
  padding: '6px 12px',
  border: '1px solid #d1d5db',
  borderRadius: 6,
  background: '#fff',
  cursor: 'pointer',
  fontSize: 12,
  fontWeight: 600,
};
