interface Props {
  conditionLabel: string;
  onUpdate: (conditionLabel: string) => void;
  onDelete: () => void;
}

export function EdgeEditPanel({ conditionLabel, onUpdate, onDelete }: Props) {
  return (
    <div style={panelStyle}>
      <h3 style={{ margin: '0 0 16px', fontSize: 15 }}>分岐条件編集</h3>

      <label style={labelStyle}>条件テキスト</label>
      <textarea
        style={{ ...inputStyle, minHeight: 80, resize: 'vertical' }}
        value={conditionLabel}
        onChange={(e) => onUpdate(e.target.value)}
        placeholder="分岐条件を入力（例: 予約したい, 問い合わせ）..."
      />

      <p style={{ fontSize: 11, color: '#6b7280', marginTop: 8 }}>
        顧客の発話がこの条件に意味的にマッチする場合、接続先のノードに遷移します。
      </p>

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
        分岐を削除
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
