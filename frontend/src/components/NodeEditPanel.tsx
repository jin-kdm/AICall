import type { ScenarioNodeData, NodeType } from '../types';

interface Props {
  data: ScenarioNodeData;
  onUpdate: (updates: Partial<ScenarioNodeData>) => void;
  onDelete: () => void;
}

export function NodeEditPanel({ data, onUpdate, onDelete }: Props) {
  return (
    <div style={panelStyle}>
      <h3 style={{ margin: '0 0 16px', fontSize: 15 }}>ノード編集</h3>

      <label style={labelStyle}>ラベル</label>
      <input
        style={inputStyle}
        value={data.label}
        onChange={(e) => onUpdate({ label: e.target.value })}
      />

      <label style={labelStyle}>セリフ（TTS テキスト）</label>
      <textarea
        style={{ ...inputStyle, minHeight: 120, resize: 'vertical' }}
        value={data.script}
        onChange={(e) => onUpdate({ script: e.target.value })}
        placeholder="AIが話すセリフを入力..."
      />

      <label style={labelStyle}>ノードタイプ</label>
      <select
        style={inputStyle}
        value={data.nodeType}
        onChange={(e) =>
          onUpdate({ nodeType: e.target.value as NodeType })
        }
      >
        <option value="normal">Normal（通常）</option>
        <option value="start">Start（開始）</option>
        <option value="end">End（終了）</option>
      </select>

      <div
        style={{
          marginTop: 12,
          fontSize: 12,
          color: data.hasAudio ? '#22c55e' : '#9ca3af',
        }}
      >
        音声: {data.hasAudio ? '生成済み' : '未生成'}
      </div>

      <button
        onClick={onDelete}
        style={{
          ...buttonStyle,
          marginTop: 16,
          background: '#fee2e2',
          color: '#ef4444',
          border: '1px solid #fca5a5',
        }}
      >
        ノードを削除
      </button>
    </div>
  );
}

const panelStyle: React.CSSProperties = {
  width: 280,
  padding: 16,
  borderLeft: '1px solid #e5e7eb',
  background: '#fafafa',
  overflowY: 'auto',
  fontFamily: 'system-ui, sans-serif',
  fontSize: 13,
};

const labelStyle: React.CSSProperties = {
  display: 'block',
  marginTop: 12,
  marginBottom: 4,
  fontWeight: 600,
  fontSize: 12,
  color: '#374151',
};

const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '8px 10px',
  border: '1px solid #d1d5db',
  borderRadius: 6,
  fontSize: 13,
  boxSizing: 'border-box',
  fontFamily: 'inherit',
};

const buttonStyle: React.CSSProperties = {
  width: '100%',
  padding: '8px 12px',
  borderRadius: 6,
  cursor: 'pointer',
  fontSize: 13,
  fontWeight: 600,
};
