import { useState } from 'react';
import type { ScenarioListItem } from '../types';

interface Props {
  scenarios: ScenarioListItem[];
  selectedId: number | null;
  onSelect: (id: number) => void;
  onCreate: (name: string) => void;
  onDelete: (id: number) => void;
}

export function ScenarioList({
  scenarios,
  selectedId,
  onSelect,
  onCreate,
  onDelete,
}: Props) {
  const [newName, setNewName] = useState('');

  const handleCreate = () => {
    const name = newName.trim();
    if (!name) return;
    onCreate(name);
    setNewName('');
  };

  return (
    <div style={sidebarStyle}>
      <h2 style={{ margin: '0 0 12px', fontSize: 16 }}>シナリオ一覧</h2>

      <div style={{ display: 'flex', gap: 6, marginBottom: 16 }}>
        <input
          style={inputStyle}
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
          placeholder="新しいシナリオ名"
        />
        <button onClick={handleCreate} style={createBtnStyle}>
          作成
        </button>
      </div>

      <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
        {scenarios.map((s) => (
          <li
            key={s.id}
            onClick={() => onSelect(s.id)}
            style={{
              ...itemStyle,
              background: s.id === selectedId ? '#eff6ff' : 'transparent',
              borderColor: s.id === selectedId ? '#3b82f6' : 'transparent',
            }}
          >
            <span style={{ fontWeight: 500 }}>{s.name}</span>
            <button
              onClick={(e) => {
                e.stopPropagation();
                onDelete(s.id);
              }}
              style={deleteBtnStyle}
            >
              ×
            </button>
          </li>
        ))}
      </ul>

      {scenarios.length === 0 && (
        <p style={{ fontSize: 12, color: '#9ca3af', textAlign: 'center' }}>
          シナリオがありません
        </p>
      )}
    </div>
  );
}

const sidebarStyle: React.CSSProperties = {
  width: 240,
  padding: 16,
  borderRight: '1px solid #e5e7eb',
  background: '#f9fafb',
  overflowY: 'auto',
  fontFamily: 'system-ui, sans-serif',
  flexShrink: 0,
};

const inputStyle: React.CSSProperties = {
  flex: 1,
  padding: '6px 10px',
  border: '1px solid #d1d5db',
  borderRadius: 6,
  fontSize: 13,
};

const createBtnStyle: React.CSSProperties = {
  padding: '6px 12px',
  background: '#3b82f6',
  color: '#fff',
  border: 'none',
  borderRadius: 6,
  cursor: 'pointer',
  fontSize: 13,
  fontWeight: 600,
  flexShrink: 0,
};

const itemStyle: React.CSSProperties = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  padding: '8px 10px',
  borderRadius: 6,
  cursor: 'pointer',
  border: '1px solid transparent',
  fontSize: 13,
  marginBottom: 2,
};

const deleteBtnStyle: React.CSSProperties = {
  background: 'none',
  border: 'none',
  color: '#9ca3af',
  cursor: 'pointer',
  fontSize: 16,
  lineHeight: 1,
  padding: '0 4px',
};
