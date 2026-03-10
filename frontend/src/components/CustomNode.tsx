import { Handle, Position } from '@xyflow/react';
import type { NodeProps } from '@xyflow/react';
import type { ScenarioNodeData } from '../types';

const BORDER_COLORS: Record<string, string> = {
  start: '#22c55e',
  end: '#ef4444',
  normal: '#3b82f6',
};

const BADGE_COLORS: Record<string, string> = {
  start: '#dcfce7',
  end: '#fee2e2',
};

export function CustomNode({
  data,
  selected,
}: NodeProps & { data: ScenarioNodeData }) {
  const borderColor = BORDER_COLORS[data.nodeType] || BORDER_COLORS.normal;

  return (
    <div
      style={{
        border: `2px solid ${borderColor}`,
        borderRadius: 8,
        padding: 12,
        background: selected ? '#f0f9ff' : '#fff',
        minWidth: 200,
        maxWidth: 280,
        boxShadow: selected
          ? '0 0 0 2px #3b82f6'
          : '0 1px 3px rgba(0,0,0,0.12)',
        fontFamily: 'system-ui, sans-serif',
      }}
    >
      <Handle
        type="target"
        position={Position.Top}
        style={{ background: '#6b7280', width: 10, height: 10 }}
      />

      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          marginBottom: 6,
        }}
      >
        {data.nodeType !== 'normal' && (
          <span
            style={{
              fontSize: 10,
              fontWeight: 700,
              padding: '2px 6px',
              borderRadius: 4,
              background: BADGE_COLORS[data.nodeType] || '#f3f4f6',
              color: borderColor,
              textTransform: 'uppercase',
              letterSpacing: 0.5,
            }}
          >
            {data.nodeType}
          </span>
        )}
        <span style={{ fontWeight: 600, fontSize: 13 }}>{data.label}</span>
      </div>

      <div
        style={{
          fontSize: 11,
          color: '#6b7280',
          maxHeight: 50,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          lineHeight: 1.4,
        }}
      >
        {data.script || '(セリフ未設定)'}
      </div>

      {data.hasAudio && (
        <div
          style={{
            fontSize: 10,
            color: '#22c55e',
            marginTop: 6,
            display: 'flex',
            alignItems: 'center',
            gap: 4,
          }}
        >
          <span>&#9835;</span> 音声生成済み
        </div>
      )}

      <Handle
        type="source"
        position={Position.Bottom}
        style={{ background: '#6b7280', width: 10, height: 10 }}
      />
    </div>
  );
}
